# rabbitmiles-auth-callback (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# API_BASE_URL (ex: https://9zke9jame0.execute-api.us-east-1.amazonaws.com)
# FRONTEND_URL (ex: https://<you>.github.io/rabbitmiles)
# APP_SECRET (long random string)
# STRAVA_CLIENT_ID
# STRAVA_CLIENT_SECRET   (or set STRAVA_SECRET_ARN instead)
# STRAVA_SECRET_ARN      (optional, JSON: {"client_id":"...","client_secret":"..."})

import os
import json
import time
import hmac
import hashlib
import base64
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")

# Get environment variables safely - validation happens in handler
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")

API_BASE = os.environ.get("API_BASE_URL", "").rstrip("/")
FRONTEND = os.environ.get("FRONTEND_URL", "").rstrip("/")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

# Extract path from API_BASE_URL for cookie Path attribute
# API_BASE_URL format: https://domain.com/stage or https://domain.com
# We need the path portion (e.g., /stage) for cookies to work with API Gateway
_parsed_api_base = urlparse(API_BASE) if API_BASE else None
COOKIE_PATH = _parsed_api_base.path if _parsed_api_base and _parsed_api_base.path else "/"


def _parse_cookies(event: dict) -> dict:
    """Parse cookies from API Gateway HTTP API v2 event format or headers"""
    out = {}
    
    # API Gateway HTTP API v2 provides cookies in event['cookies'] array
    cookies_array = event.get("cookies") or []
    for cookie_str in cookies_array:
        if not cookie_str or "=" not in cookie_str:
            continue
        # Handle cookie strings that might have multiple cookies separated by semicolons
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            out[k] = v
    
    # Also check headers for backwards compatibility
    headers = event.get("headers") or {}
    cookie_header = headers.get("cookie") or headers.get("Cookie") or ""
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            # Prefer cookies from event['cookies'] array (v2 format) over headers (v1 format)
            if k not in out:
                out[k] = v
    
    return out


def _get_strava_creds() -> tuple[str, str]:
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    secret_arn = os.environ.get("STRAVA_SECRET_ARN")

    if (not client_id or not client_secret) and secret_arn:
        resp = sm.get_secret_value(SecretId=secret_arn)
        data = json.loads(resp["SecretString"])
        client_id = client_id or str(data.get("client_id") or data.get("clientId"))
        client_secret = client_secret or str(data.get("client_secret") or data.get("clientSecret"))

    if not client_id or not client_secret:
        raise RuntimeError("Missing STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN).")

    return client_id, client_secret


def _exec_sql(sql: str, parameters: list | None = None):
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def _make_session_token(athlete_id: int, days: int = 30) -> str:
    payload = {"aid": int(athlete_id), "exp": int(time.time()) + days * 24 * 3600}
    b = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
    return f"{b}.{sig}"


