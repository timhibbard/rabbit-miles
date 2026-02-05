# lambda_me.py
import os, json, base64, hmac, hashlib
from urllib.parse import urlparse
import boto3

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
    cors_headers = get_cors_headers()
    
    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
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
        # Validate required environment variables
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN environment variable")
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        if not APP_SECRET:
            print("ERROR: Missing APP_SECRET environment variable")
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        # Debug: Log request context for better diagnostics
        request_context = event.get("requestContext", {})
        http_context = request_context.get("http", {})
        print(f"Debug - Request method: {http_context.get('method', 'UNKNOWN')}")
        print(f"Debug - Request path: {http_context.get('path', 'UNKNOWN')}")
        print(f"Debug - Source IP: {http_context.get('sourceIp', 'UNKNOWN')}")
        
        # Debug: Log cookie information (sanitized for security)
        headers = event.get("headers") or {}
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
        print(f"Debug - cookies array present: {len(cookies_array) > 0}, count: {len(cookies_array)}")
        print(f"Debug - cookie header present: {cookie_header is not None}")
        if cookie_header:
            print(f"Debug - cookie header length: {len(cookie_header)}")
        print(f"Debug - Origin: {origin_header}")
        print(f"Debug - Referer: {referer_header}")
        print(f"Debug - Host: {host_header}")
        print(f"Debug - Sec-Fetch-Site: {sec_fetch_site}")
        print(f"Debug - Sec-Fetch-Mode: {sec_fetch_mode}")
        print(f"Debug - Sec-Fetch-Dest: {sec_fetch_dest}")
        print(f"Debug - Sec-Fetch-Storage-Access: {sec_fetch_storage}")
        if cookies_array:
            # Log cookie names only, not values
            all_cookie_names = []
            for cookie_str in cookies_array:
                if cookie_str:
                    all_cookie_names.extend(extract_cookie_names(cookie_str))
            print(f"Debug - cookie names in array: {', '.join(all_cookie_names) if all_cookie_names else 'none'}")
        if cookie_header:
            cookie_names = extract_cookie_names(cookie_header)
            print(f"Debug - cookie names in header: {', '.join(cookie_names) if cookie_names else 'none'}")
        
        # Log additional browser context that may affect cookies
        user_agent = headers.get("user-agent") or headers.get("User-Agent") or ""
        if user_agent:
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
            print(f"Debug - Browser type: {browser_type}")
        
        # Check for Authorization header (should not be present)
        check_authorization_header(headers)
        
        tok = parse_session_token(event)
        if tok:
            print("Found session token")
        
        if not tok:
            print(f"No session cookie found")
            print(f"Debug - Full event keys: {list(event.keys())}")
            # Log header keys only, not values (avoid exposing sensitive data)
            print(f"Debug - Header keys: {list(headers.keys()) if headers else 'none'}")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        aid = verify_session_token(tok)
        if not aid:
            print("Session token verification failed")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        print(f"Verified session for athlete_id: {aid}")

        sql = "SELECT athlete_id, display_name, profile_picture FROM users WHERE athlete_id = :aid LIMIT 1"
        res = exec_sql(sql, parameters=[{"name":"aid","value":{"longValue":aid}}])
        records = res.get("records") or []
        if not records:
            print(f"User not found in database for athlete_id: {aid}")
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "user not found"})
            }
        print(f"Successfully retrieved user from database")
        rec = records[0]
        # records format: list of field lists, where each field has stringValue/longValue etc
        athlete_id = int(rec[0].get("longValue") or rec[0].get("stringValue"))
        display_name = rec[1].get("stringValue") if rec[1].get("stringValue") else ""
        # Handle profile_picture which may be NULL in database
        profile_picture = ""
        if len(rec) > 2 and rec[2]:
            profile_picture = rec[2].get("stringValue", "")
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "athlete_id": athlete_id,
                "display_name": display_name,
                "profile_picture": profile_picture
            })
        }
    except Exception as e:
        # Catch any unexpected errors and return proper error with CORS headers
        print(f"Unexpected error in /me handler: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return generic error to client, full details are in CloudWatch logs
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
