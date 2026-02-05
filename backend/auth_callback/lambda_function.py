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
# Use a root path to avoid path mismatches across stages.
_parsed_api_base = urlparse(API_BASE) if API_BASE else None
API_BASE_PATH = _parsed_api_base.path if _parsed_api_base and _parsed_api_base.path else ""
COOKIE_PATH = "/"


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
    print("=" * 80)
    print("AUTH CALLBACK LAMBDA - START")
    print("=" * 80)
    
    # Log full event structure (sanitized)
    print(f"LOG - Event keys: {list(event.keys())}")
    print(f"LOG - Request context: {event.get('requestContext', {}).get('http', {})}")
    
    qs = event.get("queryStringParameters") or {}
    code = qs.get("code")
    state = qs.get("state")
    err = qs.get("error")
    
    print(f"LOG - Query string parameters: code={bool(code)}, state={bool(state)}, error={err}")
    if code:
        print(f"LOG - OAuth code present: {code[:10]}...{code[-10:]} (length: {len(code)})")
    if state:
        print(f"LOG - OAuth state present: {state[:10]}...{state[-10:]} (length: {len(state)})")
    
    if API_BASE_PATH:
        print(f"LOG - API_BASE_URL path detected: {API_BASE_PATH}")
    print(f"LOG - Cookie path configured as: {COOKIE_PATH}")
    print(f"LOG - FRONTEND URL: {FRONTEND}")
    print(f"LOG - API_BASE URL: {API_BASE}")
    
    # Log request headers for debugging
    headers = event.get("headers") or {}
    print(f"LOG - Number of headers: {len(headers)}")
    print(f"LOG - Header keys: {list(headers.keys())}")
    
    user_agent = headers.get("user-agent") or headers.get("User-Agent") or ""
    if user_agent:
        print(f"LOG - User-Agent: {user_agent}")
    
    referer = headers.get("referer") or headers.get("Referer") or ""
    if referer:
        print(f"LOG - Referer: {referer}")
    
    origin = headers.get("origin") or headers.get("Origin") or ""
    if origin:
        print(f"LOG - Origin: {origin}")
    
    # Log cookies in request (if any)
    cookies_array = event.get("cookies") or []
    cookie_header = headers.get("cookie") or headers.get("Cookie")
    print(f"LOG - Request has cookies array: {len(cookies_array) > 0} (count: {len(cookies_array)})")
    print(f"LOG - Request has cookie header: {bool(cookie_header)}")

    if not code or not state:
        print(f"ERROR - Missing required parameters: code={bool(code)}, state={bool(state)}")
        return {"statusCode": 400, "body": "missing code/state"}

    # Validate state from database (fallback to cookie for backwards compatibility)
    state_valid = False
    
    print(f"LOG - Starting state validation")
    # First try database validation
    try:
        print(f"LOG - Attempting database state validation")
        sql = "SELECT expires_at FROM oauth_states WHERE state = :state"
        params = [{"name": "state", "value": {"stringValue": state}}]
        result = _exec_sql(sql, params)
        
        print(f"LOG - Database query result: {result.get('numberOfRecordsUpdated', 0)} records")
        if result.get("records"):
            expires_at = result["records"][0][0].get("longValue")
            current_time = int(time.time())
            print(f"LOG - State expires_at: {expires_at}, current_time: {current_time}")
            
            if expires_at and expires_at > current_time:
                state_valid = True
                print(f"LOG - State validation SUCCESS via database")
            else:
                print(f"LOG - State expired or invalid")
        else:
            print(f"LOG - State not found in database")
        
        # Clean up state (used or expired) after validation check
        try:
            print(f"LOG - Cleaning up OAuth state from database")
            delete_sql = "DELETE FROM oauth_states WHERE state = :state"
            _exec_sql(delete_sql, params)
            print(f"LOG - OAuth state cleanup successful")
        except Exception as cleanup_error:
            # Log cleanup failure but don't fail the request
            print(f"WARNING - Failed to cleanup OAuth state: {cleanup_error}")
    except Exception as e:
        # If database validation fails, fall back to cookie validation
        print(f"LOG - Database state validation failed: {e}")
        print(f"LOG - Falling back to cookie validation")
        cookies = _parse_cookies(event)
        print(f"LOG - Parsed cookies: {list(cookies.keys())}")
        if cookies.get("rm_state") == state:
            state_valid = True
            print(f"LOG - State validation SUCCESS via cookie")
        else:
            print(f"LOG - State validation FAILED - cookie mismatch")
    
    if not state_valid:
        print(f"ERROR - State validation FAILED - rejecting request")
        return {"statusCode": 400, "body": "invalid state"}

    # Exchange code for tokens
    print(f"LOG - Getting Strava credentials")
    client_id, client_secret = _get_strava_creds()
    print(f"LOG - Strava client_id length: {len(client_id)} chars")
    print(f"LOG - Strava client_secret length: {len(client_secret)} chars")
    
    # CRITICAL: redirect_uri must EXACTLY match the one used in auth_start
    # auth_start uses {FRONTEND_URL}/callback, so we must use the same here
    redirect_uri = f"{FRONTEND}/callback"
    print(f"LOG - OAuth redirect_uri: {redirect_uri}")

    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            # OAuth 2.0 spec requires redirect_uri to match the authorization request
            "redirect_uri": redirect_uri,
        }
    ).encode()

    print(f"LOG - Exchanging OAuth code for tokens with Strava")
    print(f"LOG - Strava token URL: {STRAVA_TOKEN_URL}")
    req = Request(STRAVA_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            print(f"LOG - Strava response status: {resp.status}")
            token_resp = json.loads(resp.read().decode())
            print(f"LOG - Strava response keys: {list(token_resp.keys())}")
    except Exception as e:
        print(f"ERROR - Token exchange failed: {e}")
        return {"statusCode": 500, "body": f"token exchange failed: {e}"}

    access_token = token_resp.get("access_token")
    refresh_token = token_resp.get("refresh_token")
    expires_at = int(token_resp.get("expires_at") or 0)
    athlete = token_resp.get("athlete") or {}
    athlete_id = athlete.get("id")

    print(f"LOG - Extracted from Strava response:")
    print(f"LOG -   access_token: {bool(access_token)} (length: {len(access_token) if access_token else 0})")
    print(f"LOG -   refresh_token: {bool(refresh_token)} (length: {len(refresh_token) if refresh_token else 0})")
    print(f"LOG -   expires_at: {expires_at}")
    print(f"LOG -   athlete_id: {athlete_id}")
    print(f"LOG -   athlete keys: {list(athlete.keys())}")

    if not access_token or not refresh_token or not athlete_id:
        print(f"ERROR - Missing required fields in token response")
        return {"statusCode": 500, "body": f"unexpected token response: {json.dumps(token_resp)[:500]}"}

    athlete_id = int(athlete_id)
    display_name = (athlete.get("firstname") or "").strip()
    if athlete.get("lastname"):
        display_name = (display_name + " " + str(athlete.get("lastname")).strip()).strip()
    
    # Get profile picture URL (Strava provides 'profile' or 'profile_medium')
    # Use None instead of empty string for better database handling
    profile_picture = athlete.get("profile_medium") or athlete.get("profile") or None
    
    print(f"LOG - Processed athlete data:")
    print(f"LOG -   athlete_id: {athlete_id}")
    print(f"LOG -   display_name: {display_name}")
    print(f"LOG -   profile_picture: {bool(profile_picture)}")

    # Upsert user row (Data API)
    print(f"LOG - Upserting user to database")
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
        print(f"LOG - Including profile picture in database")
    else:
        params.append({"name": "pic", "value": {"isNull": True}})
        print(f"LOG - Profile picture is NULL")
    
    params.extend([
        {"name": "at", "value": {"stringValue": access_token}},
        {"name": "rt", "value": {"stringValue": refresh_token}},
        {"name": "exp", "value": {"longValue": expires_at}},
    ])
    
    print(f"LOG - Executing database upsert for athlete_id: {athlete_id}")
    _exec_sql(sql, params)
    print(f"LOG - Database upsert SUCCESS for user {athlete_id} ({display_name})")

    # Create session cookie
    print(f"LOG - Creating session token for athlete_id: {athlete_id}")
    session_token = _make_session_token(athlete_id)
    max_age = 30 * 24 * 3600
    print(f"LOG - Session token created successfully")
    print(f"LOG -   Token length: {len(session_token)} characters")

    # SameSite=None is required for cross-site cookies (GitHub Pages + API Gateway)
    # Partitioned attribute removed for better browser compatibility
    set_cookie = f"rm_session={session_token}; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age={max_age}"
    clear_state = f"rm_state=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
    
    print(f"LOG - Cookie configuration:")
    print(f"LOG -   Name: rm_session")
    print(f"LOG -   Value length: {len(session_token)} chars")
    print(f"LOG -   HttpOnly: Yes (JavaScript cannot access)")
    print(f"LOG -   Secure: Yes (HTTPS only)")
    print(f"LOG -   SameSite: None (cross-site allowed)")
    print(f"LOG -   Partitioned: No (removed for compatibility)")
    print(f"LOG -   Path: {COOKIE_PATH}")
    print(f"LOG -   Max-Age: {max_age} seconds ({max_age // 86400} days)")
    print(f"LOG - Set-Cookie header length: {len(set_cookie)} chars")

    # Redirect back to SPA with connected=1 query parameter
    redirect_to = f"{FRONTEND}/connect?connected=1"

    print(f"LOG - Preparing response:")
    print(f"LOG -   Status: 200 OK (HTML page with meta refresh)")
    print(f"LOG -   Content-Type: text/html; charset=utf-8")
    print(f"LOG -   Redirect destination: {redirect_to}")
    print(f"LOG -   Number of cookies to set: 2 (rm_session, rm_state clear)")
    print(f"LOG - Using HTML page instead of 302 redirect to ensure cookies are stored")
    
    # Escape the redirect URL for safe inclusion in HTML/JavaScript
    import html
    redirect_to_escaped = html.escape(redirect_to, quote=True)

    # Return HTML page instead of 302 redirect to ensure cookies are set before redirect
    # This works around browser issues with cookies in cross-site 302 redirects
    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Connecting to Strava...</title>
    <meta http-equiv="refresh" content="1;url={redirect_to_escaped}">
    <style>
        body {{ font-family: system-ui, sans-serif; text-align: center; padding-top: 100px; }}
        .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #ea580c; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="spinner"></div>
    <h2>Successfully connected to Strava!</h2>
    <p>Redirecting you back to RabbitMiles...</p>
    <p><small>If you are not redirected, <a href="{redirect_to_escaped}">click here</a>.</small></p>
    <script>
        // Fallback redirect via JavaScript after 1 second
        setTimeout(function() {{
            window.location.href = {json.dumps(redirect_to)};
        }}, 1000);
    </script>
</body>
</html>"""

    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
        # Multi cookies: HTTP API v2 uses "cookies" array for setting multiple cookies
        # Do not use Set-Cookie header with cookies array to avoid conflicts
        "cookies": [set_cookie, clear_state],
        "body": html_body,
    }
    
    print(f"LOG - Response object created:")
    print(f"LOG -   Response keys: {list(response.keys())}")
    print(f"LOG -   Headers: {response['headers']}")
    print(f"LOG -   Cookies array length: {len(response['cookies'])}")
    print(f"LOG -   Body length: {len(response['body'])} chars")
    print("=" * 80)
    print("AUTH CALLBACK LAMBDA - SUCCESS")
    print("=" * 80)
    
    return response
