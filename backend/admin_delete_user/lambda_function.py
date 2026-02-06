# rabbitmiles-admin-delete-user (API Gateway HTTP API -> Lambda proxy)
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
    print("ADMIN DELETE USER - START")
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
                "Access-Control-Allow-Methods": "DELETE, OPTIONS",
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
                "delete_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        # Extract target athlete_id from path parameters
        path_params = event.get("pathParameters") or {}
        target_athlete_id_str = path_params.get("athlete_id")
        
        if not target_athlete_id_str:
            print("ERROR - Missing athlete_id in path")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "athlete_id required"})
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
        
        print(f"LOG - Admin {athlete_id} requesting deletion of user {target_athlete_id}")
        
        # Check if user exists
        print(f"LOG - Checking if user {target_athlete_id} exists")
        check_sql = "SELECT athlete_id, display_name FROM users WHERE athlete_id = :athlete_id"
        check_params = [{"name": "athlete_id", "value": {"longValue": target_athlete_id}}]
        check_result = exec_sql(check_sql, check_params)
        
        if not check_result.get("records"):
            print(f"ERROR - User {target_athlete_id} not found")
            admin_utils.audit_log_admin_action(
                athlete_id,
                f"/admin/users/{target_athlete_id}",
                "delete_failed",
                {"reason": "user not found", "target_athlete_id": target_athlete_id}
            )
            return {
                "statusCode": 404,
                "headers": headers,
                "body": json.dumps({"error": "user not found"})
            }
        
        user_record = check_result["records"][0]
        display_name = user_record[1].get("stringValue", "")
        print(f"LOG - Found user: {display_name} ({target_athlete_id})")
        
        # Delete activities first (due to foreign key constraint)
        print(f"LOG - Deleting activities for user {target_athlete_id}")
        delete_activities_sql = "DELETE FROM activities WHERE athlete_id = :athlete_id"
        delete_activities_params = [{"name": "athlete_id", "value": {"longValue": target_athlete_id}}]
        activities_result = exec_sql(delete_activities_sql, delete_activities_params)
        activities_deleted = activities_result.get("numberOfRecordsUpdated", 0)
        print(f"LOG - Deleted {activities_deleted} activities")
        
        # Delete user record
        print(f"LOG - Deleting user {target_athlete_id}")
        delete_user_sql = "DELETE FROM users WHERE athlete_id = :athlete_id"
        delete_user_params = [{"name": "athlete_id", "value": {"longValue": target_athlete_id}}]
        user_result = exec_sql(delete_user_sql, delete_user_params)
        users_deleted = user_result.get("numberOfRecordsUpdated", 0)
        print(f"LOG - Deleted {users_deleted} user record")
        
        # Audit log the successful deletion
        admin_utils.audit_log_admin_action(
            athlete_id,
            f"/admin/users/{target_athlete_id}",
            "delete_success",
            {
                "target_athlete_id": target_athlete_id,
                "display_name": display_name,
                "activities_deleted": activities_deleted,
                "users_deleted": users_deleted
            }
        )
        
        print(f"LOG - Successfully deleted user {target_athlete_id} and {activities_deleted} activities")
        print("=" * 80)
        print("ADMIN DELETE USER - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "success": True,
                "deleted": {
                    "athlete_id": target_athlete_id,
                    "display_name": display_name,
                    "activities_count": activities_deleted
                }
            })
        }
    
    except Exception as e:
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("ADMIN DELETE USER - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
