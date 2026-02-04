"""
Lambda function to reset last_matched field for all activities
This allows the trail matching process to re-process all activities
"""

import os
import json
import base64
import hmac
import hashlib
from urllib.parse import urlparse
import boto3

# Initialize RDS Data client
rds_data = boto3.client("rds-data")

# Environment variables
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
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def get_cors_headers():
    """Return CORS headers for cross-origin requests"""
    headers = {"Content-Type": "application/json"}
    origin = get_cors_origin()
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers


def verify_session_token(tok):
    """Verify session token and return athlete_id"""
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


def parse_session_cookie(event):
    """Parse rm_session cookie from API Gateway event or Authorization header"""
    headers = event.get("headers") or {}
    auth_header = headers.get("authorization") or headers.get("Authorization")
    
    # First, try Authorization header (Mobile Safari fallback)
    if auth_header:
        # Format: "Bearer <token>"
        if auth_header.startswith("Bearer "):
            tok = auth_header[7:]  # Remove "Bearer " prefix
            print(f"Found session token in Authorization header: {tok[:20]}...")
            return tok
    
    # If not in Authorization header, try cookies
    cookies_array = event.get("cookies") or []
    cookie_header = headers.get("cookie") or headers.get("Cookie")
    
    # Try cookies array first (API Gateway HTTP API v2 format)
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
    
    # Fallback to cookie header
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v
    
    return None


def _exec_sql(sql, params=None):
    """Execute SQL statement using RDS Data API"""
    exec_params = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    
    if params:
        exec_params["parameters"] = params
    
    response = rds_data.execute_statement(**exec_params)
    return response


def handler(event, context):
    """
    Lambda handler for resetting last_matched field
    
    Expected: POST request to /activities/reset-matching
    Returns: JSON with count of reset activities
    """
    print("Event received:", json.dumps(event))
    
    cors_headers = get_cors_headers()
    
    # Handle OPTIONS preflight
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
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
        
        # Parse and verify session token
        tok = parse_session_cookie(event)
        if not tok:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        aid = verify_session_token(tok)
        if not aid:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        
        # Reset last_matched for all activities belonging to authenticated user
        # Note: We don't check IS NOT NULL as it's a no-op to set NULL to NULL
        # and the athlete_id index will efficiently filter the results
        sql = """
        UPDATE activities 
        SET last_matched = NULL 
        WHERE athlete_id = :aid
        """
        
        params = [
            {"name": "aid", "value": {"longValue": aid}},
        ]
        
        response = _exec_sql(sql, params)
        affected_rows = response.get("numberOfRecordsUpdated", 0)
        
        print(f"Successfully reset last_matched for {affected_rows} activities for athlete {aid}")
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "success": True,
                "activities_reset": affected_rows,
                "message": f"Successfully reset {affected_rows} activities for trail matching"
            })
        }
        
    except Exception as e:
        print(f"ERROR: Failed to reset last_matched: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({
                "error": "Failed to reset activities",
                "details": str(e)
            })
        }
