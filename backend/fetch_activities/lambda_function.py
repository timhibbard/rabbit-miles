# fetch_activities Lambda function
# Fetches activities from Strava API and stores them in the database
# Can be invoked:
# 1. By API Gateway endpoint (e.g., POST /activities/fetch)
# 2. By CloudWatch Events (scheduled)
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)
# FRONTEND_URL (for CORS)

import os
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")

DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ.get("DB_NAME", "postgres")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


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
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page={page}"
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
    
    for activity in activities:
        strava_activity_id = activity.get("id")
        if not strava_activity_id:
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
        
        # Get polyline from map summary_polyline
        polyline = ""
        if activity.get("map"):
            polyline = activity["map"].get("summary_polyline", "")
        
        # Insert or update activity
        sql = """
        INSERT INTO activities (
            athlete_id, strava_activity_id, name, distance, moving_time, elapsed_time,
            total_elevation_gain, type, start_date, start_date_local, timezone, polyline, updated_at
        )
        VALUES (:aid, :sid, :name, :dist, :mt, :et, :elev, :type, :sd, :sdl, :tz, :poly, now())
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
            stored_count += 1
        except Exception as e:
            print(f"Failed to store activity {strava_activity_id}: {e}")
            continue
    
    return stored_count


def fetch_activities_for_athlete(athlete_id, access_token, refresh_token, expires_at):
    """Fetch and store activities for a single athlete"""
    current_time = int(time.time())
    
    # Check if token needs refresh (with 5-minute buffer to prevent expiration during API call)
    TOKEN_REFRESH_BUFFER = 300  # 5 minutes
    if expires_at < current_time + TOKEN_REFRESH_BUFFER:
        print(f"Access token expired or expiring soon for athlete {athlete_id}, refreshing...")
        access_token = refresh_access_token(athlete_id, refresh_token)
    
    # Fetch activities from Strava (first page, 30 activities)
    print(f"Fetching activities for athlete {athlete_id}...")
    activities = fetch_strava_activities(access_token, per_page=30, page=1)
    
    # Store activities in database
    stored_count = store_activities(athlete_id, activities)
    
    print(f"Stored {stored_count} activities for athlete {athlete_id}")
    return stored_count


def handler(event, context):
    """Lambda handler - can be invoked via API Gateway or scheduled event"""
    cors_headers = get_cors_headers()
    
    # Handle OPTIONS preflight
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Cookie",
                "Access-Control-Max-Age": "86400"
            },
            "body": ""
        }
    
    try:
        # Get all users with valid tokens
        sql = "SELECT athlete_id, access_token, refresh_token, expires_at FROM users WHERE access_token IS NOT NULL"
        result = _exec_sql(sql)
        
        records = result.get("records", [])
        if not records:
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({"message": "No users to fetch activities for", "count": 0})
            }
        
        total_stored = 0
        successful_athletes = []
        failed_athletes = []
        
        for record in records:
            try:
                athlete_id = int(record[0].get("longValue"))
                access_token = record[1].get("stringValue", "")
                refresh_token = record[2].get("stringValue", "")
                expires_at = int(record[3].get("longValue", 0))
                
                stored = fetch_activities_for_athlete(athlete_id, access_token, refresh_token, expires_at)
                total_stored += stored
                successful_athletes.append(athlete_id)
            except Exception as e:
                print(f"Failed to fetch activities for athlete {athlete_id}: {e}")
                failed_athletes.append(athlete_id)
                continue
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "message": f"Successfully fetched activities",
                "total_activities_stored": total_stored,
                "successful_athletes": successful_athletes,
                "failed_athletes": failed_athletes
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
