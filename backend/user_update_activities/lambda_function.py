# user_update_activities Lambda function
# User endpoint to refresh their own activities from Strava
# Uses the authenticated user's Strava tokens
# 
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)

import os
import json
import time
import base64
import hmac
import hashlib
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")

# Get environment variables safely
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

# Filter activities starting from Jan 1, 2026 00:00:00 UTC
ACTIVITIES_START_DATE = 1767225600

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300


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
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def verify_session_token(tok):
    """Verify session token and return athlete_id"""
    try:
        b, sig = tok.rsplit(".", 1)
        expected = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode())
        if data.get("exp", 0) < time.time():
            return None
        return int(data.get("aid"))
    except Exception:
        return None


def parse_session_cookie(event):
    """Parse rm_session cookie from API Gateway event"""
    headers = event.get("headers") or {}
    
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
        
        print(f"Refreshed access token for athlete {athlete_id}")
        return access_token
    except Exception as e:
        print(f"Failed to refresh token for athlete {athlete_id}: {e}")
        raise


def ensure_valid_token(athlete_id, access_token, refresh_token, expires_at):
    """Ensure access token is valid, refresh if needed"""
    current_time = int(time.time())
    
    # Check if token needs refresh
    if expires_at < current_time + TOKEN_REFRESH_BUFFER_SECONDS:
        print(f"Access token expired or expiring soon for athlete {athlete_id}, refreshing...")
        access_token = refresh_access_token(athlete_id, refresh_token)
    
    return access_token


def get_user_tokens(athlete_id):
    """Get user's tokens from database"""
    sql = "SELECT access_token, refresh_token, expires_at FROM users WHERE athlete_id = :aid"
    params = [{"name": "aid", "value": {"longValue": athlete_id}}]
    result = _exec_sql(sql, params)
    
    records = result.get("records", [])
    if not records:
        print(f"User {athlete_id} not found in database")
        return None, None, 0
    
    record = records[0]
    access_token = record[0].get("stringValue", "")
    refresh_token = record[1].get("stringValue", "")
    expires_at = int(record[2].get("longValue", 0))
    
    return access_token, refresh_token, expires_at


def fetch_strava_activities(access_token, per_page=200, page=1):
    """Fetch activities from Strava API"""
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page={page}&after={ACTIVITIES_START_DATE}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    try:
        with urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode()
            activities = json.loads(response_body)
            print(f"Fetched {len(activities) if isinstance(activities, list) else 'non-list'} activities from Strava")
        return activities
    except Exception as e:
        print(f"Failed to fetch activities from Strava: {e}")
        if hasattr(e, 'code'):
            print(f"HTTP status code: {e.code}")
        if hasattr(e, 'read'):
            try:
                error_body = e.read().decode()
                print(f"Error response body: {error_body}")
            except Exception:
                pass
        raise


def store_activity(athlete_id, activity):
    """Store or update activity in database"""
    strava_activity_id = activity.get("id")
    if not strava_activity_id:
        print(f"ERROR: Activity missing id: {activity}")
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
        print(f"Successfully stored activity {strava_activity_id}: {name}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to store activity {strava_activity_id}: {e}")
        return False


def update_user_activities(athlete_id, per_page=200):
    """Update activities for the authenticated user"""
    print(f"Updating activities for user {athlete_id}")
    
    # Get user tokens
    access_token, refresh_token, expires_at = get_user_tokens(athlete_id)
    
    if not access_token or not refresh_token:
        raise ValueError(f"User {athlete_id} not found or not connected to Strava")
    
    # Ensure token is valid
    access_token = ensure_valid_token(athlete_id, access_token, refresh_token, expires_at)
    
    # Fetch activities from Strava - get first page only
    activities = fetch_strava_activities(access_token, per_page=per_page, page=1)
    
    if not isinstance(activities, list):
        raise RuntimeError(f"Unexpected response from Strava API: {type(activities)}")
    
    # Store activities in database
    stored_count = 0
    failed_count = 0
    
    for activity in activities:
        if store_activity(athlete_id, activity):
            stored_count += 1
        else:
            failed_count += 1
    
    return {
        "message": "Activities updated successfully",
        "athlete_id": athlete_id,
        "total_activities": len(activities),
        "stored": stored_count,
        "failed": failed_count
    }


def handler(event, context):
    """
    Lambda handler for user activity updates.
    
    User endpoint to refresh their own activities from Strava.
    Requires authentication. Uses the authenticated user's Strava tokens.
    
    Path: POST /activities/update
    """
    print(f"user_update_activities handler invoked")
    print(f"Event: {json.dumps(event, default=str)}")
    
    # Validate required environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "server configuration error"})
        }
    
    try:
        # Verify authentication
        session_token = parse_session_cookie(event)
        if not session_token:
            print("No session cookie found")
            return {
                "statusCode": 401,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "authentication required"})
            }
        
        athlete_id = verify_session_token(session_token)
        if not athlete_id:
            print("Invalid session token")
            return {
                "statusCode": 401,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "invalid or expired session"})
            }
        
        # Update activities for authenticated user
        result = update_user_activities(athlete_id)
        
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps(result)
        }
        
    except ValueError as e:
        print(f"Validation error: {e}")
        return {
            "statusCode": 404,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        print(f"Error in user_update_activities handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "internal server error"})
        }
