# rabbitmiles-admin-user-activities (API Gateway HTTP API -> Lambda proxy)
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
    print("ADMIN USER ACTIVITIES - START")
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
                f"/admin/users/{target_athlete_id}/activities",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {athlete_id} authenticated successfully")
        print(f"LOG - Fetching activities for user {target_athlete_id}")
        admin_utils.audit_log_admin_action(
            athlete_id,
            f"/admin/users/{target_athlete_id}/activities",
            "view_user_activities",
            {"target_athlete_id": target_athlete_id}
        )
        
        # Get pagination parameters
        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", 50))
        offset = int(query_params.get("offset", 0))
        
        # Limit to reasonable values
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
        
        # Query activities from database
        print(f"LOG - Querying activities for athlete {target_athlete_id} (limit={limit}, offset={offset})")
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
            created_at,
            updated_at
        FROM activities
        WHERE athlete_id = :athlete_id
        ORDER BY start_date DESC
        LIMIT :limit OFFSET :offset
        """
        
        params = [
            {"name": "athlete_id", "value": {"longValue": target_athlete_id}},
            {"name": "limit", "value": {"longValue": limit}},
            {"name": "offset", "value": {"longValue": offset}},
        ]
        
        result = exec_sql(sql, params)
        records = result.get("records", [])
        print(f"LOG - Found {len(records)} activities")
        
        # Transform records to JSON-friendly format
        activities = []
        for rec in records:
            activity = {
                "id": rec[0].get("longValue") if rec[0].get("longValue") is not None else int(rec[0].get("stringValue", 0)),
                "strava_activity_id": rec[1].get("longValue") if rec[1].get("longValue") is not None else int(rec[1].get("stringValue", 0)),
                "name": rec[2].get("stringValue", ""),
                "distance": float(rec[3].get("doubleValue", 0)) if rec[3].get("doubleValue") is not None else None,
                "moving_time": int(rec[4].get("longValue", 0)) if rec[4].get("longValue") is not None else None,
                "elapsed_time": int(rec[5].get("longValue", 0)) if rec[5].get("longValue") is not None else None,
                "total_elevation_gain": float(rec[6].get("doubleValue", 0)) if rec[6].get("doubleValue") is not None else None,
                "type": rec[7].get("stringValue", ""),
                "start_date": rec[8].get("stringValue", ""),
                "start_date_local": rec[9].get("stringValue", ""),
                "created_at": rec[10].get("stringValue", ""),
                "updated_at": rec[11].get("stringValue", ""),
            }
            activities.append(activity)
        
        # Get total count
        count_sql = "SELECT COUNT(*) FROM activities WHERE athlete_id = :athlete_id"
        count_params = [{"name": "athlete_id", "value": {"longValue": target_athlete_id}}]
        count_result = exec_sql(count_sql, count_params)
        total_count = int(count_result.get("records", [[{"longValue": 0}]])[0][0].get("longValue", 0))
        
        print(f"LOG - Returning {len(activities)} activities (total: {total_count})")
        print("=" * 80)
        print("ADMIN USER ACTIVITIES - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "athlete_id": target_athlete_id,
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
        print("ADMIN USER ACTIVITIES - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
