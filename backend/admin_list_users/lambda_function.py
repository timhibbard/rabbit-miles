# rabbitmiles-admin-list-users (API Gateway HTTP API -> Lambda proxy)
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


def handler(event, context):
    print("=" * 80)
    print("ADMIN LIST USERS - START")
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
                "/admin/users",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {athlete_id} authenticated successfully")
        admin_utils.audit_log_admin_action(
            athlete_id,
            "/admin/users",
            "list_users",
            {}
        )
        
        # Query all users from database (exclude sensitive tokens)
        print("LOG - Querying all users from database")
        sql = """
        SELECT 
            athlete_id,
            display_name,
            profile_picture,
            created_at,
            updated_at
        FROM users
        ORDER BY created_at DESC
        """
        
        result = exec_sql(sql)
        records = result.get("records", [])
        print(f"LOG - Found {len(records)} users")
        
        # Compute trail statistics for all athletes in a single query
        # Using same time period logic as dashboard (current week starting Monday, current calendar month, current calendar year)
        print("LOG - Computing trail statistics for all athletes")
        stats_sql = """
        WITH time_periods AS (
            SELECT 
                -- Start of week (Monday) - matches dashboard logic
                -- If Sunday (DOW=0), go back 6 days; otherwise go back (DOW-1) days
                DATE_TRUNC('day', NOW() - INTERVAL '1 day' * 
                    CASE 
                        WHEN EXTRACT(DOW FROM NOW()) = 0 THEN 6 
                        ELSE EXTRACT(DOW FROM NOW()) - 1 
                    END
                ) as start_of_week,
                -- Start of current month
                DATE_TRUNC('month', NOW()) as start_of_month,
                -- Start of current year
                DATE_TRUNC('year', NOW()) as start_of_year
        )
        SELECT 
            athlete_id,
            -- Total
            COALESCE(SUM(distance_on_trail), 0) as total_distance,
            COALESCE(SUM(time_on_trail), 0) as total_time,
            -- This week (current week starting Monday)
            COALESCE(SUM(CASE 
                WHEN start_date_local >= (SELECT start_of_week FROM time_periods)
                THEN distance_on_trail 
                ELSE 0 
            END), 0) as week_distance,
            COALESCE(SUM(CASE 
                WHEN start_date_local >= (SELECT start_of_week FROM time_periods)
                THEN time_on_trail 
                ELSE 0 
            END), 0) as week_time,
            -- This month (current calendar month)
            COALESCE(SUM(CASE 
                WHEN start_date_local >= (SELECT start_of_month FROM time_periods)
                THEN distance_on_trail 
                ELSE 0 
            END), 0) as month_distance,
            COALESCE(SUM(CASE 
                WHEN start_date_local >= (SELECT start_of_month FROM time_periods)
                THEN time_on_trail 
                ELSE 0 
            END), 0) as month_time,
            -- This year (current calendar year)
            COALESCE(SUM(CASE 
                WHEN start_date_local >= (SELECT start_of_year FROM time_periods)
                THEN distance_on_trail 
                ELSE 0 
            END), 0) as year_distance,
            COALESCE(SUM(CASE 
                WHEN start_date_local >= (SELECT start_of_year FROM time_periods)
                THEN time_on_trail 
                ELSE 0 
            END), 0) as year_time
        FROM activities
        CROSS JOIN time_periods
        WHERE distance_on_trail IS NOT NULL
            AND time_on_trail IS NOT NULL
        GROUP BY athlete_id
        """
        
        stats_result = exec_sql(stats_sql)
        stats_records = stats_result.get("records", [])
        print(f"LOG - Computed statistics for {len(stats_records)} athletes")
        
        # Build a map of athlete_id to stats
        stats_map = {}
        for stats_rec in stats_records:
            athlete_id = stats_rec[0].get("longValue") if stats_rec[0].get("longValue") is not None else int(stats_rec[0].get("stringValue", 0))
            stats_map[athlete_id] = {
                "total_distance": float(stats_rec[1].get("stringValue", 0)) if stats_rec[1].get("stringValue") else 0,
                "total_time": stats_rec[2].get("longValue", 0) if stats_rec[2].get("longValue") is not None else 0,
                "week_distance": float(stats_rec[3].get("stringValue", 0)) if stats_rec[3].get("stringValue") else 0,
                "week_time": stats_rec[4].get("longValue", 0) if stats_rec[4].get("longValue") is not None else 0,
                "month_distance": float(stats_rec[5].get("stringValue", 0)) if stats_rec[5].get("stringValue") else 0,
                "month_time": stats_rec[6].get("longValue", 0) if stats_rec[6].get("longValue") is not None else 0,
                "year_distance": float(stats_rec[7].get("stringValue", 0)) if stats_rec[7].get("stringValue") else 0,
                "year_time": stats_rec[8].get("longValue", 0) if stats_rec[8].get("longValue") is not None else 0,
            }
        
        # Transform records to JSON-friendly format and attach stats
        users = []
        for rec in records:
            athlete_id = rec[0].get("longValue") if rec[0].get("longValue") is not None else int(rec[0].get("stringValue", 0))
            
            # Get stats for this athlete (default to zeros if none found)
            stats = stats_map.get(athlete_id, {
                "total_distance": 0, "total_time": 0, "week_distance": 0, "week_time": 0, 
                "month_distance": 0, "month_time": 0, "year_distance": 0, "year_time": 0
            })
            
            user = {
                "athlete_id": athlete_id,
                "display_name": rec[1].get("stringValue", ""),
                "profile_picture": rec[2].get("stringValue") if rec[2].get("stringValue") else None,
                "created_at": rec[3].get("stringValue", ""),
                "updated_at": rec[4].get("stringValue", ""),
                "stats": stats
            }
            users.append(user)
        
        print(f"LOG - Returning {len(users)} users")
        print("=" * 80)
        print("ADMIN LIST USERS - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "users": users,
                "count": len(users)
            })
        }
    
    except Exception as e:
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("ADMIN LIST USERS - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
