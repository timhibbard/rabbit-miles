# rabbitmiles-leaderboard-get (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Public endpoint - no authentication required (but shows user's rank if logged in)
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for optional session verification)
# FRONTEND_URL (for CORS)

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


def get_current_window_key(window):
    """Get the current window key for the specified window type"""
    now = datetime.utcnow()
    
    if window == "week":
        # Get Monday of the current week
        days_since_monday = now.weekday()  # Monday is 0
        monday = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if days_since_monday > 0:
            monday = monday - timedelta(days=days_since_monday)
        return f"week_{monday.strftime('%Y-%m-%d')}"
    
    elif window == "month":
        return f"month_{now.strftime('%Y-%m')}"
    
    elif window == "year":
        return f"year_{now.strftime('%Y')}"
    
    else:
        return None


def get_previous_window_key(window, current_window_key):
    """Calculate the previous window key for a given window type"""
    try:
        if window == "week":
            # Extract date from current week key: "week_2026-02-09"
            date_str = current_window_key.split('_')[1]
            current_monday = datetime.strptime(date_str, '%Y-%m-%d')
            # Previous week is 7 days before
            previous_monday = current_monday - timedelta(days=7)
            return f"week_{previous_monday.strftime('%Y-%m-%d')}"
        
        elif window == "month":
            # Extract year and month from current month key: "month_2026-02"
            year_month = current_window_key.split('_')[1]
            year, month = map(int, year_month.split('-'))
            # Previous month
            if month == 1:
                prev_year, prev_month = year - 1, 12
            else:
                prev_year, prev_month = year, month - 1
            return f"month_{prev_year:04d}-{prev_month:02d}"
        
        elif window == "year":
            # Extract year from current year key: "year_2026"
            year_str = current_window_key.split('_')[1]
            year = int(year_str)
            return f"year_{year - 1}"
        
        else:
            return None
    except Exception as e:
        print(f"ERROR: Failed to calculate previous window key: {e}")
        return None


def query_leaderboard(window_key, metric, activity_type, limit, offset):
    """Query leaderboard rankings for a given window"""
    sql = """
    SELECT 
        l.athlete_id,
        u.display_name,
        u.profile_picture,
        l.value,
        l.last_updated
    FROM leaderboard_agg l
    JOIN users u ON l.athlete_id = u.athlete_id
    WHERE l.window_key = :window_key
      AND l.metric = :metric
      AND l.activity_type = :activity_type
      AND u.show_on_leaderboards = true
    ORDER BY l.value DESC
    LIMIT :limit OFFSET :offset
    """
    
    params = [
        {"name": "window_key", "value": {"stringValue": window_key}},
        {"name": "metric", "value": {"stringValue": metric}},
        {"name": "activity_type", "value": {"stringValue": activity_type}},
        {"name": "limit", "value": {"longValue": limit}},
        {"name": "offset", "value": {"longValue": offset}},
    ]
    
    result = exec_sql(sql, params)
    records = result.get("records", [])
    
    # Parse results
    rows = []
    for idx, record in enumerate(records):
        athlete_id = int(record[0].get("longValue", 0))
        display_name = record[1].get("stringValue", "")
        profile_picture = record[2].get("stringValue", "") if not record[2].get("isNull") else ""
        # NUMERIC fields are returned as stringValue by RDS Data API
        value_field = record[3]
        if "stringValue" in value_field:
            value = float(value_field["stringValue"])
        elif "doubleValue" in value_field:
            value = float(value_field["doubleValue"])
        else:
            value = 0.0
        last_updated = record[4].get("stringValue", "")
        
        rows.append({
            "rank": offset + idx + 1,
            "user": {
                "id": athlete_id,
                "display_name": display_name,
                "avatar_url": profile_picture
            },
            "value": value,
            "last_updated": last_updated
        })
    
    return rows


def get_user_rank(window_key, metric, activity_type, athlete_id):
    """Get the rank and value for a specific user"""
    sql = """
    WITH ranked_users AS (
        SELECT 
            l.athlete_id,
            l.value,
            ROW_NUMBER() OVER (ORDER BY l.value DESC) as rank
        FROM leaderboard_agg l
        JOIN users u ON l.athlete_id = u.athlete_id
        WHERE l.window_key = :window_key
          AND l.metric = :metric
          AND l.activity_type = :activity_type
          AND u.show_on_leaderboards = true
    )
    SELECT rank, value
    FROM ranked_users
    WHERE athlete_id = :athlete_id
    """
    
    params = [
        {"name": "window_key", "value": {"stringValue": window_key}},
        {"name": "metric", "value": {"stringValue": metric}},
        {"name": "activity_type", "value": {"stringValue": activity_type}},
        {"name": "athlete_id", "value": {"longValue": athlete_id}},
    ]
    
    result = exec_sql(sql, params)
    records = result.get("records", [])
    
    if not records:
        return None
    
    record = records[0]
    rank = int(record[0].get("longValue", 0))
    # NUMERIC fields are returned as stringValue by RDS Data API
    value_field = record[1]
    if "stringValue" in value_field:
        value = float(value_field["stringValue"])
    elif "doubleValue" in value_field:
        value = float(value_field["doubleValue"])
    else:
        value = 0.0
    
    return {
        "rank": rank,
        "value": value
    }


