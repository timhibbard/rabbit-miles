# lambda_me.py
import os, json, base64, hmac, hashlib, sys
from urllib.parse import urlparse
import boto3

# Add parent directory to path to import admin_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import admin_utils

rds = boto3.client("rds-data")
# Get environment variables safely - validation happens in handler
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

def get_cors_origin():
    """Extract origin (scheme + host) from FRONTEND_URL for CORS headers"""
    if not FRONTEND_URL:
        return None
    parsed = urlparse(FRONTEND_URL)
    # Origin only includes scheme + netloc (no path)
    # Validate that both scheme and netloc are present
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"

def get_cors_headers():
    """Return CORS headers for cross-origin requests"""
    headers = {
        "Content-Type": "application/json",
    }
    origin = get_cors_origin()
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers

def verify_session_token(tok):
    try:
        b, sig = tok.rsplit(".", 1)
        expected = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode())
        if data.get("exp", 0) < __import__("time").time():
            return None
        return int(data.get("aid"))
    except Exception:
        return None

def check_authorization_header(headers):
    """Check if Authorization header is present and log warning (cookie-based auth only)"""
    auth_header = headers.get("authorization") or headers.get("Authorization")
    if auth_header:
        # Log that an Authorization header was received but will be ignored
        print("Warning: Authorization header detected but ignored (cookie-based auth only)")

def parse_session_token(event):
    """Parse session token from cookies only (cookie-based authentication)"""
    return parse_session_cookie(event)

def parse_session_cookie(event):
    headers = event.get("headers") or {}

    cookies_array = event.get("cookies") or []
    cookie_header = headers.get("cookie") or headers.get("Cookie")

    for cookie_str in cookies_array:
        if not cookie_str or "=" not in cookie_str:
            continue
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v

    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v
    return None

def exec_sql(sql, parameters=None):
    kwargs = dict(resourceArn=DB_CLUSTER_ARN, secretArn=DB_SECRET_ARN, sql=sql, database=DB_NAME)
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)

def extract_cookie_names(cookie_string):
    """Extract cookie names from a cookie string"""
    cookie_names = []
    if not cookie_string:
        return cookie_names
    for part in cookie_string.split(";"):
        if "=" in part:
            cookie_name = part.split("=")[0].strip()
            cookie_names.append(cookie_name)
    return cookie_names

