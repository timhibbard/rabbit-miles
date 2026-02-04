# get_activities Lambda function
# Returns activities for authenticated user
# 
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)

import os
import json
import base64
import hmac
import hashlib
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


def _exec_sql(sql, parameters=None):
    """Execute SQL statement using RDS Data API"""
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
    """Lambda handler for GET /activities"""
    cors_headers = get_cors_headers()
    
    # Handle OPTIONS preflight
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
        
        # Try to get session token from multiple sources:
        # 1. Authorization header (for Mobile Safari compatibility)
        # 2. Cookies array (API Gateway HTTP API v2 format)
        # 3. Cookie header (backwards compatibility)
        
        headers = event.get("headers") or {}
        auth_header = headers.get("authorization") or headers.get("Authorization")
        
        tok = None
        
        # First, try Authorization header (Mobile Safari fallback)
        if auth_header:
            # Format: "Bearer <token>"
            if auth_header.startswith("Bearer "):
                tok = auth_header[7:]  # Remove "Bearer " prefix
                print("Found session token in Authorization header")
        
        # If not in Authorization header, try cookies
        if not tok:
            # API Gateway HTTP API v2 provides cookies in event['cookies'] array
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
                        tok = v
                        break
                if tok:
                    break
            
            # Fallback to cookie header
            if not tok and cookie_header:
                for part in cookie_header.split(";"):
                    part = part.strip()
                    if not part or "=" not in part:
                        continue
                    k, v = part.split("=", 1)
                    if k == "rm_session":
                        tok = v
                        break
        
        if not tok:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        # Verify session token
        aid = verify_session_token(tok)
        if not aid:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        
        # Get query parameters for pagination
        qs = event.get("queryStringParameters") or {}
        limit = int(qs.get("limit", 10))
        offset = int(qs.get("offset", 0))
        
        # Limit max results per request
        if limit > 100:
            limit = 100
        
        # Fetch activities for the authenticated user
        sql = """
        SELECT 
            id, strava_activity_id, name, distance, moving_time, elapsed_time,
            total_elevation_gain, type, start_date, start_date_local, timezone,
            time_on_trail, distance_on_trail
        FROM activities
        WHERE athlete_id = :aid
        ORDER BY start_date DESC
        LIMIT :limit OFFSET :offset
        """
        
        params = [
            {"name": "aid", "value": {"longValue": aid}},
            {"name": "limit", "value": {"longValue": limit}},
            {"name": "offset", "value": {"longValue": offset}},
        ]
        
        result = _exec_sql(sql, params)
        records = result.get("records", [])
        
        # Format activities for response
        activities = []
        for record in records:
            # RDS Data API returns DECIMAL columns as stringValue, not doubleValue
            distance_str = record[3].get("stringValue")
            elevation_str = record[6].get("stringValue")
            distance_on_trail_str = record[12].get("stringValue")
            
            # Convert string values to float, handling None/empty strings
            try:
                distance = float(distance_str) if distance_str is not None else 0.0
            except (ValueError, TypeError):
                distance = 0.0
            
            try:
                elevation = float(elevation_str) if elevation_str is not None else 0.0
            except (ValueError, TypeError):
                elevation = 0.0
            
            try:
                distance_on_trail = float(distance_on_trail_str) if distance_on_trail_str is not None else None
            except (ValueError, TypeError):
                distance_on_trail = None
            
            # Get time_on_trail, checking for null first
            time_on_trail = None
            if not record[11].get("isNull"):
                time_on_trail_value = record[11].get("longValue")
                if time_on_trail_value is not None:
                    time_on_trail = int(time_on_trail_value)
            
            activity = {
                "id": int(record[0].get("longValue", 0)),
                "strava_activity_id": int(record[1].get("longValue", 0)),
                "name": record[2].get("stringValue", ""),
                "distance": distance,
                "moving_time": int(record[4].get("longValue", 0)),
                "elapsed_time": int(record[5].get("longValue", 0)),
                "total_elevation_gain": elevation,
                "type": record[7].get("stringValue", ""),
                "start_date": record[8].get("stringValue", "") if not record[8].get("isNull") else None,
                "start_date_local": record[9].get("stringValue", "") if not record[9].get("isNull") else None,
                "timezone": record[10].get("stringValue", ""),
                "time_on_trail": time_on_trail,
                "distance_on_trail": distance_on_trail,
            }
            activities.append(activity)
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "activities": activities,
                "limit": limit,
                "offset": offset,
                "count": len(activities)
            })
        }
        
    except Exception as e:
        print(f"Error in get_activities handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
