# scheduled_activity_update Lambda function
# Runs every hour to update recent activities for all connected users
# Updates activities from the last 24 hours from Strava API
# 
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)

import os
import json
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")


def log(message, level="INFO"):
    """Enhanced logging with timestamp and level"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    print(f"[{timestamp}] [{level}] {message}")

# Get environment variables safely - they are checked in handler
DB_CLUSTER_ARN = None
DB_SECRET_ARN = None
DB_NAME = None

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

# Filter activities starting from Jan 1, 2026 00:00:00 UTC
# Unix timestamp: 1767225600
ACTIVITIES_START_DATE = 1767225600

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300

# Update activities from the last 24 hours
UPDATE_WINDOW_SECONDS = 24 * 60 * 60


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
        
        log(f"Refreshed access token for athlete {athlete_id}", "INFO")
        return access_token
    except Exception as e:
        log(f"Failed to refresh token for athlete {athlete_id}: {e}", "ERROR")
        raise


def ensure_valid_token(athlete_id, access_token, refresh_token, expires_at):
    """Ensure access token is valid, refresh if needed"""
    current_time = int(time.time())
    
    # Check if token needs refresh
    if expires_at < current_time + TOKEN_REFRESH_BUFFER_SECONDS:
        log(f"Access token expired or expiring soon for athlete {athlete_id}, refreshing...", "INFO")
        access_token = refresh_access_token(athlete_id, refresh_token)
    
    return access_token


def fetch_strava_activities(access_token, after_timestamp, per_page=200):
    """Fetch activities from Strava API after a given timestamp"""
    url = f"{STRAVA_ACTIVITIES_URL}?per_page={per_page}&page=1&after={after_timestamp}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    try:
        with urlopen(req, timeout=30) as resp:
            response_body = resp.read().decode()
            activities = json.loads(response_body)
            log(f"Fetched {len(activities) if isinstance(activities, list) else 'non-list'} activities from Strava", "INFO")
        return activities
    except Exception as e:
        log(f"Failed to fetch activities from Strava: {e}", "ERROR")
        if hasattr(e, 'code'):
            log(f"HTTP status code: {e.code}", "ERROR")
        if hasattr(e, 'read'):
            try:
                error_body = e.read().decode()
                log(f"Error response body: {error_body}", "ERROR")
            except Exception:
                pass
        raise


def store_activity(athlete_id, activity):
    """Store or update activity in database"""
    strava_activity_id = activity.get("id")
    if not strava_activity_id:
        log(f"Activity missing id: {activity}", "ERROR")
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
        log(f"Successfully stored activity {strava_activity_id}: {name}", "INFO")
        return True
    except Exception as e:
        log(f"Failed to store activity {strava_activity_id}: {e}", "ERROR")
        return False


def get_all_connected_users():
    """Get all users with valid Strava tokens"""
    sql = """
    SELECT athlete_id, access_token, refresh_token, expires_at 
    FROM users 
    WHERE access_token IS NOT NULL 
      AND refresh_token IS NOT NULL
    ORDER BY athlete_id
    """
    result = _exec_sql(sql)
    
    users = []
    records = result.get("records", [])
    for record in records:
        athlete_id = int(record[0].get("longValue", 0))
        access_token = record[1].get("stringValue", "")
        refresh_token = record[2].get("stringValue", "")
        expires_at = int(record[3].get("longValue", 0))
        
        if athlete_id and access_token and refresh_token:
            users.append({
                "athlete_id": athlete_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at
            })
    
    return users


def update_recent_activities_for_user(user):
    """Update recent activities for a single user"""
    athlete_id = user["athlete_id"]
    access_token = user["access_token"]
    refresh_token = user["refresh_token"]
    expires_at = user["expires_at"]
    
    try:
        log(f"Processing user {athlete_id}...", "INFO")
        
        # Ensure token is valid
        access_token = ensure_valid_token(athlete_id, access_token, refresh_token, expires_at)
        
        # Calculate timestamp for 24 hours ago
        current_time = int(time.time())
        after_timestamp = max(ACTIVITIES_START_DATE, current_time - UPDATE_WINDOW_SECONDS)
        
        # Fetch recent activities
        activities = fetch_strava_activities(access_token, after_timestamp)
        
        if not isinstance(activities, list):
            log(f"Unexpected response from Strava API for user {athlete_id}: {type(activities)}", "ERROR")
            return {"athlete_id": athlete_id, "success": False, "error": "Invalid API response"}
        
        # Store activities
        stored_count = 0
        failed_count = 0
        
        for activity in activities:
            if store_activity(athlete_id, activity):
                stored_count += 1
            else:
                failed_count += 1
        
        log(f"User {athlete_id}: Stored {stored_count}, Failed {failed_count} out of {len(activities)} activities", "INFO")
        
        return {
            "athlete_id": athlete_id,
            "success": True,
            "total_activities": len(activities),
            "stored": stored_count,
            "failed": failed_count
        }
        
    except Exception as e:
        log(f"ERROR processing user {athlete_id}: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return {"athlete_id": athlete_id, "success": False, "error": str(e)}


def handler(event, context):
    """
    Lambda handler for scheduled activity updates.
    
    Runs every hour to update activities from the last 24 hours for all connected users.
    """
    start_time = datetime.utcnow()
    log("="*80, "INFO")
    log("SCHEDULED ACTIVITY UPDATE - START", "INFO")
    log(f"Execution started at: {start_time.isoformat()}Z", "INFO")
    log(f"Event: {json.dumps(event, default=str)}", "INFO")
    log("="*80, "INFO")
    
    # Get environment variables
    db_cluster_arn = os.environ.get("DB_CLUSTER_ARN", "")
    db_secret_arn = os.environ.get("DB_SECRET_ARN", "")
    
    # Validate required environment variables
    if not db_cluster_arn or not db_secret_arn:
        log("Missing DB_CLUSTER_ARN or DB_SECRET_ARN", "ERROR")
        log("SCHEDULED ACTIVITY UPDATE - FAILED (Configuration Error)", "ERROR")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }
    
    try:
        # Get all connected users
        log("Fetching all connected users...", "INFO")
        users = get_all_connected_users()
        log(f"Found {len(users)} connected users", "INFO")
        
        if not users:
            log("No connected users found, nothing to update", "INFO")
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            log("="*80, "INFO")
            log(f"SCHEDULED ACTIVITY UPDATE - SUCCESS (No Users)", "INFO")
            log(f"Execution completed at: {end_time.isoformat()}Z", "INFO")
            log(f"Duration: {duration:.2f} seconds", "INFO")
            log("="*80, "INFO")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "No connected users found",
                    "total_users": 0,
                    "results": []
                })
            }
        
        # Update activities for each user
        log("Starting activity updates for all users...", "INFO")
        results = []
        for user in users:
            result = update_recent_activities_for_user(user)
            results.append(result)
        
        # Summary
        successful_updates = sum(1 for r in results if r.get("success"))
        failed_updates = len(results) - successful_updates
        total_activities_stored = sum(r.get("stored", 0) for r in results)
        
        summary = {
            "message": "Scheduled activity update completed",
            "total_users": len(users),
            "successful_updates": successful_updates,
            "failed_updates": failed_updates,
            "total_activities_stored": total_activities_stored,
            "results": results
        }
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Log summary
        log("="*80, "INFO")
        log("EXECUTION SUMMARY:", "INFO")
        log(f"  Total users processed: {len(users)}", "INFO")
        log(f"  Successful updates: {successful_updates}", "INFO")
        log(f"  Failed updates: {failed_updates}", "INFO")
        log(f"  Total activities stored: {total_activities_stored}", "INFO")
        log("="*80, "INFO")
        
        status = "SUCCESS" if failed_updates == 0 else "PARTIAL SUCCESS"
        log(f"SCHEDULED ACTIVITY UPDATE - {status}", "INFO")
        log(f"Execution completed at: {end_time.isoformat()}Z", "INFO")
        log(f"Duration: {duration:.2f} seconds", "INFO")
        log("="*80, "INFO")
        
        return {
            "statusCode": 200,
            "body": json.dumps(summary)
        }
        
    except Exception as e:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        log("="*80, "ERROR")
        log(f"Error in scheduled_activity_update handler: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        log("="*80, "ERROR")
        log("SCHEDULED ACTIVITY UPDATE - FAILED", "ERROR")
        log(f"Execution completed at: {end_time.isoformat()}Z", "ERROR")
        log(f"Duration: {duration:.2f} seconds", "ERROR")
        log("="*80, "ERROR")
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error", "details": str(e)})
        }
