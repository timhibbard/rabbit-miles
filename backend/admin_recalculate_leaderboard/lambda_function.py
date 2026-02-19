# rabbitmiles-admin-recalculate-leaderboard (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)
# ADMIN_ATHLETE_IDS (comma-separated list of admin athlete IDs)

import os
import sys
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
import boto3

# Add parent directory to path to import admin_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import admin_utils

rds = boto3.client("rds-data")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

# Filter activities starting from Jan 1, 2026 00:00:00 UTC
RECALC_START_DATE = "2026-01-01 00:00:00"


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


def get_window_keys(activity_start_date_local):
    """
    Calculate window keys (week, month, year) for an activity based on its start date.
    
    Args:
        activity_start_date_local: ISO 8601 timestamp string (e.g., "2026-02-15T10:30:00Z")
    
    Returns:
        Dict with 'week', 'month', 'year' keys containing window_key strings
    """
    try:
        # Parse ISO 8601 timestamp (can be with or without timezone)
        dt_str = activity_start_date_local.replace('Z', '+00:00')
        if '+' not in dt_str and dt_str.count(':') == 2:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str)
        
        # Week: ISO week format, Monday is start of week
        # Window key format: week_YYYY-MM-DD (Monday of the week)
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


def recalculate_leaderboard():
    """
    Recalculate leaderboard_agg table from all activities since Jan 1, 2026.
    
    This function:
    1. Verifies leaderboard_agg table exists
    2. Clears existing leaderboard_agg data
    3. Queries all activities from users who have opted in
    4. Recalculates aggregates for week, month, and year windows
    
    Returns:
        Tuple of (activities_processed, athletes_processed, error_message)
    """
    print(f"=== recalculate_leaderboard START ===")
    print(f"LOG - Recalculating leaderboard aggregates from {RECALC_START_DATE}")
    
    try:
        # Step 0: Verify that leaderboard_agg table exists
        print("LOG - Checking if leaderboard_agg table exists")
        check_table_sql = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'leaderboard_agg'
        );
        """
        result = exec_sql(check_table_sql)
        records = result.get("records", [])
        
        # Safely extract the boolean value
        table_exists = False
        if records and len(records) > 0 and len(records[0]) > 0:
            table_exists = records[0][0].get("booleanValue", False)
        
        if not table_exists:
            error_msg = (
                "The leaderboard_agg table does not exist. "
                "Please run the database migration: backend/migrations/008_create_leaderboard_agg_table.sql"
            )
            print(f"ERROR: {error_msg}")
            return 0, 0, error_msg
        
        print("LOG - leaderboard_agg table exists")
        
        # Step 1: Clear existing leaderboard_agg data
        print("LOG - Clearing existing leaderboard_agg table")
        clear_sql = "DELETE FROM leaderboard_agg"
        exec_sql(clear_sql)
        print("LOG - Cleared leaderboard_agg table")
        
        # Step 2: Query all activities since Jan 1, 2026 for opted-in users
        print("LOG - Querying activities for opted-in users")
        activities_sql = """
        SELECT 
            a.athlete_id,
            a.strava_activity_id,
            a.distance_on_trail as distance,
            a.start_date_local,
            a.type
        FROM activities a
        JOIN users u ON a.athlete_id = u.athlete_id
        WHERE u.show_on_leaderboards = true
          AND a.start_date_local >= CAST(:start_date AS TIMESTAMP)
          AND a.distance_on_trail IS NOT NULL
        ORDER BY a.athlete_id, a.start_date_local
        """
        
        params = [
            {"name": "start_date", "value": {"stringValue": RECALC_START_DATE}}
        ]
        
        result = exec_sql(activities_sql, params)
        records = result.get("records", [])
        
        print(f"LOG - Found {len(records)} activities to process")
        
        if len(records) == 0:
            print("LOG - No activities found, nothing to recalculate")
            return 0, 0, None
        
        # Step 3: Process activities and build aggregates
        # Use a dict to accumulate values before inserting
        # Key: (window_key, metric, activity_type, athlete_id) -> value
        aggregates = {}
        
        activities_processed = 0
        athletes_seen = set()
        
        for record in records:
            athlete_id = int(record[0].get("longValue", 0))
            strava_activity_id = int(record[1].get("longValue", 0))
            
            # Distance can be NUMERIC which comes back as stringValue
            distance_field = record[2]
            if "doubleValue" in distance_field:
                distance = float(distance_field["doubleValue"])
            elif "stringValue" in distance_field:
                distance = float(distance_field["stringValue"])
            else:
                distance = 0.0
            
            start_date_local = record[3].get("stringValue", "")
            activity_type = record[4].get("stringValue", "")
            
            athletes_seen.add(athlete_id)
            
            # Calculate window keys
            window_keys = get_window_keys(start_date_local)
            if not window_keys:
                print(f"WARNING: Could not calculate window keys for activity {strava_activity_id}, skipping")
                continue
            
            # Determine aggregate activity types to update
            agg_types = ["all"]  # Always update 'all'
            if activity_type in ["Run", "Walk"]:
                agg_types.append("foot")
            elif activity_type == "Ride":
                agg_types.append("bike")
            
            # Accumulate distance for each window and activity type
            metric = "distance"
            for window, window_key in window_keys.items():
                for agg_activity_type in agg_types:
                    key = (window_key, metric, agg_activity_type, athlete_id)
                    aggregates[key] = aggregates.get(key, 0.0) + distance
            
            activities_processed += 1
            
            # Log progress every 100 activities
            if activities_processed % 100 == 0:
                print(f"LOG - Processed {activities_processed} activities...")
        
        print(f"LOG - Finished processing {activities_processed} activities")
        print(f"LOG - Found {len(athletes_seen)} unique athletes")
        print(f"LOG - Generated {len(aggregates)} aggregate entries")
        
        # Step 4: Insert aggregates into leaderboard_agg table
        print("LOG - Inserting aggregates into leaderboard_agg table")
        
        insert_count = 0
        for (window_key, metric, activity_type, athlete_id), value in aggregates.items():
            # Extract window type from window_key (e.g., "week_2026-02-09" -> "week")
            window = window_key.split('_')[0]
            
            insert_sql = """
            INSERT INTO leaderboard_agg ("window", window_key, metric, activity_type, athlete_id, value, last_updated)
            VALUES (:window, :window_key, :metric, :activity_type, :athlete_id, :value, now())
            ON CONFLICT (window_key, metric, activity_type, athlete_id)
            DO UPDATE SET
                "window" = EXCLUDED."window",
                value = EXCLUDED.value,
                last_updated = now()
            """
            
            insert_params = [
                {"name": "window", "value": {"stringValue": window}},
                {"name": "window_key", "value": {"stringValue": window_key}},
                {"name": "metric", "value": {"stringValue": metric}},
                {"name": "activity_type", "value": {"stringValue": activity_type}},
                {"name": "athlete_id", "value": {"longValue": athlete_id}},
                {"name": "value", "value": {"doubleValue": value}},
            ]
            
            exec_sql(insert_sql, insert_params)
            insert_count += 1
            
            # Log progress every 100 inserts
            if insert_count % 100 == 0:
                print(f"LOG - Inserted {insert_count} aggregates...")
        
        print(f"LOG - Inserted {insert_count} aggregate entries")
        print(f"=== recalculate_leaderboard END: SUCCESS ===")
        
        return activities_processed, len(athletes_seen), None
        
    except Exception as e:
        error = f"Recalculation failed: {e}"
        print(f"ERROR: {error}")
        import traceback
        traceback.print_exc()
        return 0, 0, error


def handler(event, context):
    print("=" * 80)
    print("ADMIN RECALCULATE LEADERBOARD - START")
    print("=" * 80)
    
    start_time = time.time()
    
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
                "/admin/leaderboard/recalculate",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {athlete_id} authenticated successfully")
        print("LOG - Starting leaderboard recalculation")
        
        # Audit log
        admin_utils.audit_log_admin_action(
            athlete_id,
            "/admin/leaderboard/recalculate",
            "recalculate_leaderboard",
            {"start_date": RECALC_START_DATE}
        )
        
        # Perform recalculation
        activities_processed, athletes_processed, error_message = recalculate_leaderboard()
        
        if error_message:
            print(f"ERROR - Recalculation failed: {error_message}")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": "recalculation failed",
                    "message": error_message
                })
            }
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"LOG - Recalculation successful in {duration_ms:.2f}ms")
        print(f"LOG - Processed {activities_processed} activities from {athletes_processed} athletes")
        print("=" * 80)
        print("ADMIN RECALCULATE LEADERBOARD - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "message": "Leaderboard recalculation completed successfully",
                "activities_processed": activities_processed,
                "athletes_processed": athletes_processed,
                "duration_ms": round(duration_ms, 2)
            })
        }
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {str(e)}")
        print(f"ERROR - Duration: {duration_ms:.2f}ms")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("ADMIN RECALCULATE LEADERBOARD - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
