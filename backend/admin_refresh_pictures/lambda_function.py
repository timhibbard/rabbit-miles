# admin_refresh_pictures Lambda function
# Admin endpoint to re-fetch every connected user's Strava profile picture.
#
# Strava versions its avatar URLs, so a URL captured at login 404s once the
# athlete changes their photo. This endpoint force-refreshes all stored
# pictures on demand (the hourly scheduled poll also does this, but throttled).
#
# Path: POST /admin/refresh-pictures
#
# Because refreshing every user makes one Strava GET per user (which can exceed
# API Gateway's 30s timeout), the request handler validates admin auth and then
# self-invokes asynchronously to do the work in the background, mirroring
# admin_recalculate_leaderboard.
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)
# ADMIN_ATHLETE_IDS (comma-separated list of admin athlete IDs)

import os
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
import boto3

import admin_utils

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")
lambda_client = boto3.client("lambda")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
LAMBDA_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ATHLETE_URL = "https://www.strava.com/api/v3/athlete"

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300

# Strava read rate limit (300 requests / 15 min). Pause when this many remain.
RATE_LIMIT_LIMIT = 300
RATE_LIMIT_SAFETY_MARGIN = 5
MAX_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 120
# Leave headroom before the async Lambda's own timeout when deciding to sleep.
LAMBDA_TIME_REMAINING_SAFETY_MS = 30 * 1000

# Module-level rate-limit tracking within a single invocation.
_rate_limit_used = 0


def get_cors_origin():
    """Extract origin (scheme + host) from FRONTEND_URL for CORS headers"""
    if not FRONTEND_URL:
        return None
    parsed = urlparse(FRONTEND_URL)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _get_strava_creds():
    """Get Strava client credentials from env or Secrets Manager"""
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    secret_arn = os.environ.get("STRAVA_SECRET_ARN")

    if (not client_id or not client_secret) and secret_arn:
        resp = sm.get_secret_value(SecretId=secret_arn)
        data = json.loads(resp["SecretString"])
        client_id = client_id or str(data.get("client_id") or data.get("clientId"))
        client_secret = client_secret or str(data.get("client_secret") or data.get("clientSecret"))

    if not client_id or not client_secret:
        raise RuntimeError("Missing STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET")

    return client_id, client_secret


def exec_sql(sql, parameters=None):
    """Execute SQL using RDS Data API"""
    kwargs = dict(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        sql=sql,
        database=DB_NAME,
    )
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def refresh_access_token(athlete_id, refresh_token):
    """Refresh expired Strava access token and persist it."""
    client_id, client_secret = _get_strava_creds()

    body = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    req = Request(STRAVA_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=20) as resp:
        token_resp = json.loads(resp.read().decode())

    access_token = token_resp.get("access_token")
    new_refresh_token = token_resp.get("refresh_token")
    expires_at = int(token_resp.get("expires_at") or 0)
    if not access_token:
        raise RuntimeError(f"Token refresh failed: {token_resp}")

    sql = """
    UPDATE users
    SET access_token = :at, refresh_token = :rt, expires_at = :exp, updated_at = now()
    WHERE athlete_id = :aid
    """
    exec_sql(sql, [
        {"name": "at", "value": {"stringValue": access_token}},
        {"name": "rt", "value": {"stringValue": new_refresh_token}},
        {"name": "exp", "value": {"longValue": expires_at}},
        {"name": "aid", "value": {"longValue": athlete_id}},
    ])
    print(f"LOG - Refreshed access token for athlete {athlete_id}")
    return access_token


def ensure_valid_token(athlete_id, access_token, refresh_token, expires_at):
    """Ensure access token is valid, refresh if needed"""
    if expires_at < int(time.time()) + TOKEN_REFRESH_BUFFER_SECONDS:
        return refresh_access_token(athlete_id, refresh_token)
    return access_token


