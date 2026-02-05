# rabbitmiles-auth-disconnect
# Handler: lambda_function.handler
# Method: GET (user navigates to this endpoint, it clears session and redirects)
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# API_BASE_URL (e.g. https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod)
# FRONTEND_URL (e.g. https://<you>.github.io/rabbitmiles)
# APP_SECRET (same secret used by auth callback / me)

import os
import json
import base64
import hmac
import hashlib
import html
from urllib.parse import urlparse
import boto3

rds = boto3.client("rds-data")

# Get environment variables safely - validation happens in handler
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
API_BASE = os.environ.get("API_BASE_URL", "").rstrip("/")
FRONTEND = os.environ.get("FRONTEND_URL", "").rstrip("/")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""

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


def _verify_session_token(tok: str):
    try:
        b, sig = tok.rsplit(".", 1)
        expected = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload_json = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        data = json.loads(payload_json)
        # check expiration
        if data.get("exp", 0) < int(__import__("time").time()):
            return None
        return int(data.get("aid"))
    except Exception:
        return None


def _exec_sql(sql: str, parameters: list = None):
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def handler(event, context):
    print("=" * 80)
    print("AUTH DISCONNECT LAMBDA - START")
    print("=" * 80)
    
    try:
        # Validate required environment variables
        print(f"LOG - Validating environment variables")
        if not FRONTEND:
            print("ERROR - Missing FRONTEND_URL environment variable")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Internal Server Error"})
            }
        
        if not API_BASE:
            print("ERROR - Missing API_BASE_URL environment variable")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Internal Server Error"})
            }
        
        if not APP_SECRET:
            print("ERROR - Missing APP_SECRET environment variable")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Internal Server Error"})
            }
        
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN environment variable")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Internal Server Error"})
            }
        
        print(f"LOG - Environment variables validated successfully")
        print(f"LOG - Environment configuration:")
        print(f"LOG -   FRONTEND_URL: {FRONTEND}")
        print(f"LOG -   API_BASE_URL: {API_BASE}")
        print(f"LOG -   APP_SECRET length: {len(APP_SECRET)} bytes")
        if len(DB_CLUSTER_ARN) > 50:
            print(f"LOG -   DB_CLUSTER_ARN: {DB_CLUSTER_ARN[:50]}...")
        else:
            print(f"LOG -   DB_CLUSTER_ARN: {DB_CLUSTER_ARN}")
        if len(DB_SECRET_ARN) > 50:
            print(f"LOG -   DB_SECRET_ARN: {DB_SECRET_ARN[:50]}...")
        else:
            print(f"LOG -   DB_SECRET_ARN: {DB_SECRET_ARN}")
        
        if API_BASE_PATH:
            print(f"LOG - API_BASE_URL path detected: {API_BASE_PATH}")
        print(f"LOG - Cookie path configured as: {COOKIE_PATH}")
        
        # Log request context
        request_context = event.get("requestContext", {})
        http_context = request_context.get("http", {})
        print(f"LOG - Request method: {http_context.get('method', 'UNKNOWN')}")
        print(f"LOG - Request path: {http_context.get('path', 'UNKNOWN')}")
        print(f"LOG - Source IP: {http_context.get('sourceIp', 'UNKNOWN')}")
        
        headers = event.get("headers") or {}
        user_agent = headers.get("user-agent") or headers.get("User-Agent") or ""
        if user_agent:
            print(f"LOG - User-Agent: {user_agent}")
        
        print(f"LOG - Parsing cookies from request")
        cookies = _parse_cookies(event)
        print(f"LOG - Cookies found: {list(cookies.keys())}")
        session = cookies.get("rm_session")
        
        if not session:
            print(f"LOG - No session cookie found in request")
            # still clear cookie and redirect
            # SameSite=None is required for cross-site cookies (GitHub Pages + API Gateway)
            # Partitioned attribute removed for better browser compatibility
            clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
            print("LOG - Clearing any existing session cookie and redirecting to frontend")
            
            redirect_to = f"{FRONTEND}/?connected=0"
            redirect_to_escaped = html.escape(redirect_to, quote=True)
            
            print(f"LOG - Redirect destination: {redirect_to}")
            print("=" * 80)
            print("AUTH DISCONNECT LAMBDA - SUCCESS (No Session)")
            print("=" * 80)
            
            html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Disconnecting from Strava...</title>
    <meta http-equiv="refresh" content="1;url={redirect_to_escaped}">
</head>
<body>
    <p>Redirecting...</p>
    <script>setTimeout(function() {{ window.location.href = {json.dumps(redirect_to)}; }}, 1000);</script>