def get_total_athletes_count(window_key, metric, activity_type):
    """Get the total count of athletes on the leaderboard"""
    sql = """
    SELECT COUNT(*)
    FROM leaderboard_agg l
    JOIN users u ON l.athlete_id = u.athlete_id
    WHERE l.window_key = :window_key
      AND l.metric = :metric
      AND l.activity_type = :activity_type
      AND u.show_on_leaderboards = true
    """
    
    params = [
        {"name": "window_key", "value": {"stringValue": window_key}},
        {"name": "metric", "value": {"stringValue": metric}},
        {"name": "activity_type", "value": {"stringValue": activity_type}},
    ]
    
    result = exec_sql(sql, params)
    records = result.get("records", [])
    
    if not records:
        return 0
    
    record = records[0]
    count = int(record[0].get("longValue", 0))
    return count


def get_previous_top3(window_key, metric, activity_type):
    """Get top 3 users from the previous period"""
    rows = query_leaderboard(window_key, metric, activity_type, limit=3, offset=0)
    return rows


def handler(event, context):
    print("=" * 80)
    print("LEADERBOARD GET - START")
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
        
        # Verify session (optional - leaderboard is public but we show user's rank if logged in)
        print("LOG - Checking for session")
        athlete_id = None
        try:
            athlete_id, _ = admin_utils.verify_admin_session(event, APP_SECRET)
            if athlete_id:
                print(f"LOG - User {athlete_id} authenticated")
        except Exception as e:
            # Session verification failed, but that's OK - leaderboard is public
            print(f"LOG - No valid session found (this is OK): {e}")
        
        # Get query parameters
        query_params = event.get("queryStringParameters") or {}
        window = query_params.get("window")  # Required: week, month, year
        metric = query_params.get("metric", "distance")  # Default: distance
        activity_type = query_params.get("activity_type", "all")  # Default: all
        limit = int(query_params.get("limit", 50))
        offset = int(query_params.get("offset", 0))
        user_id = query_params.get("user_id")  # Optional: to get my_rank
        
        # Validate window parameter
        if not window or window not in ["week", "month", "year"]:
            print(f"ERROR - Invalid or missing window parameter: {window}")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "window parameter required (week, month, or year)"})
            }
        
        # Limit to reasonable values
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
        
        # Get current window key
        window_key = get_current_window_key(window)
        if not window_key:
            print(f"ERROR - Failed to calculate window key for window: {window}")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "failed to calculate window key"})
            }
        
        print(f"LOG - Querying leaderboard: window={window}, window_key={window_key}, metric={metric}, activity_type={activity_type}")
        print(f"LOG - Pagination: limit={limit}, offset={offset}")
        
        # Log telemetry
        if athlete_id:
            print(f"TELEMETRY - leaderboard_api_call user_id={athlete_id} window={window} metric={metric} activity_type={activity_type}")
        else:
            print(f"TELEMETRY - leaderboard_api_call anonymous window={window} metric={metric} activity_type={activity_type}")
        
        # Query leaderboard
        rows = query_leaderboard(window_key, metric, activity_type, limit, offset)
        
        # Get user's rank if user_id provided
        my_rank = None
        if user_id:
            try:
                user_id_int = int(user_id)
                my_rank = get_user_rank(window_key, metric, activity_type, user_id_int)
            except ValueError:
                print(f"WARNING - Invalid user_id parameter: {user_id}")
        
        # Get total athletes count
        total_athletes = get_total_athletes_count(window_key, metric, activity_type)
        print(f"LOG - Total athletes on leaderboard: {total_athletes}")
        
        # Get previous period top 3
        previous_window_key = get_previous_window_key(window, window_key)
        previous_top3 = []
        if previous_window_key:
            print(f"LOG - Querying previous period top 3: {previous_window_key}")
            previous_top3 = get_previous_top3(previous_window_key, metric, activity_type)
        
        # Calculate cursor for pagination (simple offset-based)
        cursor = None
        if len(rows) >= limit:
            cursor = str(offset + limit)
        
        # Build response
        response_data = {
            "rows": rows,
            "my_rank": my_rank,
            "previous_top3": previous_top3,
            "cursor": cursor,
            "window_key": window_key,
            "metric": metric,
            "activity_type": activity_type,
            "total_returned": len(rows),
            "total_athletes": total_athletes
        }
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"LOG - Leaderboard query completed in {duration_ms:.2f}ms")
        print(f"LOG - Returned {len(rows)} rows, previous_top3={len(previous_top3)}")
        print("=" * 80)
        print("LEADERBOARD GET - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(response_data)
        }
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"CRITICAL ERROR - Unexpected exception in /leaderboard handler")
        print(f"ERROR - Exception type: {type(e).__name__}")
        print(f"ERROR - Exception message: {str(e)}")
        print(f"ERROR - Duration: {duration_ms:.2f}ms")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("LEADERBOARD GET - FAILED")
        print("=" * 80)
        
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