def _update_rate_limit_from_headers(headers):
    """Track Strava read-limit usage from response headers."""
    global _rate_limit_used
    usage = (
        headers.get("X-ReadRateLimit-Usage")
        or headers.get("x-readratelimit-usage")
        or headers.get("X-RateLimit-Usage")
        or headers.get("x-ratelimit-usage")
    )
    if usage:
        try:
            _rate_limit_used = int(usage.split(",")[0])
        except (ValueError, IndexError):
            pass


def _remaining_lambda_ms(context):
    if context and hasattr(context, "get_remaining_time_in_millis"):
        try:
            return context.get_remaining_time_in_millis()
        except Exception:
            return float("inf")
    return float("inf")


class RateLimitExhaustedError(Exception):
    """Raised when waiting out the rate-limit window would exceed our Lambda budget."""


def _wait_if_rate_limited(context):
    """Pause if approaching Strava's 15-minute read limit."""
    global _rate_limit_used
    if _rate_limit_used >= RATE_LIMIT_LIMIT - RATE_LIMIT_SAFETY_MARGIN:
        seconds_into_window = time.time() % (15 * 60)
        wait = (15 * 60) - seconds_into_window + 5
        if wait * 1000 > _remaining_lambda_ms(context) - LAMBDA_TIME_REMAINING_SAFETY_MS:
            raise RateLimitExhaustedError("not enough Lambda time to wait out rate limit window")
        print(f"LOG - Rate limit approaching ({_rate_limit_used}/{RATE_LIMIT_LIMIT}), sleeping {wait:.0f}s")
        time.sleep(wait)
        _rate_limit_used = 0