def handler(event, context):
    print("=" * 80)
    print("/ME LAMBDA - START")
    print("=" * 80)
    
    cors_headers = get_cors_headers()
    print(f"LOG - CORS headers configured: {cors_headers}")
    
    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        print(f"LOG - OPTIONS preflight request detected")
        print(f"LOG - Returning CORS preflight response")
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Cookie, Authorization",
                "Access-Control-Max-Age": "86400"
            },
            "body": ""
        }
    
    try:
        print(f"LOG - Validating environment variables")
        # Validate required environment variables
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN environment variable")
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        if not APP_SECRET:
            print("ERROR - Missing APP_SECRET environment variable")
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        print(f"LOG - Environment variables OK")
        print(f"LOG -   DB_CLUSTER_ARN: {DB_CLUSTER_ARN[:50]}...")
        print(f"LOG -   DB_SECRET_ARN: {DB_SECRET_ARN[:50]}...")
        print(f"LOG -   DB_NAME: {DB_NAME}")
        print(f"LOG -   APP_SECRET length: {len(APP_SECRET)} bytes")
        print(f"LOG -   FRONTEND_URL: {FRONTEND_URL}")
        
        # Debug: Log request context for better diagnostics
        request_context = event.get("requestContext", {})
        http_context = request_context.get("http", {})
        print(f"LOG - Request method: {http_context.get('method', 'UNKNOWN')}")
        print(f"LOG - Request path: {http_context.get('path', 'UNKNOWN')}")
        print(f"LOG - Source IP: {http_context.get('sourceIp', 'UNKNOWN')}")
        
        # Debug: Log cookie information (sanitized for security)
        headers = event.get("headers") or {}
        print(f"LOG - Analyzing request headers")
        print(f"LOG - Number of headers: {len(headers)}")
        print(f"LOG - Header keys: {list(headers.keys())}")
        
        cookies_array = event.get("cookies") or []
        cookie_header = headers.get("cookie") or headers.get("Cookie")
        origin_header = headers.get("origin") or headers.get("Origin") or ""
        referer_header = headers.get("referer") or headers.get("Referer") or ""
        host_header = headers.get("host") or headers.get("Host") or ""
        sec_fetch_site = headers.get("sec-fetch-site") or headers.get("Sec-Fetch-Site") or ""
        sec_fetch_mode = headers.get("sec-fetch-mode") or headers.get("Sec-Fetch-Mode") or ""
        sec_fetch_dest = headers.get("sec-fetch-dest") or headers.get("Sec-Fetch-Dest") or ""
        sec_fetch_storage = headers.get("sec-fetch-storage-access") or headers.get("Sec-Fetch-Storage-Access") or ""
        
        # Log presence of cookies without exposing values
        print(f"LOG - Cookie analysis:")
        print(f"LOG -   Cookies array present: {len(cookies_array) > 0}, count: {len(cookies_array)}")
        print(f"LOG -   Cookie header present: {cookie_header is not None}")
        if cookie_header:
            print(f"LOG -   Cookie header length: {len(cookie_header)} chars")
        print(f"LOG - Request context:")
        print(f"LOG -   Origin: {origin_header}")
        print(f"LOG -   Referer: {referer_header}")
        print(f"LOG -   Host: {host_header}")
        print(f"LOG -   Sec-Fetch-Site: {sec_fetch_site}")
        print(f"LOG -   Sec-Fetch-Mode: {sec_fetch_mode}")
        print(f"LOG -   Sec-Fetch-Dest: {sec_fetch_dest}")
        print(f"LOG -   Sec-Fetch-Storage-Access: {sec_fetch_storage}")
        print(f"LOG -   Expected cookie domain: API Gateway domain (cross-site from {origin_header})")
        print(f"LOG -   CORS origin configured: {get_cors_origin()}")
        
        if cookies_array:
            # Log cookie names only, not values
            print(f"LOG - Parsing cookies array:")
            all_cookie_names = []
            for idx, cookie_str in enumerate(cookies_array):
                if cookie_str:
                    cookie_names = extract_cookie_names(cookie_str)
                    all_cookie_names.extend(cookie_names)
                    print(f"LOG -   Array[{idx}]: {cookie_names}")
            print(f"LOG - All cookie names from array: {all_cookie_names}")
        
        if cookie_header:
            cookie_names = extract_cookie_names(cookie_header)
            print(f"LOG - Cookie names from header: {cookie_names}")
            # Parse and log each cookie (name and length only for security)
            for part in cookie_header.split(";"):
                part = part.strip()
                if "=" in part:
                    name, value = part.split("=", 1)
                    print(f"LOG -   Cookie '{name}': length={len(value)} chars")
        
        # Log additional browser context that may affect cookies
        user_agent = headers.get("user-agent") or headers.get("User-Agent") or ""
        if user_agent:
            print(f"LOG - User-Agent: {user_agent}")
            # Log browser type (Chrome, Safari, Firefox, etc.) for cookie compatibility debugging
            # Check in order: Edge, Chrome, Safari (since Chrome includes Safari in UA string)
            browser_type = "unknown"
            if "Edg" in user_agent:
                browser_type = "Edge"
            elif "Chrome" in user_agent:
                browser_type = "Chrome"
            elif "Safari" in user_agent:
                browser_type = "Safari"
            elif "Firefox" in user_agent:
                browser_type = "Firefox"
            print(f"LOG - Browser type detected: {browser_type}")
        
        # Check for Authorization header (should not be present)
        check_authorization_header(headers)
        
        print(f"LOG - Parsing session token from cookies")
        tok = parse_session_token(event)
        if tok:
            print(f"LOG - Session token found!")
            print(f"LOG -   Token length: {len(tok)} chars")
        else:
            print(f"LOG - No session token found in request")
        
        if not tok:
            print(f"ERROR - No session cookie found - authentication required")
            print(f"LOG - Troubleshooting info:")
            print(f"LOG -   1. Check if cookie was set during /auth/callback")
            print(f"LOG -   2. Check browser cookie storage (DevTools > Application > Cookies)")
            print(f"LOG -   3. Verify cookie domain matches API Gateway domain")
            print(f"LOG -   4. Check if third-party cookies are blocked in browser")
            print(f"LOG -   5. Verify withCredentials=true in frontend request")
            print(f"LOG - Full event keys: {list(event.keys())}")
            # Log header keys only, not values (avoid exposing sensitive data)
            print(f"LOG - Header keys: {list(headers.keys()) if headers else 'none'}")
            print("=" * 80)
            print("/ME LAMBDA - FAILED (No Cookie)")
            print("=" * 80)
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        print(f"LOG - Verifying session token signature")
        aid = verify_session_token(tok)
        if not aid:
            print("ERROR - Session token verification FAILED")
            print(f"LOG - Token was present but signature/expiration check failed")
            print(f"LOG - Possible causes:")
            print(f"LOG -   1. APP_SECRET mismatch between callback and me Lambda")
            print(f"LOG -   2. Token has expired")
            print(f"LOG -   3. Token was tampered with")
            print("=" * 80)
            print("/ME LAMBDA - FAILED (Invalid Token)")
            print("=" * 80)
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        print(f"LOG - Session token verification SUCCESS")
        print(f"LOG - Verified athlete_id: {aid}")

        print(f"LOG - Querying database for user data")
        sql = "SELECT athlete_id, display_name, profile_picture, show_on_leaderboards, timezone FROM users WHERE athlete_id = :aid LIMIT 1"
        res = exec_sql(sql, parameters=[{"name":"aid","value":{"longValue":aid}}])
        records = res.get("records") or []
        print(f"LOG - Database query returned {len(records)} records")
        
        if not records:
            print(f"ERROR - User not found in database for athlete_id: {aid}")
            print(f"LOG - User may have been deleted or never created")
            print("=" * 80)
            print("/ME LAMBDA - FAILED (User Not Found)")
            print("=" * 80)
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "user not found"})
            }
        
        print(f"LOG - User found in database!")
        rec = records[0]
        # records format: list of field lists, where each field has stringValue/longValue etc
        athlete_id = int(rec[0].get("longValue") or rec[0].get("stringValue"))
        display_name = rec[1].get("stringValue") if rec[1].get("stringValue") else ""
        # Handle profile_picture which may be NULL in database
        profile_picture = ""
        if len(rec) > 2 and rec[2]:
            profile_picture = rec[2].get("stringValue", "")
        # Handle show_on_leaderboards (default to True if NULL)
        show_on_leaderboards = True
        if len(rec) > 3 and rec[3]:
            show_on_leaderboards = rec[3].get("booleanValue", True)
        # Handle timezone which may be NULL
        timezone = None
        if len(rec) > 4 and rec[4]:
            timezone = rec[4].get("stringValue")
        
        print(f"LOG - User data:")
        print(f"LOG -   athlete_id: {athlete_id}")
        print(f"LOG -   display_name: {display_name}")
        print(f"LOG -   profile_picture: {bool(profile_picture)}")
        print(f"LOG -   show_on_leaderboards: {show_on_leaderboards}")
        print(f"LOG -   timezone: {timezone}")
        
        # Check if user is an admin
        is_user_admin = admin_utils.is_admin(athlete_id)
        print(f"LOG -   is_admin: {is_user_admin}")
        
        response_data = {
            "athlete_id": athlete_id,
            "display_name": display_name,
            "profile_picture": profile_picture,
            "is_admin": is_user_admin,
            "show_on_leaderboards": show_on_leaderboards,
            "timezone": timezone
        }
        
        print(f"LOG - Returning success response")
        print("=" * 80)
        print("/ME LAMBDA - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(response_data)
        }
    except Exception as e:
        # Catch any unexpected errors and return proper error with CORS headers
        print(f"CRITICAL ERROR - Unexpected exception in /me handler")
        print(f"ERROR - Exception type: {type(e).__name__}")
        print(f"ERROR - Exception message: {str(e)}")
        import traceback
        print(f"ERROR - Stack trace:")
        traceback.print_exc()
        print("=" * 80)
        print("/ME LAMBDA - FAILED (Exception)")
        print("=" * 80)
        # Return generic error to client, full details are in CloudWatch logs
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
