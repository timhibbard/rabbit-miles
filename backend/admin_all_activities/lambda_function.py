# rabbitmiles-admin-all-activities (API Gateway HTTP API -> Lambda proxy)
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
    print("ADMIN ALL ACTIVITIES - START")
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
                "/admin/activities",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {athlete_id} authenticated successfully")
        print(f"LOG - Fetching activities for all users")
        admin_utils.audit_log_admin_action(
            athlete_id,
            "/admin/activities",
            "view_all_activities",
            {}
        )
        
        # Get pagination parameters
        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", 50))
        offset = int(query_params.get("offset", 0))
        
        # Limit to reasonable values
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
        
        # Query activities from database (all users, sorted by most recent)
        print(f"LOG - Querying all activities (limit={limit}, offset={offset})")
        sql = """
        SELECT 
            a.id,
            a.athlete_id,
            a.strava_activity_id,
            a.name,
            a.distance,
            a.moving_time,
            a.elapsed_time,
            a.total_elevation_gain,
            a.type,
            a.start_date,
            a.start_date_local,
            a.created_at,
            a.updated_at,
            a.time_on_trail,
            a.distance_on_trail,
            u.display_name as athlete_name
        FROM activities a
        LEFT JOIN users u ON a.athlete_id = u.athlete_id
        ORDER BY a.start_date_local DESC
        LIMIT :limit OFFSET :offset
        """
        
        params = [
            {"name": "limit", "value": {"longValue": limit}},
            {"name": "offset", "value": {"longValue": offset}},
        ]
        
        result = exec_sql(sql, params)
        records = result.get("records", [])
        print(f"LOG - Found {len(records)} activities")
        
        # Transform records to JSON-friendly format
        activities = []
        for rec in records:
            # Helper to parse numeric field that can be either doubleValue or stringValue
            def parse_numeric(field_rec, default=None):
                if field_rec.get("doubleValue") is not None:
                    return float(field_rec.get("doubleValue"))
                elif field_rec.get("stringValue"):
                    try:
                        return float(field_rec.get("stringValue"))
                    except (ValueError, TypeError):
                        return default
                return default
            
            # Helper to parse integer field that can be either longValue or stringValue
            def parse_integer(field_rec, default=None):
                long_val = field_rec.get("longValue")
                if long_val is not None:
                    return int(long_val)
                string_val = field_rec.get("stringValue")
                if string_val:
                    try:
                        return int(string_val)
                    except (ValueError, TypeError):
                        return default
                return default
            
            # Parse distance
            distance = parse_numeric(rec[4])
            
            # Handle trail time (can be null)
            time_on_trail = None
            if not rec[13].get("isNull"):
                time_on_trail_value = rec[13].get("longValue")
                if time_on_trail_value is not None:
                    time_on_trail = int(time_on_trail_value)
            
            # Parse trail distance (can be null)
            distance_on_trail = None
            if not rec[14].get("isNull"):
                distance_on_trail = parse_numeric(rec[14])
            
            # Parse other numeric fields
            moving_time_val = rec[5].get("longValue")
            elapsed_time_val = rec[6].get("longValue")
            elevation_val = rec[7].get("doubleValue")
            
            activity = {
                "id": parse_integer(rec[0], 0),
                "athlete_id": parse_integer(rec[1], 0),
                "strava_activity_id": parse_integer(rec[2], 0),
                "name": rec[3].get("stringValue", ""),
                "distance": distance,
                "moving_time": int(moving_time_val) if moving_time_val is not None else None,
                "elapsed_time": int(elapsed_time_val) if elapsed_time_val is not None else None,
                "total_elevation_gain": float(elevation_val) if elevation_val is not None else None,
                "type": rec[8].get("stringValue", ""),
                "start_date": rec[9].get("stringValue", ""),
                "start_date_local": rec[10].get("stringValue", ""),
                "created_at": rec[11].get("stringValue", ""),
                "updated_at": rec[12].get("stringValue", ""),
                "time_on_trail": time_on_trail,
                "distance_on_trail": distance_on_trail,
                "athlete_name": rec[15].get("stringValue", "Unknown"),
            }
            activities.append(activity)
        
        # Get total count
        count_sql = "SELECT COUNT(*) FROM activities"
        count_result = exec_sql(count_sql)
        total_count = int(count_result.get("records", [[{"longValue": 0}]])[0][0].get("longValue", 0))
        
        print(f"LOG - Returning {len(activities)} activities (total: {total_count})")
        print("=" * 80)
        print("ADMIN ALL ACTIVITIES - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "activities": activities,
                "count": len(activities),
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            })
        }
    
    except Exception as e:
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("ADMIN ALL ACTIVITIES - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
