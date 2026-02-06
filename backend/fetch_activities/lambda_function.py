# fetch_activities Lambda function
# Fetches activities from Strava API and stores them in the database
# 
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)
# MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN (optional - for auto trail matching)

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
lambda_client = boto3.client("lambda")

# Get environment variables safely - validation happens in handler
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN = os.environ.get("MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN", "")

STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

# Filter activities starting from Jan 1, 2026 00:00:00 UTC
# Unix timestamp: 1767225600
ACTIVITIES_START_DATE = 1767225600


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


def fetch_strava_activities(access_token, per_page=30, page=1):
    """Fetch activities from Strava API"""
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page={page}&after={ACTIVITIES_START_DATE}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    try:
        with urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode()
            print(f"Strava API response status: {resp.status}, body length: {len(response_body)}")
            activities = json.loads(response_body)
            print(f"Parsed {len(activities) if isinstance(activities, list) else 'non-list'} activities from Strava")
        return activities
    except Exception as e:
        print(f"Failed to fetch activities from Strava: {e}")
        print(f"Exception type: {type(e).__name__}")
        if hasattr(e, 'code'):
            print(f"HTTP status code: {e.code}")
        if hasattr(e, 'read'):
            try:
                error_body = e.read().decode()
                print(f"Error response body: {error_body}")
            except:
                pass
        raise


def store_activities(athlete_id, activities):
    """Store activities in database"""
    stored_count = 0
    failed_count = 0
    
    if not isinstance(activities, list):
        print(f"ERROR: activities is not a list, got {type(activities)}: {activities}")
        return 0
    
    print(f"Attempting to store {len(activities)} activities for athlete {athlete_id}")
    
    for activity in activities:
        strava_activity_id = activity.get("id")
        if not strava_activity_id:
            print(f"WARNING: Skipping activity without id: {activity.keys() if isinstance(activity, dict) else type(activity)}")
            continue
        
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
        # Note: time_on_trail, distance_on_trail, and last_matched are initialized as NULL
        # time_on_trail and distance_on_trail will be computed later through trail intersection calculations
        # last_matched will be set when the activity is checked against trail matching database
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
            stored_count += 1
            print(f"Successfully stored activity {strava_activity_id}: {name}")
        except Exception as e:
            failed_count += 1
            print(f"ERROR: Failed to store activity {strava_activity_id} ({name}): {e}")
            print(f"Activity data: distance={distance}, moving_time={moving_time}, type={activity_type}")
            continue
    
    print(f"Storage complete: {stored_count} stored, {failed_count} failed")
    return stored_count


def trigger_trail_matching():
    """
    Trigger the match_unmatched_activities Lambda to match newly fetched activities with trails.
    
    This is called after activities are successfully stored to initiate trail matching.
    Uses async invocation so it doesn't block the fetch_activities flow.
    
    Note: This triggers matching for ALL unmatched activities across all users, not just
    the current athlete. This is intentional to handle any backlog of unmatched activities,
    but it means trail matching happens globally, not just for the current user.
    
    Returns:
        bool: True if trail matching was successfully triggered, False if not configured
              or if invocation failed.
    """
    if not MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN:
        print("INFO: MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN not configured, skipping trail matching")
        return False
    
    try:
        # Invoke match_unmatched_activities Lambda asynchronously
        # This will find ALL activities where last_matched IS NULL (across all users)
        # and trigger matching for them
        payload = json.dumps({})  # No specific payload needed - will match all unmatched
        
        response = lambda_client.invoke(
            FunctionName=MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN,
            InvocationType='Event',  # Async invocation
            Payload=payload
        )
        print(f"Successfully triggered trail matching lambda: status {response.get('StatusCode')}")
        return True
    except Exception as e:
        # Don't fail the fetch flow if trail matching trigger fails
        print(f"WARNING: Failed to trigger trail matching: {e}")
        return False


