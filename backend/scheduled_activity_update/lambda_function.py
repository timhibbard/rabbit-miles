# scheduled_activity_update Lambda function
# Runs every hour to update recent activities for all connected users
# Updates activities from the last 24 hours from Strava API
# 
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)

import os
import json
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")
lambda_client = boto3.client("lambda")

# Logging constants
SEPARATOR_LINE = "=" * 80


def log(message, level="INFO"):
    """Enhanced logging with timestamp and level"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    print(f"[{timestamp}] [{level}] {message}")

# Get environment variables safely - they are checked in handler
DB_CLUSTER_ARN = None
DB_SECRET_ARN = None
DB_NAME = None

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

# Filter activities starting from Jan 1, 2026 00:00:00 UTC
# Unix timestamp: 1767225600
ACTIVITIES_START_DATE = 1767225600

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300

# Update activities from the last 24 hours
UPDATE_WINDOW_SECONDS = 24 * 60 * 60

# Strava rate limit state (module-level, shared across calls within a single invocation)
_rate_limit_used = 0
_rate_limit_limit = 100  # Strava default

# Pause when this many requests remain in the current 15-minute window
RATE_LIMIT_SAFETY_MARGIN = 5

# Maximum retries on HTTP 429
MAX_RETRIES = 3

# Maximum wait time between retries (capped well below Lambda's 15-min hard cap so a
# single bad user can't time out the entire batch). Above this, we abort the run
# and let the next scheduled invocation pick up where we left off.
MAX_RETRY_WAIT_SECONDS = 120

# Skip users whose data was already kept fresh by webhooks within this window.
# The hourly job is only a backstop for missed webhooks.
WEBHOOK_FRESHNESS_SECONDS = 6 * 60 * 60  # 6 hours

# How many users to process per invocation. If more users remain, we self-invoke
# the lambda to continue, so one Lambda execution never spans more than this many.
USERS_PER_INVOCATION = 25

# Stop processing and self-continue when remaining Lambda time drops below this.
LAMBDA_TIME_REMAINING_SAFETY_MS = 90 * 1000  # 90 seconds


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


def _exec_sql(sql, parameters=None):
    """Execute SQL statement using RDS Data API"""
    global DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME
    
    if DB_CLUSTER_ARN is None:
        DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
    if DB_SECRET_ARN is None:
        DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
    if DB_NAME is None:
        DB_NAME = os.environ.get("DB_NAME", "postgres")
    
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def refresh_access_token(athlete_id, refresh_token):
    """Refresh expired Strava access token"""
    client_id, client_secret = _get_strava_creds()
    
    body = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    
    req = Request(STRAVA_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    
    try:
        with urlopen(req, timeout=20) as resp:
            token_resp = json.loads(resp.read().decode())
        
        access_token = token_resp.get("access_token")
        new_refresh_token = token_resp.get("refresh_token")
        expires_at = int(token_resp.get("expires_at") or 0)
        
        if not access_token:
            raise RuntimeError(f"Token refresh failed: {token_resp}")
        
        # Update tokens in database
        sql = """
        UPDATE users 
        SET access_token = :at, refresh_token = :rt, expires_at = :exp, updated_at = now()
        WHERE athlete_id = :aid
        """
        params = [
            {"name": "at", "value": {"stringValue": access_token}},
            {"name": "rt", "value": {"stringValue": new_refresh_token}},
            {"name": "exp", "value": {"longValue": expires_at}},
            {"name": "aid", "value": {"longValue": athlete_id}},
        ]
        _exec_sql(sql, params)
        
        log(f"Refreshed access token for athlete {athlete_id}", "INFO")
        return access_token
    except Exception as e:
        log(f"Failed to refresh token for athlete {athlete_id}: {e}", "ERROR")
        raise


def ensure_valid_token(athlete_id, access_token, refresh_token, expires_at):
    """Ensure access token is valid, refresh if needed"""
    current_time = int(time.time())
    
    # Check if token needs refresh
    if expires_at < current_time + TOKEN_REFRESH_BUFFER_SECONDS:
        log(f"Access token expired or expiring soon for athlete {athlete_id}, refreshing...", "INFO")
        access_token = refresh_access_token(athlete_id, refresh_token)
    
    return access_token


def _update_rate_limit_from_headers(headers):
    """Parse and store Strava rate limit headers from a response.

    Prefer read rate-limit headers when present to avoid exceeding the lower
    read quota.
    """
    global _rate_limit_used, _rate_limit_limit
    usage = (
        headers.get("X-ReadRateLimit-Usage")
        or headers.get("x-readratelimit-usage")
        or headers.get("X-RateLimit-Usage")
        or headers.get("x-ratelimit-usage")
    )
    limit = (
        headers.get("X-ReadRateLimit-Limit")
        or headers.get("x-readratelimit-limit")
        or headers.get("X-RateLimit-Limit")
        or headers.get("x-ratelimit-limit")
    )
    if usage:
        try:
            _rate_limit_used = int(usage.split(",")[0])
        except (ValueError, IndexError):
            pass
    if limit:
        try:
            _rate_limit_limit = int(limit.split(",")[0])
        except (ValueError, IndexError):
            pass


class RateLimitExhaustedError(Exception):
    """Raised when we'd need to wait longer than is safe inside this Lambda
    invocation. The caller should stop processing and let the next scheduled
    run pick up the rest."""


def _seconds_until_lambda_deadline(context):
    """Return remaining ms in the current Lambda invocation, or +inf if no context."""
    if context and hasattr(context, "get_remaining_time_in_millis"):
        try:
            return context.get_remaining_time_in_millis()
        except Exception:
            return float("inf")
    return float("inf")


def _wait_if_rate_limited(context=None):
    """Pause if we are approaching Strava's 15-minute rate limit.

    Raises RateLimitExhaustedError when sleeping would exceed our remaining
    Lambda budget; the caller should abort and let the next run continue.
    """
    global _rate_limit_used
    if _rate_limit_used >= _rate_limit_limit - RATE_LIMIT_SAFETY_MARGIN:
        now = time.time()
        seconds_into_window = now % (15 * 60)
        wait = (15 * 60) - seconds_into_window + 5  # +5s buffer

        remaining_ms = _seconds_until_lambda_deadline(context)
        if wait * 1000 > remaining_ms - LAMBDA_TIME_REMAINING_SAFETY_MS:
            log(f"Rate limit hit and {wait:.0f}s wait exceeds remaining Lambda time ({remaining_ms/1000:.0f}s); aborting batch", "WARNING")
            raise RateLimitExhaustedError("not enough Lambda time to wait out rate limit window")

        log(f"Rate limit approaching ({_rate_limit_used}/{_rate_limit_limit}), sleeping {wait:.0f}s for window reset", "WARNING")
        time.sleep(wait)
        _rate_limit_used = 0


def _strava_get(req, context=None, timeout=30):
    """Shared Strava GET with rate-limit awareness and 429 retry."""
    for attempt in range(MAX_RETRIES + 1):
        _wait_if_rate_limited(context)
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode()
                _update_rate_limit_from_headers(dict(resp.headers))
                return json.loads(body)
        except HTTPError as e:
            if e.code == 429:
                if attempt < MAX_RETRIES:
                    wait = min(60 * (2 ** attempt), MAX_RETRY_WAIT_SECONDS)
                    remaining_ms = _seconds_until_lambda_deadline(context)
                    if wait * 1000 > remaining_ms - LAMBDA_TIME_REMAINING_SAFETY_MS:
                        log(f"429 received but {wait}s retry exceeds remaining Lambda time; aborting", "WARNING")
                        raise RateLimitExhaustedError("not enough Lambda time to retry after 429") from e
                    log(f"429 received, retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})", "WARNING")
                    time.sleep(wait)
                    continue
            raise


def fetch_strava_activities(access_token, after_timestamp, context=None, per_page=200):
    """Fetch activities from Strava API after a given timestamp"""
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page=1&after={after_timestamp}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})

    try:
        activities = _strava_get(req, context=context, timeout=30)
        log(f"Fetched {len(activities) if isinstance(activities, list) else 'non-list'} activities from Strava", "INFO")
        return activities
    except Exception as e:
        log(f"Failed to fetch activities from Strava: {e}", "ERROR")
        if hasattr(e, 'code'):
            log(f"HTTP status code: {e.code}", "ERROR")
        if hasattr(e, 'read'):
            try:
                error_body = e.read().decode()
                log(f"Error response body: {error_body}", "ERROR")
            except Exception:
                pass
        raise


def store_activity(athlete_id, activity):
    """Store or update activity in database"""
    strava_activity_id = activity.get("id")
    if not strava_activity_id:
        log(f"Activity missing id: {activity}", "ERROR")
        return False
    
    # Extract activity data
    name = activity.get("name", "")
    distance = activity.get("distance", 0)  # meters
    moving_time = activity.get("moving_time", 0)  # seconds
    elapsed_time = activity.get("elapsed_time", 0)  # seconds
    total_elevation_gain = activity.get("total_elevation_gain", 0)
    activity_type = activity.get("type", "")
    start_date = activity.get("start_date", "")
    start_date_local = activity.get("start_date_local", "")
    timezone = activity.get("timezone", "")
    athlete_count = activity.get("athlete_count", 1)  # Default to 1 for solo activities
    
    # Get polyline from map - prefer full polyline over summary_polyline
    polyline = ""
    if activity.get("map"):
        # Try full polyline first, fallback to summary_polyline
        polyline = activity["map"].get("polyline") or activity["map"].get("summary_polyline", "")
    
    # Insert or update activity
    # Note: time_on_trail and distance_on_trail are computed separately by trail matching logic
    # We initialize them as NULL and preserve existing values on update using COALESCE
    # This ensures computed trail metrics aren't accidentally overwritten during activity updates
    sql = """
    INSERT INTO activities (
        athlete_id, strava_activity_id, name, distance, moving_time, elapsed_time,
        total_elevation_gain, type, start_date, start_date_local, timezone, polyline,
        athlete_count, time_on_trail, distance_on_trail, updated_at
    )
    VALUES (:aid, :sid, :name, :dist, :mt, :et, :elev, :type, CAST(:sd AS TIMESTAMP), CAST(:sdl AS TIMESTAMP), :tz, :poly, :ac, NULL, NULL, now())
    ON CONFLICT (athlete_id, strava_activity_id) 
    DO UPDATE SET
        name = EXCLUDED.name,
        distance = EXCLUDED.distance,
        moving_time = EXCLUDED.moving_time,
        elapsed_time = EXCLUDED.elapsed_time,
        total_elevation_gain = EXCLUDED.total_elevation_gain,
        type = EXCLUDED.type,
        start_date = EXCLUDED.start_date,
        start_date_local = EXCLUDED.start_date_local,
        timezone = EXCLUDED.timezone,
        polyline = EXCLUDED.polyline,
        athlete_count = EXCLUDED.athlete_count,
        time_on_trail = COALESCE(activities.time_on_trail, EXCLUDED.time_on_trail),
        distance_on_trail = COALESCE(activities.distance_on_trail, EXCLUDED.distance_on_trail),
        updated_at = now()
    """
    
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "sid", "value": {"longValue": strava_activity_id}},
        {"name": "name", "value": {"stringValue": name}},
        {"name": "dist", "value": {"doubleValue": float(distance)}},
        {"name": "mt", "value": {"longValue": moving_time}},
        {"name": "et", "value": {"longValue": elapsed_time}},
        {"name": "elev", "value": {"doubleValue": float(total_elevation_gain)}},
        {"name": "type", "value": {"stringValue": activity_type}},
        {"name": "sd", "value": {"stringValue": start_date} if start_date else {"isNull": True}},
        {"name": "sdl", "value": {"stringValue": start_date_local} if start_date_local else {"isNull": True}},
        {"name": "tz", "value": {"stringValue": timezone}},
        {"name": "poly", "value": {"stringValue": polyline} if polyline else {"isNull": True}},
        {"name": "ac", "value": {"longValue": athlete_count}},
    ]
    
    try:
        _exec_sql(sql, params)
        log(f"Successfully stored activity {strava_activity_id}: {name}", "INFO")
        return True
    except Exception as e:
        log(f"Failed to store activity {strava_activity_id}: {e}", "ERROR")
        return False


def get_users_needing_poll():
    """Get connected users that webhooks have not kept fresh recently.

    Skips users whose last_webhook_received_at is within WEBHOOK_FRESHNESS_SECONDS
    so we only poll the backstop set, not every connected user. Users that have
    never received a webhook are always included.

    Falls back to "all connected users" if the column does not yet exist
    (so this works before migration 011 has run).
    """
    sql_with_filter = f"""
    SELECT athlete_id, access_token, refresh_token, expires_at
    FROM users
    WHERE access_token IS NOT NULL
      AND refresh_token IS NOT NULL
      AND (
        last_webhook_received_at IS NULL
        OR last_webhook_received_at < NOW() - INTERVAL '{WEBHOOK_FRESHNESS_SECONDS} seconds'
      )
    ORDER BY athlete_id
    """
    sql_fallback = """
    SELECT athlete_id, access_token, refresh_token, expires_at
    FROM users
    WHERE access_token IS NOT NULL
      AND refresh_token IS NOT NULL
    ORDER BY athlete_id
    """
    try:
        result = _exec_sql(sql_with_filter)
    except Exception as e:
        log(f"last_webhook_received_at filter failed ({e}); falling back to all connected users", "WARNING")
        result = _exec_sql(sql_fallback)

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
                "expires_at": expires_at
            })

    return users


def update_recent_activities_for_user(user, context=None):
    """Update recent activities for a single user.

    The per-user `/athlete` profile call has been removed: it doubled the
    rate-limit budget for no functional benefit (profile pics are not
    time-sensitive). Re-add it as a separate, less-frequent job if needed.
    """
    athlete_id = user["athlete_id"]
    access_token = user["access_token"]
    refresh_token = user["refresh_token"]
    expires_at = user["expires_at"]

    try:
        log(f"Processing user {athlete_id}...", "INFO")

        # Ensure token is valid
        access_token = ensure_valid_token(athlete_id, access_token, refresh_token, expires_at)

        # Calculate timestamp for 24 hours ago
        current_time = int(time.time())
        after_timestamp = max(ACTIVITIES_START_DATE, current_time - UPDATE_WINDOW_SECONDS)

        # Fetch recent activities
        activities = fetch_strava_activities(access_token, after_timestamp, context=context)

        if not isinstance(activities, list):
            log(f"Unexpected response from Strava API for user {athlete_id}: {type(activities)}", "ERROR")
            return {"athlete_id": athlete_id, "success": False, "error": "Invalid API response"}

        # Store activities
        stored_count = 0
        failed_count = 0

        for activity in activities:
            if store_activity(athlete_id, activity):
                stored_count += 1
            else:
                failed_count += 1

        log(f"User {athlete_id}: Stored {stored_count}, Failed {failed_count} out of {len(activities)} activities", "INFO")

        return {
            "athlete_id": athlete_id,
            "success": True,
            "total_activities": len(activities),
            "stored": stored_count,
            "failed": failed_count
        }

    except RateLimitExhaustedError:
        # Bubble up so the handler can stop processing and self-continue.
        raise
    except Exception as e:
        log(f"Processing user {athlete_id}: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return {"athlete_id": athlete_id, "success": False, "error": str(e)}


def _self_continue(context, remaining_athlete_ids):
    """Re-invoke this Lambda asynchronously to process the remaining users.

    Avoids running every connected user in a single invocation: bounded batches
    keep us comfortably inside Lambda's 15-minute hard cap and isolate the
    blast radius of one slow user.
    """
    function_name = (context.function_name if context else None) or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    if not function_name:
        log("Cannot self-continue: function name unknown", "WARNING")
        return False
    try:
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps({"continue_athlete_ids": remaining_athlete_ids}).encode(),
        )
        log(f"Self-invoked to continue with {len(remaining_athlete_ids)} remaining users", "INFO")
        return True
    except Exception as e:
        log(f"Failed to self-continue ({e}); next scheduled run will pick them up", "WARNING")
        return False


def handler(event, context):
    """
    Lambda handler for scheduled activity updates.

    Runs every hour as a backstop for missed webhooks. Two execution modes:
      1. Scheduled invoke (no `continue_athlete_ids` in event): pulls connected
         users that webhooks have not kept fresh recently, processes the first
         USERS_PER_INVOCATION, and self-invokes for the rest.
      2. Continuation invoke (`continue_athlete_ids` in event): processes only
         the supplied athlete IDs and self-invokes again if needed.
    """
    start_time = datetime.utcnow()
    log(SEPARATOR_LINE, "INFO")
    log("SCHEDULED ACTIVITY UPDATE - START", "INFO")
    log(f"Execution started at: {start_time.isoformat()}Z", "INFO")
    log(f"Event: {json.dumps(event, default=str)}", "INFO")
    log(SEPARATOR_LINE, "INFO")

    if not os.environ.get("DB_CLUSTER_ARN") or not os.environ.get("DB_SECRET_ARN"):
        log("Missing DB_CLUSTER_ARN or DB_SECRET_ARN", "ERROR")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }

    try:
        continue_ids = event.get("continue_athlete_ids") if isinstance(event, dict) else None
        if continue_ids:
            log(f"Continuation invocation: {len(continue_ids)} athlete IDs", "INFO")
            all_users = get_users_needing_poll()
            id_set = set(continue_ids)
            users = [u for u in all_users if u["athlete_id"] in id_set]
            log(f"Resolved {len(users)} of {len(continue_ids)} continuation IDs to active users", "INFO")
        else:
            log("Fetching connected users that webhooks have not kept fresh...", "INFO")
            users = get_users_needing_poll()
            log(f"Found {len(users)} users to poll (webhook-stale or never-webhooked)", "INFO")

        if not users:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            log(f"SCHEDULED ACTIVITY UPDATE - SUCCESS (No Users), duration {duration:.1f}s", "INFO")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No users to poll", "total_users": 0, "results": []})
            }

        # Process this chunk; defer the rest to a continuation invocation.
        chunk = users[:USERS_PER_INVOCATION]
        remaining_ids = [u["athlete_id"] for u in users[USERS_PER_INVOCATION:]]

        results = []
        aborted_early = False
        for user in chunk:
            # Time-budget guard: leave headroom for the self-continue invocation.
            remaining_ms = _seconds_until_lambda_deadline(context)
            if remaining_ms < LAMBDA_TIME_REMAINING_SAFETY_MS:
                log(f"Lambda time budget exhausted ({remaining_ms/1000:.0f}s remaining); aborting chunk early", "WARNING")
                # Push unprocessed chunk users back onto the continuation list.
                idx = chunk.index(user)
                remaining_ids = [u["athlete_id"] for u in chunk[idx:]] + remaining_ids
                aborted_early = True
                break

            try:
                results.append(update_recent_activities_for_user(user, context=context))
            except RateLimitExhaustedError:
                log("Rate limit exhausted; aborting chunk and deferring rest to next scheduled run", "WARNING")
                idx = chunk.index(user)
                remaining_ids = [u["athlete_id"] for u in chunk[idx:]] + remaining_ids
                aborted_early = True
                break

            time.sleep(1)  # pace requests to avoid rate limit burst

        if remaining_ids and not aborted_early:
            _self_continue(context, remaining_ids)
        elif remaining_ids and aborted_early:
            # Don't immediately self-invoke after a rate-limit/time abort —
            # let the next scheduled run pick it up after the window resets.
            log(f"{len(remaining_ids)} users deferred to next scheduled run", "INFO")

        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        total_stored = sum(r.get("stored", 0) for r in results)

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        log(SEPARATOR_LINE, "INFO")
        log("EXECUTION SUMMARY:", "INFO")
        log(f"  Users processed this invocation: {len(results)}", "INFO")
        log(f"  Users deferred to continuation: {len(remaining_ids)}", "INFO")
        log(f"  Successful: {successful}", "INFO")
        log(f"  Failed: {failed}", "INFO")
        log(f"  Activities stored: {total_stored}", "INFO")
        log(f"  Rate limit usage: {_rate_limit_used}/{_rate_limit_limit}", "INFO")
        log(f"  Duration: {duration:.2f}s", "INFO")
        log(SEPARATOR_LINE, "INFO")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Scheduled activity update completed",
                "users_processed": len(results),
                "users_deferred": len(remaining_ids),
                "successful_updates": successful,
                "failed_updates": failed,
                "total_activities_stored": total_stored,
                "results": results,
            })
        }

    except Exception as e:
        log(f"Error in scheduled_activity_update handler: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error", "details": str(e)})
        }
