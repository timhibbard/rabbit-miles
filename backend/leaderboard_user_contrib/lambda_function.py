# rabbitmiles-leaderboard-user-contrib (API Gateway HTTP API -> Lambda proxy)
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


def get_window_date_range(window):
    """Calculate the date range for a given window type (current period)"""
    now = datetime.utcnow()
    
    if window == "week":
        # Get Monday of the current week
        days_since_monday = now.weekday()  # Monday is 0
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if days_since_monday > 0:
            start_date = start_date - timedelta(days=days_since_monday)
        # End date is Sunday (6 days after Monday)
        end_date = start_date + timedelta(days=7)
        return start_date, end_date
    
    elif window == "month":
        # First day of current month
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # First day of next month
        if now.month == 12:
            end_date = start_date.replace(year=now.year + 1, month=1)
        else:
            end_date = start_date.replace(month=now.month + 1)
        return start_date, end_date
    
    elif window == "year":
        # First day of current year
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        # First day of next year
        end_date = start_date.replace(year=now.year + 1)
        return start_date, end_date
    
    else:
        return None, None


def query_contributing_activities(athlete_id, window):
    """Query activities that contributed to the user's leaderboard aggregate for the given window"""
    start_date, end_date = get_window_date_range(window)
    
    if not start_date or not end_date:
        print(f"ERROR - Invalid window: {window}")
        return []
    
    print(f"LOG - Querying activities for athlete {athlete_id}, window={window}")
    print(f"LOG - Date range: {start_date.isoformat()} to {end_date.isoformat()}")
    
    sql = """
    SELECT 
        id,
        strava_activity_id,
        name,
        distance,
        moving_time,
        elapsed_time,
        total_elevation_gain,
        type,
        start_date,
        start_date_local,
        timezone
    FROM activities
    WHERE athlete_id = :athlete_id
      AND start_date_local >= :start_date
      AND start_date_local < :end_date
    ORDER BY start_date_local DESC
    """
    
    params = [
        {"name": "athlete_id", "value": {"longValue": athlete_id}},
        {"name": "start_date", "value": {"stringValue": start_date.isoformat()}},
        {"name": "end_date", "value": {"stringValue": end_date.isoformat()}},
    ]
    
    result = exec_sql(sql, params)
    records = result.get("records", [])
    
    # Parse results
    activities = []
    for record in records:
        activity_id = int(record[0].get("longValue", 0))
        strava_activity_id = int(record[1].get("longValue", 0))
        name = record[2].get("stringValue", "")
        distance = float(record[3].get("doubleValue", 0))
        moving_time = int(record[4].get("longValue", 0))
        elapsed_time = int(record[5].get("longValue", 0))
        elevation_gain = float(record[6].get("doubleValue", 0))
        activity_type = record[7].get("stringValue", "")
        start_date = record[8].get("stringValue", "")
        start_date_local = record[9].get("stringValue", "")
        timezone = record[10].get("stringValue", "") if not record[10].get("isNull") else ""
        
        activities.append({
            "id": activity_id,
            "strava_activity_id": strava_activity_id,
            "name": name,
            "distance": distance,
            "moving_time": moving_time,
            "elapsed_time": elapsed_time,
            "total_elevation_gain": elevation_gain,
            "type": activity_type,
            "start_date": start_date,
            "start_date_local": start_date_local,
            "timezone": timezone
        })
    
    return activities


def handler(event, context):
    print("=" * 80)
    print("LEADERBOARD USER CONTRIB - START")
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
                "Access-Control-Allow-Methods": "GET, OPTIONS",
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
        admin_athlete_id, is_admin = admin_utils.verify_admin_session(event, APP_SECRET)
        
        if not admin_athlete_id:
            print("ERROR - Not authenticated")
            return {
                "statusCode": 401,
                "headers": headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        if not is_admin:
            print(f"ERROR - User {admin_athlete_id} is not an admin")
            admin_utils.audit_log_admin_action(
                admin_athlete_id,
                "/users/:id/leaderboard_contrib",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {admin_athlete_id} authenticated successfully")
        
        # Get path parameters
        path_params = event.get("pathParameters") or {}
        user_id = path_params.get("id")
        
        if not user_id:
            print("ERROR - Missing user ID path parameter")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "user ID required"})
            }
        
        try:
            athlete_id = int(user_id)
        except ValueError:
            print(f"ERROR - Invalid user ID: {user_id}")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "invalid user ID"})
            }
        
        # Get query parameters
        query_params = event.get("queryStringParameters") or {}
        window = query_params.get("window")  # Required: week, month, year
        
        # Validate window parameter
        if not window or window not in ["week", "month", "year"]:
            print(f"ERROR - Invalid or missing window parameter: {window}")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "window parameter required (week, month, or year)"})
            }
        
        print(f"LOG - Querying contributing activities for user {athlete_id}, window={window}")
        
        # Audit log
        admin_utils.audit_log_admin_action(
            admin_athlete_id,
            f"/users/{athlete_id}/leaderboard_contrib",
            "view_user_contrib",
            {
                "athlete_id": athlete_id,
                "window": window
            }
        )
        
        # Query contributing activities
        activities = query_contributing_activities(athlete_id, window)
        
        # Calculate total distance
        total_distance = sum(act["distance"] for act in activities)
        
        # Build response
        response_data = {
            "athlete_id": athlete_id,
            "window": window,
            "activities": activities,
            "total_distance": total_distance,
            "total_activities": len(activities)
        }
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"LOG - Query completed in {duration_ms:.2f}ms")
        print(f"LOG - Returned {len(activities)} activities, total_distance={total_distance:.2f}m")
        print("=" * 80)
        print("LEADERBOARD USER CONTRIB - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(response_data)
        }
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"CRITICAL ERROR - Unexpected exception in /users/:id/leaderboard_contrib handler")
        print(f"ERROR - Exception type: {type(e).__name__}")
        print(f"ERROR - Exception message: {str(e)}")
        print(f"ERROR - Duration: {duration_ms:.2f}ms")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("LEADERBOARD USER CONTRIB - FAILED")
        print("=" * 80)
        
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