def fetch_activities_for_athlete(athlete_id, access_token, refresh_token, expires_at):
    """Fetch and store activities for a single athlete"""
    current_time = int(time.time())
    
    print(f"=== fetch_activities_for_athlete START ===")
    print(f"athlete_id: {athlete_id}")
    print(f"Token expires_at: {expires_at}, current_time: {current_time}, diff: {expires_at - current_time}s")
    
    # Check if token needs refresh (with 5-minute buffer to prevent expiration during API call)
    TOKEN_REFRESH_BUFFER = 300  # 5 minutes
    if expires_at < current_time + TOKEN_REFRESH_BUFFER:
        print(f"Access token expired or expiring soon for athlete {athlete_id}, refreshing...")
        try:
            access_token = refresh_access_token(athlete_id, refresh_token)
            print(f"Token refresh successful, new token: {'***' if access_token else 'MISSING'}")
        except Exception as e:
            print(f"ERROR: Token refresh failed: {e}")
            raise
    else:
        print(f"Access token is valid, skipping refresh")
    
    # Fetch activities from Strava (first page, 30 activities)
    print(f"Fetching activities from Strava API for athlete {athlete_id}...")
    try:
        activities = fetch_strava_activities(access_token, per_page=30, page=1)
        print(f"fetch_strava_activities returned: {type(activities)} with {len(activities) if isinstance(activities, list) else 'N/A'} items")
    except Exception as e:
        print(f"ERROR: Failed to fetch activities from Strava: {e}")
        raise
    
    # Store activities in database
    print(f"Storing activities in database...")
    try:
        stored_count = store_activities(athlete_id, activities)
        print(f"store_activities returned: {stored_count}")
    except Exception as e:
        print(f"ERROR: Failed to store activities: {e}")
        raise
    
    # Trigger trail matching for newly fetched activities
    if stored_count > 0:
        print(f"Triggering trail matching for {stored_count} newly stored activities...")
        trigger_trail_matching()
    
    print(f"=== fetch_activities_for_athlete END: {stored_count} activities stored ===")
    return stored_count


def handler(event, context):
    """Lambda handler - requires authentication, fetches activities for authenticated user only
    
    Can be invoked in two ways:
    1. Via API Gateway with cookies (for user-initiated fetches)
    2. Directly from another lambda with payload containing athlete credentials (for automatic fetches)
    """
    cors_headers = get_cors_headers()
    
    print(f"fetch_activities handler called")
    print(f"Event keys: {list(event.keys())}")
    
    # Check if this is a direct lambda invocation (has athlete_id in payload)
    # vs an API Gateway invocation (has requestContext)
    is_direct_invoke = "athlete_id" in event and "access_token" in event
    
    if is_direct_invoke:
        print(f"Direct lambda invocation detected")
        # Direct invocation from auth_callback with credentials
        athlete_id = event.get("athlete_id")
        access_token = event.get("access_token")
        refresh_token = event.get("refresh_token")
        expires_at = event.get("expires_at")
        
        print(f"Direct invocation for athlete_id: {athlete_id}")
        
        # Validate credentials are present
        if not athlete_id or not access_token or not refresh_token:
            print(f"ERROR: Missing required fields in direct invocation")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "missing required fields"})
            }
        
        # Fetch and store activities
        try:
            stored_count = fetch_activities_for_athlete(athlete_id, access_token, refresh_token, expires_at)
            print(f"Direct invocation completed: {stored_count} activities stored")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Successfully fetched activities",
                    "total_activities_stored": stored_count
                })
            }
        except Exception as e:
            print(f"Error in direct invocation: {e}")
            import traceback
            traceback.print_exc()
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "internal server error"})
            }
    
    # API Gateway invocation - continue with existing logic
    print(f"Request method: {event.get('requestContext', {}).get('http', {}).get('method')}")
    
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
        
        # Parse cookies to get session token
        tok = parse_session_cookie(event)
        
        if not tok:
            print("ERROR: No session cookie found")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        # Verify session token
        athlete_id = verify_session_token(tok)
        if not athlete_id:
            print("ERROR: Invalid session token")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        
        print(f"Authenticated as athlete_id: {athlete_id}")
        
        # Get user's tokens from database
        sql = "SELECT access_token, refresh_token, expires_at FROM users WHERE athlete_id = :aid"
        params = [{"name": "aid", "value": {"longValue": athlete_id}}]
        result = _exec_sql(sql, params)
        
        records = result.get("records", [])
        if not records:
            print(f"ERROR: User {athlete_id} not found in database")
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "user not found"})
            }
        
        record = records[0]
        access_token = record[0].get("stringValue", "")
        refresh_token = record[1].get("stringValue", "")
        expires_at = int(record[2].get("longValue", 0))
        
        print(f"Retrieved tokens from database: access_token={'***' if access_token else 'MISSING'}, refresh_token={'***' if refresh_token else 'MISSING'}, expires_at={expires_at}")
        
        if not access_token or not refresh_token:
            print("ERROR: User not connected to Strava (tokens missing)")
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "user not connected to Strava"})
            }
        
        # Fetch and store activities for this athlete
        print(f"Calling fetch_activities_for_athlete...")
        stored_count = fetch_activities_for_athlete(athlete_id, access_token, refresh_token, expires_at)
        
        print(f"fetch_activities_for_athlete returned: {stored_count} activities stored")
        
        # Provide helpful message based on result
        if stored_count == 0:
            message = "Successfully fetched activities (no new activities found). If you have activities in Strava but don't see them here, try disconnecting and reconnecting to grant the required permissions."
        else:
            message = "Successfully fetched activities"
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "message": message,
                "total_activities_stored": stored_count
            })
        }
    except Exception as e:
        print(f"Error in fetch_activities handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