</body>
</html>"""
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8",
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                },
                "cookies": [clear],
                "body": html_body,
            }

        aid = _verify_session_token(session)
        if not aid:
            print(f"LOG - Session token present but verification FAILED")
            # invalid session: clear cookie
            # SameSite=None is required for cross-site cookies (GitHub Pages + API Gateway)
            # Partitioned attribute removed for better browser compatibility
            clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
            print("LOG - Invalid session token, clearing and redirecting")
            
            redirect_to = f"{FRONTEND}/?connected=0"
            redirect_to_escaped = html.escape(redirect_to, quote=True)
            
            print(f"LOG - Redirect destination: {redirect_to}")
            print("=" * 80)
            print("AUTH DISCONNECT LAMBDA - SUCCESS (Invalid Session)")
            print("=" * 80)
            
            html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Disconnecting from Strava...</title>
    <meta http-equiv="refresh" content="1;url={redirect_to_escaped}">
</head>
<body>
    <p>Redirecting...</p>
    <script>setTimeout(function() {{ window.location.href = {json.dumps(redirect_to)}; }}, 1000);</script>
</body>
</html>"""
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8",
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                },
                "cookies": [clear],
                "body": html_body,
            }

        # Remove sensitive tokens from the users row but keep the account (so we don't lose preferences)
        print(f"LOG - Session token verified for athlete_id: {aid}")
        print(f"LOG - Clearing Strava tokens from database")
        sql = """
        UPDATE users
        SET access_token = NULL,
            refresh_token = NULL,
            expires_at = NULL,
            updated_at = now()
        WHERE athlete_id = :aid
        """
        params = [{"name": "aid", "value": {"longValue": aid}}]
        try:
            _exec_sql(sql, params)
            print(f"LOG - Successfully cleared tokens for athlete_id: {aid}")
        except Exception as e:
            # best-effort: clear cookie and redirect even on DB failures, but surface minimal error
            # Log generic error to avoid exposing sensitive database details
            print(f"ERROR - Failed to clear tokens in database: {e}")
            print(f"LOG - Proceeding with cookie clear and redirect despite DB error")
            # SameSite=None is required for cross-site cookies (GitHub Pages + API Gateway)
            # Partitioned attribute removed for better browser compatibility
            clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
            
            redirect_to = f"{FRONTEND}/?connected=0&error=disconnect_failed"
            redirect_to_escaped = html.escape(redirect_to, quote=True)
            
            print(f"LOG - Redirect destination: {redirect_to}")
            print("=" * 80)
            print("AUTH DISCONNECT LAMBDA - PARTIAL SUCCESS (DB Error)")
            print("=" * 80)
            
            html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Disconnecting from Strava...</title>
    <meta http-equiv="refresh" content="1;url={redirect_to_escaped}">
</head>
<body>
    <p>Redirecting...</p>
    <script>setTimeout(function() {{ window.location.href = {json.dumps(redirect_to)}; }}, 1000);</script>
</body>
</html>"""
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8",
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                },
                "cookies": [clear],
                "body": html_body,
            }
    
        # Clear session cookie and redirect to frontend
        # SameSite=None is required for cross-site cookies (GitHub Pages + API Gateway)
        # Partitioned attribute removed for better browser compatibility
        clear_session = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
        # also clear any leftover rm_state just in case
        clear_state = f"rm_state=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
        print(f"LOG - Clearing session cookies and redirecting to frontend for athlete_id: {aid}")
    
        redirect_to = f"{FRONTEND}/?connected=0"
        print(f"LOG - Redirect destination: {redirect_to}")
        
        # Return HTML page instead of 302 redirect to ensure cookies are cleared before redirect
        # This works around browser issues with cookies in cross-site 302 redirects
        redirect_to_escaped = html.escape(redirect_to, quote=True)
        
        print("=" * 80)
        print("AUTH DISCONNECT LAMBDA - SUCCESS")
        print("=" * 80)
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Disconnecting from Strava...</title>
    <meta http-equiv="refresh" content="1;url={redirect_to_escaped}">
    <style>
        body {{ font-family: system-ui, sans-serif; text-align: center; padding-top: 100px; }}
        .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #ea580c; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="spinner"></div>
    <h2>Successfully disconnected from Strava</h2>
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
    
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store, no-cache, must-revalidate",
            },
            "cookies": [clear_session, clear_state],
            "body": html_body,
        }
    except Exception as e:
        # Catch any unexpected errors and return proper error response
        print(f"CRITICAL ERROR - Unexpected exception in disconnect handler")
        print(f"ERROR - Exception type: {type(e).__name__}")
        print(f"ERROR - Exception message: {str(e)}")
        import traceback
        print(f"ERROR - Stack trace:")
        traceback.print_exc()
        print("=" * 80)
        print("AUTH DISCONNECT LAMBDA - FAILED (Exception)")
        print("=" * 80)
        # Return generic error to client, full details are in CloudWatch logs
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Internal Server Error"})
        }
