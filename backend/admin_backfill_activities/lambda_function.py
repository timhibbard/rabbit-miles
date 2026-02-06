# rabbitmiles-admin-backfill-activities (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)
# ADMIN_ATHLETE_IDS (comma-separated list of admin athlete IDs)
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)

import os
import sys
import json
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import boto3

# Add parent directory to path to import admin_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import admin_utils

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

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


def exec_sql(sql, parameters=None):
    """Execute SQL using RDS Data API"""
    kwargs = dict(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        sql=sql,
        database=DB_NAME
    )
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


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
        exec_sql(sql, params)
        
        print(f"Refreshed access token for athlete {athlete_id}")
        return access_token
    except Exception as e:
        print(f"Failed to refresh token for athlete {athlete_id}: {e}")
        raise


def fetch_strava_activities(access_token, per_page=200, page=1):
    """Fetch activities from Strava API"""
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page={page}&after={ACTIVITIES_START_DATE}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    try:
        with urlopen(req, timeout=30) as resp:
            activities = json.loads(resp.read().decode())
        return activities
    except Exception as e:
        print(f"Failed to fetch activities from Strava: {e}")
        raise


def store_activities(athlete_id, activities):
    """Store activities in database"""
    stored_count = 0
    
    if not isinstance(activities, list):
        print(f"ERROR: activities is not a list, got {type(activities)}")
        return 0
    
    print(f"Storing {len(activities)} activities for athlete {athlete_id}")
    
    for activity in activities:
        strava_activity_id = activity.get("id")
        if not strava_activity_id:
            continue
        
        # Extract activity data
        name = activity.get("name", "")
        distance = activity.get("distance", 0)
        moving_time = activity.get("moving_time", 0)
        elapsed_time = activity.get("elapsed_time", 0)
        total_elevation_gain = activity.get("total_elevation_gain", 0)
        activity_type = activity.get("type", "")
        start_date = activity.get("start_date", "")
        start_date_local = activity.get("start_date_local", "")
        timezone = activity.get("timezone", "")
        athlete_count = activity.get("athlete_count", 1)
        
        # Get polyline from map
        polyline = ""
        if activity.get("map"):
            polyline = activity["map"].get("polyline") or activity["map"].get("summary_polyline", "")
        
        # Insert or update activity
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
            exec_sql(sql, params)
            stored_count += 1
        except Exception as e:
            print(f"ERROR: Failed to store activity {strava_activity_id}: {e}")
            continue
    
    print(f"Stored {stored_count} activities")
    return stored_count


def backfill_activities_for_athlete(athlete_id):
    """
    Backfill all activities since Jan 1, 2026 for a specific athlete.
    
    Returns:
        Tuple of (stored_count, error_message)
    """
    print(f"=== backfill_activities_for_athlete START for athlete {athlete_id} ===")
    
    # Get user's tokens from database
    sql = "SELECT access_token, refresh_token, expires_at FROM users WHERE athlete_id = :aid"
    params = [{"name": "aid", "value": {"longValue": athlete_id}}]
    result = exec_sql(sql, params)
    
    records = result.get("records", [])
    if not records:
        error = f"User {athlete_id} not found in database"
        print(f"ERROR: {error}")
        return 0, error
    
    record = records[0]
    access_token = record[0].get("stringValue", "")
    refresh_token = record[1].get("stringValue", "")
    expires_at = int(record[2].get("longValue", 0))
    
    if not access_token or not refresh_token:
        error = f"User {athlete_id} not connected to Strava (tokens missing)"
        print(f"ERROR: {error}")
        return 0, error
    
    # Check if token needs refresh
    current_time = int(time.time())
    TOKEN_REFRESH_BUFFER = 300  # 5 minutes
    
    if expires_at < current_time + TOKEN_REFRESH_BUFFER:
        print(f"Access token expired or expiring soon, refreshing...")
        try:
            access_token = refresh_access_token(athlete_id, refresh_token)
        except Exception as e:
            error = f"Token refresh failed: {e}"
            print(f"ERROR: {error}")
            return 0, error
    
    # Fetch all activities with pagination
    all_activities = []
    page = 1
    per_page = 200  # Maximum allowed by Strava API
    
    try:
        while True:
            print(f"Fetching page {page} (per_page={per_page})...")
            activities = fetch_strava_activities(access_token, per_page=per_page, page=page)
            
            if not isinstance(activities, list):
                print(f"ERROR: fetch_strava_activities returned non-list: {type(activities)}")
                break
            
            if len(activities) == 0:
                print(f"No more activities on page {page}, stopping pagination")
                break
            
            print(f"Page {page} returned {len(activities)} activities")
            all_activities.extend(activities)
            
            # If we got fewer activities than per_page, we've reached the end
            if len(activities) < per_page:
                print(f"Received {len(activities)} < {per_page}, reached last page")
                break
            
            page += 1
        
        print(f"Pagination complete: fetched {len(all_activities)} total activities")
    except Exception as e:
        error = f"Failed to fetch activities from Strava: {e}"
        print(f"ERROR: {error}")
        return 0, error
    
    # Store activities in database
    try:
        stored_count = store_activities(athlete_id, all_activities)
        print(f"=== backfill_activities_for_athlete END: {stored_count} activities stored ===")
        return stored_count, None
    except Exception as e:
        error = f"Failed to store activities: {e}"
        print(f"ERROR: {error}")
        return 0, error