def fetch_strava_athlete(access_token, context):
    """Fetch athlete profile from Strava (rate-limit aware, retries on 429)."""
    req = Request(STRAVA_ATHLETE_URL, headers={"Authorization": f"Bearer {access_token}"})
    for attempt in range(MAX_RETRIES + 1):
        _wait_if_rate_limited(context)
        try:
            with urlopen(req, timeout=20) as resp:
                body = resp.read().decode()
                _update_rate_limit_from_headers(dict(resp.headers))
                return json.loads(body)
        except HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                wait = min(60 * (2 ** attempt), MAX_RETRY_WAIT_SECONDS)
                if wait * 1000 > _remaining_lambda_ms(context) - LAMBDA_TIME_REMAINING_SAFETY_MS:
                    raise RateLimitExhaustedError("not enough Lambda time to retry after 429") from e
                print(f"LOG - 429 received, retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            print(f"LOG - Failed to fetch athlete profile: HTTP {e.code}")
            return None
        except Exception as e:
            print(f"LOG - Failed to fetch athlete profile: {e}")
            return None


def get_connected_users():
    """Get all users connected to Strava (have tokens)."""
    sql = """
    SELECT athlete_id, access_token, refresh_token, expires_at
    FROM users
    WHERE access_token IS NOT NULL AND refresh_token IS NOT NULL
    ORDER BY athlete_id
    """
    result = exec_sql(sql)
    users = []
    for record in result.get("records", []):
        athlete_id = int(record[0].get("longValue", 0))
        access_token = record[1].get("stringValue", "")
        refresh_token = record[2].get("stringValue", "")
        expires_at = int(record[3].get("longValue", 0))
        if athlete_id and access_token and refresh_token:
            users.append({
                "athlete_id": athlete_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            })
    return users


def persist_profile_picture(athlete_id, athlete):
    """Persist the athlete's current profile picture to the database."""
    if not isinstance(athlete, dict):
        return False
    profile_picture = athlete.get("profile_medium") or athlete.get("profile") or ""

    sql = """
    UPDATE users
    SET profile_picture = :pic,
        profile_picture_updated_at = now(),
        updated_at = now()
    WHERE athlete_id = :aid
    """
    params = [{"name": "aid", "value": {"longValue": athlete_id}}]
    if profile_picture:
        params.append({"name": "pic", "value": {"stringValue": profile_picture}})
    else:
        params.append({"name": "pic", "value": {"isNull": True}})

    exec_sql(sql, params)
    return True


def refresh_all_pictures(context):
    """Re-fetch and persist every connected user's profile picture."""
    users = get_connected_users()
    print(f"LOG - Refreshing pictures for {len(users)} connected users")

    updated = 0
    failed = 0
    aborted = False
    for user in users:
        athlete_id = user["athlete_id"]
        try:
            access_token = ensure_valid_token(
                athlete_id, user["access_token"], user["refresh_token"], user["expires_at"]
            )
            athlete = fetch_strava_athlete(access_token, context)
            if athlete and persist_profile_picture(athlete_id, athlete):
                updated += 1
            else:
                failed += 1
        except RateLimitExhaustedError:
            # Stop cleanly; remaining users keep their existing pictures and the
            # hourly poll (or a repeat click) will catch them up.
            print("LOG - Rate limit budget exhausted; stopping early")
            aborted = True
            break
        except Exception as e:
            print(f"LOG - Failed to refresh picture for athlete {athlete_id}: {e}")
            failed += 1

    return {
        "total_users": len(users),
        "updated": updated,
        "failed": failed,
        "aborted": aborted,
    }


def handler(event, context):
    print("=" * 80)
    print("ADMIN REFRESH PICTURES - START")
    print("=" * 80)

    start_time = time.time()
    cors_origin = get_cors_origin()
    headers = admin_utils.get_admin_headers(cors_origin)

    # Background invocation: skip auth (already verified) and do the work.
    if event.get("async_invocation") is True:
        print("LOG - Running as async invocation (background task)")
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
            return {"statusCode": 500, "body": json.dumps({"error": "server configuration error"})}

        result = refresh_all_pictures(context)
        duration_ms = (time.time() - start_time) * 1000
        print(f"LOG - Refreshed {result['updated']}/{result['total_users']} pictures "
              f"({result['failed']} failed) in {duration_ms:.0f}ms")
        print("=" * 80)
        print("ADMIN REFRESH PICTURES - SUCCESS")
        print("=" * 80)
        return {"statusCode": 200, "body": json.dumps({**result, "duration_ms": round(duration_ms, 2)})}

    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                **headers,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Cookie",
                "Access-Control-Max-Age": "86400",
            },
            "body": "",
        }

    try:
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN or not APP_SECRET or not LAMBDA_FUNCTION_NAME:
            print("ERROR - Missing required environment variables")
            return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": "server configuration error"})}

        athlete_id, is_admin = admin_utils.verify_admin_session(event, APP_SECRET)
        if not athlete_id:
            return {"statusCode": 401, "headers": headers, "body": json.dumps({"error": "not authenticated"})}
        if not is_admin:
            admin_utils.audit_log_admin_action(
                athlete_id, "/admin/refresh-pictures", "access_denied", {"reason": "not in admin allowlist"}
            )
            return {"statusCode": 403, "headers": headers, "body": json.dumps({"error": "forbidden"})}

        print(f"LOG - Admin {athlete_id} triggering profile picture refresh")
        admin_utils.audit_log_admin_action(
            athlete_id, "/admin/refresh-pictures", "refresh_pictures_triggered"
        )

        # Self-invoke asynchronously to run past the API Gateway 30s timeout.
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps({"async_invocation": True, "triggered_by_athlete_id": athlete_id}),
        )
        status_code = response.get("StatusCode")
        if status_code not in [200, 202]:
            print(f"ERROR - Lambda invocation returned unexpected status code: {status_code}")
            return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": "Failed to trigger refresh"})}

        return {
            "statusCode": 202,
            "headers": headers,
            "body": json.dumps({
                "message": "Profile picture refresh started. This runs in the background and may take a minute.",
                "status": "processing",
            }),
        }

    except Exception as e:
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": "internal server error"})}