def handler(event, context):
    qs = event.get("queryStringParameters") or {}
    code = qs.get("code")
    state = qs.get("state")
    err = qs.get("error")

    if err:
        # Strava can return access_denied if user cancels
        return {"statusCode": 302, "headers": {"Location": f"{FRONTEND}/?connected=0&error={err}"}, "body": ""}

    if not code or not state:
        return {"statusCode": 400, "body": "missing code/state"}

    # Validate state from database (fallback to cookie for backwards compatibility)
    state_valid = False
    
    # First try database validation
    try:
        sql = "SELECT expires_at FROM oauth_states WHERE state = :state"
        params = [{"name": "state", "value": {"stringValue": state}}]
        result = _exec_sql(sql, params)
        
        if result.get("records"):
            expires_at = result["records"][0][0].get("longValue")
            current_time = int(time.time())
            
            if expires_at and expires_at > current_time:
                state_valid = True
        
        # Clean up state (used or expired) after validation check
        try:
            delete_sql = "DELETE FROM oauth_states WHERE state = :state"
            _exec_sql(delete_sql, params)
        except Exception as cleanup_error:
            # Log cleanup failure but don't fail the request
            print(f"Warning: Failed to cleanup OAuth state: {cleanup_error}")
    except Exception as e:
        # If database validation fails, fall back to cookie validation
        print(f"Database state validation failed, falling back to cookie: {e}")
        cookies = _parse_cookies(event)
        if cookies.get("rm_state") == state:
            state_valid = True
    
    if not state_valid:
        return {"statusCode": 400, "body": "invalid state"}

    # Exchange code for tokens
    client_id, client_secret = _get_strava_creds()
    redirect_uri = f"{API_BASE}/auth/callback"

    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            # Strava does not require redirect_uri for token exchange, but harmless if included
            "redirect_uri": redirect_uri,
        }
    ).encode()

    req = Request(STRAVA_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            token_resp = json.loads(resp.read().decode())
    except Exception as e:
        return {"statusCode": 500, "body": f"token exchange failed: {e}"}

    access_token = token_resp.get("access_token")
    refresh_token = token_resp.get("refresh_token")
    expires_at = int(token_resp.get("expires_at") or 0)
    athlete = token_resp.get("athlete") or {}
    athlete_id = athlete.get("id")

    if not access_token or not refresh_token or not athlete_id:
        return {"statusCode": 500, "body": f"unexpected token response: {json.dumps(token_resp)[:500]}"}

    athlete_id = int(athlete_id)
    display_name = (athlete.get("firstname") or "").strip()
    if athlete.get("lastname"):
        display_name = (display_name + " " + str(athlete.get("lastname")).strip()).strip()
    
    # Get profile picture URL (Strava provides 'profile' or 'profile_medium')
    # Use None instead of empty string for better database handling
    profile_picture = athlete.get("profile_medium") or athlete.get("profile") or None

    # Upsert user row (Data API)
    sql = """
    INSERT INTO users (athlete_id, display_name, profile_picture, access_token, refresh_token, expires_at, updated_at)
    VALUES (:aid, :dname, :pic, :at, :rt, :exp, now())
    ON CONFLICT (athlete_id) DO UPDATE
      SET display_name = EXCLUDED.display_name,
          profile_picture = EXCLUDED.profile_picture,
          access_token = EXCLUDED.access_token,
          refresh_token = EXCLUDED.refresh_token,
          expires_at = EXCLUDED.expires_at,
          updated_at = now();
    """
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "dname", "value": {"stringValue": display_name}},
    ]
    
    # Only add profile_picture parameter if it's not None
    if profile_picture:
        params.append({"name": "pic", "value": {"stringValue": profile_picture}})
    else:
        params.append({"name": "pic", "value": {"isNull": True}})
    
    params.extend([
        {"name": "at", "value": {"stringValue": access_token}},
        {"name": "rt", "value": {"stringValue": refresh_token}},
        {"name": "exp", "value": {"longValue": expires_at}},
    ])
    _exec_sql(sql, params)
    print(f"Successfully upserted user {athlete_id} ({display_name}) to database")

    # Create session cookie
    session_token = _make_session_token(athlete_id)
    max_age = 30 * 24 * 3600
    print(f"Created session token for athlete_id: {athlete_id}")

    set_cookie = f"rm_session={session_token}; HttpOnly; Secure; SameSite=Lax; Path={COOKIE_PATH}; Max-Age={max_age}"
    clear_state = f"rm_state=; HttpOnly; Secure; SameSite=Lax; Path={COOKIE_PATH}; Max-Age=0"

    # Redirect back to SPA - use /connect page to show success message
    redirect_to = f"{FRONTEND}/connect?connected=1"

    return {
        "statusCode": 302,
        "headers": {
            "Location": redirect_to,
            "Set-Cookie": set_cookie,
        },
        # Multi cookies: HTTP API supports "cookies" array. Safer than multiple Set-Cookie headers.
        "cookies": [set_cookie, clear_state],
        "body": "",
    }