def handler(event, context):
    print("=" * 80)
    print("ADMIN BACKFILL ACTIVITIES - START")
    print("=" * 80)
    
    cors_origin = get_cors_origin()
    headers = admin_utils.get_admin_headers(cors_origin)
    
    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        print("LOG - OPTIONS preflight request")
        return {
            "statusCode": 200,
            "headers": {
                **headers,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Cookie",
                "Access-Control-Max-Age": "86400"
            },
            "body": ""
        }
    
    try:
        # Validate required environment variables
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        if not APP_SECRET:
            print("ERROR - Missing APP_SECRET")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        # Extract target athlete_id from path parameters
        path_params = event.get("pathParameters") or {}
        target_athlete_id_str = path_params.get("athlete_id")
        
        if not target_athlete_id_str:
            print("ERROR - Missing athlete_id path parameter")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "missing athlete_id"})
            }
        
        try:
            target_athlete_id = int(target_athlete_id_str)
        except ValueError:
            print(f"ERROR - Invalid athlete_id: {target_athlete_id_str}")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "invalid athlete_id"})
            }
        
        # Verify session and admin status
        print("LOG - Verifying admin session")
        athlete_id, is_admin = admin_utils.verify_admin_session(event, APP_SECRET)
        
        if not athlete_id:
            print("ERROR - Not authenticated")
            return {
                "statusCode": 401,
                "headers": headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        if not is_admin:
            print(f"ERROR - User {athlete_id} is not an admin")
            admin_utils.audit_log_admin_action(
                athlete_id,
                f"/admin/users/{target_athlete_id}/backfill-activities",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {athlete_id} authenticated successfully")
        print(f"LOG - Backfilling activities for user {target_athlete_id}")
        admin_utils.audit_log_admin_action(
            athlete_id,
            f"/admin/users/{target_athlete_id}/backfill-activities",
            "backfill_user_activities",
            {"target_athlete_id": target_athlete_id}
        )
        
        # Perform backfill
        stored_count, error_message = backfill_activities_for_athlete(target_athlete_id)
        
        if error_message:
            print(f"ERROR - Backfill failed: {error_message}")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": "backfill failed",
                    "message": error_message
                })
            }
        
        print(f"LOG - Backfill successful: {stored_count} activities stored")
        print("=" * 80)
        print("ADMIN BACKFILL ACTIVITIES - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "message": "Backfill completed successfully",
                "athlete_id": target_athlete_id,
                "activities_stored": stored_count
            })
        }
    
    except Exception as e:
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("ADMIN BACKFILL ACTIVITIES - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
