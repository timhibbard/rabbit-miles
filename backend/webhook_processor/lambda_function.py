# webhook_processor Lambda function (SQS triggered)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)
# MATCH_ACTIVITY_LAMBDA_ARN (optional, for trail matching)
#
# This Lambda is triggered by SQS messages from the webhook handler.
# It processes Strava webhook events asynchronously:
# - Fetches activity details from Strava API
# - Updates the activities table in the database
# - Updates leaderboard aggregations
# - Handles token refresh if needed
# - Implements idempotency to avoid duplicate processing

import os
import json
import time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import boto3

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")
lambda_client = boto3.client("lambda")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
MATCH_ACTIVITY_LAMBDA_ARN = os.environ.get("MATCH_ACTIVITY_LAMBDA_ARN", "")

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITY_URL = "https://www.strava.com/api/v3/activities"

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


def store_activity(athlete_id, activity):
    """Store or update activity in database, returns activity_id if successful"""
    strava_activity_id = activity.get("id")
    if not strava_activity_id:
        print(f"ERROR: Activity missing id: {activity}")
        return None
    
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
    
    # Insert or update activity and return the activity ID
    sql = """
    INSERT INTO activities (
        athlete_id, strava_activity_id, name, distance, moving_time, elapsed_time,
        total_elevation_gain, type, start_date, start_date_local, timezone, polyline, updated_at
    )
    VALUES (:aid, :sid, :name, :dist, :mt, :et, :elev, :type, CAST(:sd AS TIMESTAMP), CAST(:sdl AS TIMESTAMP), :tz, :poly, now())
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
    RETURNING id
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
        result = _exec_sql(sql, params)
        # Get the returned activity ID
        records = result.get("records", [])
        if records:
            activity_id = int(records[0][0].get("longValue", 0))
            print(f"Successfully stored activity {strava_activity_id}: {name} (id={activity_id})")
            return activity_id
        else:
            print(f"WARNING: Activity stored but no ID returned for {strava_activity_id}")
            return None
    except Exception as e:
        print(f"ERROR: Failed to store activity {strava_activity_id}: {e}")
        return None


def delete_activity(athlete_id, strava_activity_id):
    """Delete activity from database"""
    sql = "DELETE FROM activities WHERE athlete_id = :aid AND strava_activity_id = :sid"
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "sid", "value": {"longValue": strava_activity_id}},
    ]
    
    try:
        _exec_sql(sql, params)
        print(f"Successfully deleted activity {strava_activity_id} for athlete {athlete_id}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to delete activity {strava_activity_id}: {e}")
        return False


def trigger_trail_matching(activity_id):
    """Trigger trail matching Lambda for an activity"""
    if not MATCH_ACTIVITY_LAMBDA_ARN:
        print("WARNING: MATCH_ACTIVITY_LAMBDA_ARN not configured, skipping trail matching")
        return False
    
    try:
        payload = json.dumps({"activity_id": activity_id})
        response = lambda_client.invoke(
            FunctionName=MATCH_ACTIVITY_LAMBDA_ARN,
            InvocationType='Event',  # Async invocation
            Payload=payload
        )
        print(f"Triggered trail matching for activity {activity_id}: status {response['StatusCode']}")
        return True
    except Exception as e:
        print(f"WARNING: Failed to trigger trail matching for activity {activity_id}: {e}")
        # Don't fail the webhook processing if trail matching fails
        return False


def get_window_keys(activity_start_date_local):
    """
    Calculate window keys for current week, month, and year based on activity date.
    
    Args:
        activity_start_date_local: ISO 8601 timestamp string (e.g., "2026-02-15T10:30:00Z")
    
    Returns:
        Dict with 'week', 'month', 'year' keys containing window_key strings
    """
    try:
        # Parse ISO 8601 timestamp
        dt = datetime.fromisoformat(activity_start_date_local.replace('Z', '+00:00'))
        
        # Week: ISO week format, Monday is start of week
        # Window key format: week_YYYY-MM-DD (Monday of the week)
        # Get Monday of the current week
        days_since_monday = dt.weekday()  # Monday is 0
        monday = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if days_since_monday > 0:
            monday = monday - timedelta(days=days_since_monday)
        week_key = f"week_{monday.strftime('%Y-%m-%d')}"
        
        # Month: YYYY-MM
        month_key = f"month_{dt.strftime('%Y-%m')}"
        
        # Year: YYYY
        year_key = f"year_{dt.strftime('%Y')}"
        
        return {
            'week': week_key,
            'month': month_key,
            'year': year_key
        }
    except Exception as e:
        print(f"ERROR: Failed to parse activity date {activity_start_date_local}: {e}")
        return None


def check_user_leaderboard_opt_in(athlete_id):
    """Check if user has opted in to leaderboards (show_on_leaderboards = true)"""
    sql = "SELECT show_on_leaderboards FROM users WHERE athlete_id = :aid"
    params = [{"name": "aid", "value": {"longValue": athlete_id}}]
    
    try:
        result = _exec_sql(sql, params)
        records = result.get("records", [])
        if not records:
            print(f"User {athlete_id} not found in database")
            return False
        
        # Get boolean value - handle both booleanValue and stringValue
        field = records[0][0]
        if "booleanValue" in field:
            return field["booleanValue"]
        elif "stringValue" in field:
            return field["stringValue"].lower() in ('true', 't', '1')
        
        # Default to False if field is NULL or unexpected type
        return False
    except Exception as e:
        print(f"ERROR: Failed to check leaderboard opt-in for user {athlete_id}: {e}")
        # Default to False on error - safer to not include than to include incorrectly
        return False


def update_leaderboard_aggregates(athlete_id, activity):
    """
    Update leaderboard aggregates for an activity (create or update).
    Increments aggregate values for current week, month, and year.
    
    Args:
        athlete_id: The athlete ID
        activity: The activity dict from Strava API
    
    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    print(f"TELEMETRY - leaderboard_agg_update_start athlete_id={athlete_id} activity_id={activity.get('id')}")
    
    try:
        # Check if user has opted in to leaderboards
        if not check_user_leaderboard_opt_in(athlete_id):
            print(f"User {athlete_id} has opted out of leaderboards, skipping aggregation")
            return True  # Not an error, just skip
        
        # Extract activity data
        strava_activity_id = activity.get("id")
        distance = float(activity.get("distance", 0))  # meters
        start_date_local = activity.get("start_date_local", "")
        activity_type = activity.get("type", "")
        
        if not start_date_local:
            print(f"WARNING: Activity {strava_activity_id} has no start_date_local, skipping aggregation")
            return True
        
        # Calculate window keys
        window_keys = get_window_keys(start_date_local)
        if not window_keys:
            print(f"WARNING: Failed to calculate window keys for activity {strava_activity_id}")
            return True
        
        # Track distance metric
        metric = "distance"
        
        # Determine aggregate activity types to update
        # Map Strava activity types to aggregate categories
        agg_types = ["all"]  # Always update 'all'
        if activity_type in ["Run", "Walk"]:
            agg_types.append("foot")
        elif activity_type == "Ride":
            agg_types.append("bike")
        
        # First, check if this activity was already counted in aggregates
        # We need to get the old distance to adjust the aggregates properly
        check_sql = """
        SELECT distance FROM activities 
        WHERE athlete_id = :aid AND strava_activity_id = :sid
        """
        check_params = [
            {"name": "aid", "value": {"longValue": athlete_id}},
            {"name": "sid", "value": {"longValue": strava_activity_id}},
        ]
        check_result = _exec_sql(check_sql, check_params)
        
        old_distance = 0
        if check_result.get("records"):
            old_dist_field = check_result["records"][0][0]
            if "doubleValue" in old_dist_field:
                old_distance = float(old_dist_field["doubleValue"])
            elif "stringValue" in old_dist_field:
                old_distance = float(old_dist_field["stringValue"])
        
        # Calculate delta (new distance - old distance)
        # For new activities, old_distance is 0
        # For updates, we adjust by the difference
        distance_delta = distance - old_distance
        
        # Update aggregates for each window (week, month, year) and each activity type
        for window, window_key in window_keys.items():
            for agg_activity_type in agg_types:
                sql = """
                INSERT INTO leaderboard_agg ("window", window_key, metric, activity_type, athlete_id, value, last_updated)
                VALUES (:window, :window_key, :metric, :act_type, :aid, :value, now())
                ON CONFLICT (window_key, metric, activity_type, athlete_id)
                DO UPDATE SET
                    value = leaderboard_agg.value + EXCLUDED.value,
                    last_updated = now()
                """
                
                params = [
                    {"name": "window", "value": {"stringValue": window}},
                    {"name": "window_key", "value": {"stringValue": window_key}},
                    {"name": "metric", "value": {"stringValue": metric}},
                    {"name": "act_type", "value": {"stringValue": agg_activity_type}},
                    {"name": "aid", "value": {"longValue": athlete_id}},
                    {"name": "value", "value": {"doubleValue": distance_delta}},
                ]
                
                _exec_sql(sql, params)
                print(f"Updated leaderboard aggregate: {window_key} athlete={athlete_id} type={agg_activity_type} delta={distance_delta:.2f}m")
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"TELEMETRY - leaderboard_agg_update_complete athlete_id={athlete_id} activity_id={strava_activity_id} duration_ms={duration_ms:.2f}")
        return True
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"TELEMETRY - leaderboard_agg_error athlete_id={athlete_id} error={str(e)} duration_ms={duration_ms:.2f}")
        print(f"ERROR: Failed to update leaderboard aggregates for athlete {athlete_id}: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the entire webhook processing if leaderboard update fails
        return False


def delete_leaderboard_aggregates(athlete_id, strava_activity_id):
    """
    Remove activity contribution from leaderboard aggregates when activity is deleted.
    
    Args:
        athlete_id: The athlete ID
        strava_activity_id: The Strava activity ID being deleted
    
    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    print(f"TELEMETRY - leaderboard_agg_delete_start athlete_id={athlete_id} activity_id={strava_activity_id}")
    
    try:
        # Check if user has opted in to leaderboards
        if not check_user_leaderboard_opt_in(athlete_id):
            print(f"User {athlete_id} has opted out of leaderboards, no aggregates to delete")
            return True
        
        # Get the activity details before deletion to know what to subtract
        sql = "SELECT distance, start_date_local, type FROM activities WHERE athlete_id = :aid AND strava_activity_id = :sid"
        params = [
            {"name": "aid", "value": {"longValue": athlete_id}},
            {"name": "sid", "value": {"longValue": strava_activity_id}},
        ]
        result = _exec_sql(sql, params)
        
        records = result.get("records", [])
        if not records:
            print(f"Activity {strava_activity_id} not found, no aggregates to delete")
            return True
        
        # Extract distance, date, and type
        record = records[0]
        distance_field = record[0]
        distance = 0
        if "doubleValue" in distance_field:
            distance = float(distance_field["doubleValue"])
        elif "stringValue" in distance_field:
            distance = float(distance_field["stringValue"])
        
        start_date_local_field = record[1]
        start_date_local = start_date_local_field.get("stringValue", "")
        
        activity_type_field = record[2]
        activity_type = activity_type_field.get("stringValue", "")
        
        if not start_date_local:
            print(f"Activity {strava_activity_id} has no start_date_local, skipping aggregate deletion")
            return True
        
        # Calculate window keys
        window_keys = get_window_keys(start_date_local)
        if not window_keys:
            print(f"Failed to calculate window keys for activity {strava_activity_id}")
            return True
        
        # Determine which aggregate types to update
        metric = "distance"
        agg_types = ["all"]  # Always update 'all'
        if activity_type in ["Run", "Walk"]:
            agg_types.append("foot")
        elif activity_type == "Ride":
            agg_types.append("bike")
        
        # Subtract distance from each window aggregate for each activity type
        for window, window_key in window_keys.items():
            for agg_activity_type in agg_types:
                sql = """
                UPDATE leaderboard_agg
                SET value = value - :value, last_updated = now()
                WHERE window_key = :window_key AND metric = :metric AND activity_type = :act_type AND athlete_id = :aid
                """
                
                params = [
                    {"name": "value", "value": {"doubleValue": distance}},
                    {"name": "window_key", "value": {"stringValue": window_key}},
                    {"name": "metric", "value": {"stringValue": metric}},
                    {"name": "act_type", "value": {"stringValue": agg_activity_type}},
                    {"name": "aid", "value": {"longValue": athlete_id}},
                ]
                
                _exec_sql(sql, params)
                print(f"Deleted from leaderboard aggregate: {window_key} athlete={athlete_id} type={agg_activity_type} distance={distance:.2f}m")
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"TELEMETRY - leaderboard_agg_delete_complete athlete_id={athlete_id} activity_id={strava_activity_id} duration_ms={duration_ms:.2f}")
        return True
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"TELEMETRY - leaderboard_agg_delete_error athlete_id={athlete_id} error={str(e)} duration_ms={duration_ms:.2f}")
        print(f"ERROR: Failed to delete leaderboard aggregates for activity {strava_activity_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_idempotency(idempotency_key):
    """Check if event has already been processed"""
    sql = "SELECT processed_at FROM webhook_events WHERE idempotency_key = :key"
    params = [{"name": "key", "value": {"stringValue": idempotency_key}}]
    
    try:
        result = _exec_sql(sql, params)
        return len(result.get("records", [])) > 0
    except Exception as e:
        # If table doesn't exist yet, event hasn't been processed
        print(f"Idempotency check failed (table may not exist): {e}")
        return False


def mark_event_processed(idempotency_key, webhook_event):
    """Mark event as processed in database"""
    sql = """
    INSERT INTO webhook_events (
        idempotency_key, subscription_id, object_type, object_id, 
        aspect_type, owner_id, event_time, processed_at
    )
    VALUES (:key, :sub_id, :obj_type, :obj_id, :aspect, :owner, :evt_time, now())
    ON CONFLICT (idempotency_key) DO NOTHING
    """
    
    params = [
        {"name": "key", "value": {"stringValue": idempotency_key}},
        {"name": "sub_id", "value": {"longValue": int(webhook_event.get("subscription_id", 0))}},
        {"name": "obj_type", "value": {"stringValue": webhook_event.get("object_type", "")}},
        {"name": "obj_id", "value": {"longValue": int(webhook_event.get("object_id", 0))}},
        {"name": "aspect", "value": {"stringValue": webhook_event.get("aspect_type", "")}},
        {"name": "owner", "value": {"longValue": int(webhook_event.get("owner_id", 0))}},
        {"name": "evt_time", "value": {"longValue": int(webhook_event.get("event_time", 0))}},
    ]
    
    try:
        _exec_sql(sql, params)
        print(f"Marked event as processed: {idempotency_key}")
    except Exception as e:
        # If table doesn't exist, that's okay - we'll create it later
        print(f"WARNING: Failed to mark event as processed (table may not exist): {e}")


def process_webhook_event(webhook_event):
    """Process a single webhook event"""
    object_type = webhook_event.get("object_type")
    aspect_type = webhook_event.get("aspect_type")
    object_id = int(webhook_event.get("object_id", 0))
    owner_id = int(webhook_event.get("owner_id", 0))
    subscription_id = webhook_event.get("subscription_id")
    event_time = webhook_event.get("event_time")
    
    print(f"Processing webhook event: {object_type} {aspect_type} {object_id} for athlete {owner_id}")
    
    # Create idempotency key
    idempotency_key = f"{subscription_id}:{object_id}:{aspect_type}:{event_time}"
    
    # Check if already processed
    if check_idempotency(idempotency_key):
        print(f"Event already processed: {idempotency_key}")
        return True
    
    # Get user tokens
    access_token, refresh_token, expires_at = get_user_tokens(owner_id)
    
    if not access_token or not refresh_token:
        print(f"User {owner_id} not found or not connected to Strava")
        # Mark as processed to avoid retrying
        mark_event_processed(idempotency_key, webhook_event)
        return True
    
    # Check if token needs refresh
    current_time = int(time.time())
    if expires_at < current_time + TOKEN_REFRESH_BUFFER_SECONDS:
        print(f"Access token expired or expiring soon for athlete {owner_id}, refreshing...")
        try:
            access_token = refresh_access_token(owner_id, refresh_token)
        except Exception as e:
            print(f"ERROR: Token refresh failed: {e}")
            # Don't mark as processed, allow retry
            return False
    
    # Handle different event types
    success = False
    activity_id = None
    
    if aspect_type == "delete":
        # Delete from leaderboard aggregates first (before deleting activity record)
        delete_leaderboard_aggregates(owner_id, object_id)
        # Delete activity from database
        success = delete_activity(owner_id, object_id)
    elif aspect_type in ["create", "update"]:
        # Fetch activity details from Strava and store
        try:
            activity = fetch_activity_details(access_token, object_id)
            activity_id = store_activity(owner_id, activity)
            success = activity_id is not None
            
            # Update leaderboard aggregates for the activity
            if success:
                update_leaderboard_aggregates(owner_id, activity)
            
            # Trigger trail matching for the activity
            if success and activity_id:
                trigger_trail_matching(activity_id)
        except Exception as e:
            print(f"ERROR: Failed to fetch/store activity: {e}")
            # Don't mark as processed if fetch failed (might be temporary)
            return False
    else:
        print(f"Unknown aspect_type: {aspect_type}")
        success = True  # Mark as processed to avoid retrying unknown types
    
    # Mark event as processed
    if success:
        mark_event_processed(idempotency_key, webhook_event)
    
    return success


def handler(event, context):
    """
    Lambda handler triggered by SQS.
    Processes webhook events from the queue.
    """
    print(f"webhook_processor handler invoked")
    print(f"Event: {json.dumps(event, default=str)}")
    
    # Validate required environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        raise RuntimeError("Missing database configuration")
    
    # Process each SQS record
    records = event.get("Records", [])
    print(f"Processing {len(records)} SQS records")
    
    failed_records = []
    
    for record in records:
        try:
            # Parse webhook event from SQS message
            message_body = record.get("body", "{}")
            webhook_event = json.loads(message_body)
            
            print(f"Processing SQS record: {record.get('messageId')}")
            
            # Process the event
            success = process_webhook_event(webhook_event)
            
            if not success:
                print(f"Failed to process event: {webhook_event}")
                failed_records.append(record)
        except Exception as e:
            print(f"ERROR processing SQS record: {e}")
            import traceback
            traceback.print_exc()
            failed_records.append(record)
    
    # If any records failed, raise an exception to trigger retry
    if failed_records:
        print(f"{len(failed_records)} records failed processing")
        # SQS will retry based on queue configuration
        raise RuntimeError(f"Failed to process {len(failed_records)} records")
    
    print(f"Successfully processed all {len(records)} records")
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(records)})
    }
