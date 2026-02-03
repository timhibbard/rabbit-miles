# update_activities Lambda function
# Updates activities in the database from Strava
# 
# Accepts either:
# - Single Strava activity ID (requires athlete_id in request)
# - Single athlete ID (fetches recent activities for that athlete)
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)

import os
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")

# Get environment variables safely - they are checked in handler
DB_CLUSTER_ARN = None
DB_SECRET_ARN = None
DB_NAME = None

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITY_URL = "https://www.strava.com/api/v3/activities"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300


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
    global DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME
    
    if DB_CLUSTER_ARN is None:
        DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
    if DB_SECRET_ARN is None:
        DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
    if DB_NAME is None:
        DB_NAME = os.environ.get("DB_NAME", "postgres")
    
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


def ensure_valid_token(athlete_id, access_token, refresh_token, expires_at):
    """Ensure access token is valid, refresh if needed"""
    current_time = int(time.time())
    
    # Check if token needs refresh
    if expires_at < current_time + TOKEN_REFRESH_BUFFER_SECONDS:
        print(f"Access token expired or expiring soon for athlete {athlete_id}, refreshing...")
        access_token = refresh_access_token(athlete_id, refresh_token)
    
    return access_token


def fetch_activity_details(access_token, activity_id):
    """Fetch detailed activity data from Strava API"""
    url = f"{STRAVA_ACTIVITY_URL}/{activity_id}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    try:
        with urlopen(req, timeout=30) as resp:
            activity = json.loads(resp.read().decode())
        print(f"Fetched activity {activity_id} from Strava API")
        return activity
    except Exception as e:
        print(f"Failed to fetch activity {activity_id} from Strava: {e}")
        if hasattr(e, 'code'):
            print(f"HTTP status code: {e.code}")
        if hasattr(e, 'read'):
            try:
                error_body = e.read().decode()
                print(f"Error response body: {error_body}")
            except Exception:
                pass
        raise


def fetch_strava_activities(access_token, per_page=30, page=1):
    """Fetch activities from Strava API"""
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page={page}"
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
    
    # Get polyline from map - prefer full polyline over summary_polyline
    polyline = ""
    if activity.get("map"):
        # Try full polyline first, fallback to summary_polyline
        polyline = activity["map"].get("polyline") or activity["map"].get("summary_polyline", "")
    
    # Insert or update activity
    sql = """
    INSERT INTO activities (
        athlete_id, strava_activity_id, name, distance, moving_time, elapsed_time,
        total_elevation_gain, type, start_date, start_date_local, timezone, polyline,
        time_on_trail, distance_on_trail, updated_at
    )
    VALUES (:aid, :sid, :name, :dist, :mt, :et, :elev, :type, CAST(:sd AS TIMESTAMP), CAST(:sdl AS TIMESTAMP), :tz, :poly, NULL, NULL, now())
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
    ]
    
    try:
        _exec_sql(sql, params)
        print(f"Successfully stored activity {strava_activity_id}: {name}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to store activity {strava_activity_id}: {e}")
        return False


def update_single_activity(athlete_id, activity_id):
    """Update a single activity by its Strava activity ID"""
    print(f"Updating single activity {activity_id} for athlete {athlete_id}")
    
    # Get user tokens
    access_token, refresh_token, expires_at = get_user_tokens(athlete_id)
    
    if not access_token or not refresh_token:
        raise ValueError(f"User {athlete_id} not found or not connected to Strava")
    
    # Ensure token is valid
    access_token = ensure_valid_token(athlete_id, access_token, refresh_token, expires_at)
    
    # Fetch activity details from Strava
    activity = fetch_activity_details(access_token, activity_id)
    
    # Store activity in database
    success = store_activity(athlete_id, activity)
    
    if not success:
        raise RuntimeError(f"Failed to store activity {activity_id}")
    
    return {
        "message": "Activity updated successfully",
        "activity_id": activity_id,
        "athlete_id": athlete_id
    }


def update_athlete_activities(athlete_id, per_page=30):
    """Update recent activities for an athlete"""
    print(f"Updating recent activities for athlete {athlete_id}")
    
    # Get user tokens
    access_token, refresh_token, expires_at = get_user_tokens(athlete_id)
    
    if not access_token or not refresh_token:
        raise ValueError(f"User {athlete_id} not found or not connected to Strava")
    
    # Ensure token is valid
    access_token = ensure_valid_token(athlete_id, access_token, refresh_token, expires_at)
    
    # Fetch activities from Strava
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
    Lambda handler for updating activities in the database.
    
    Accepts JSON body with either:
    - {"athlete_id": 123456} - updates recent activities for athlete
    - {"athlete_id": 123456, "activity_id": 789012} - updates single activity
    
    Or query string parameters:
    - ?athlete_id=123456
    - ?athlete_id=123456&activity_id=789012
    """
    print(f"update_activities handler invoked")
    print(f"Event: {json.dumps(event, default=str)}")
    
    # Get environment variables
    db_cluster_arn = os.environ.get("DB_CLUSTER_ARN", "")
    db_secret_arn = os.environ.get("DB_SECRET_ARN", "")
    
    # Validate required environment variables
    if not db_cluster_arn or not db_secret_arn:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }
    
    try:
        # Parse input from JSON body or query string
        body = {}
        if event.get("body"):
            try:
                body = json.loads(event["body"])
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "invalid JSON body"})
                }
        
        # Check query string parameters as fallback
        query_params = event.get("queryStringParameters") or {}
        
        # Get athlete_id and activity_id
        athlete_id = body.get("athlete_id") or query_params.get("athlete_id")
        activity_id = body.get("activity_id") or query_params.get("activity_id")
        
        # Validate athlete_id is provided
        if not athlete_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "athlete_id is required"})
            }
        
        # Convert to integers
        try:
            athlete_id = int(athlete_id)
            if activity_id:
                activity_id = int(activity_id)
        except (ValueError, TypeError):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "athlete_id and activity_id must be integers"})
            }
        
        # Update single activity or all activities for athlete
        if activity_id:
            result = update_single_activity(athlete_id, activity_id)
        else:
            result = update_athlete_activities(athlete_id)
        
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
        
    except ValueError as e:
        print(f"Validation error: {e}")
        return {
            "statusCode": 404,
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        print(f"Error in update_activities handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error"})
        }
