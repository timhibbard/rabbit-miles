# rabbitmiles-update-user-settings (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)

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


def get_cors_headers():
    """Return CORS headers for cross-origin requests"""
    headers = {
        "Content-Type": "application/json",
    }
    origin = get_cors_origin()
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers


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
    print("UPDATE USER SETTINGS - START")
    print("=" * 80)
    
    cors_headers = get_cors_headers()
    
    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        print("LOG - OPTIONS preflight request")
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Access-Control-Allow-Methods": "PATCH, OPTIONS",
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
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        if not APP_SECRET:
            print("ERROR - Missing APP_SECRET")
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        # Verify session (any authenticated user can update their own settings)
        print("LOG - Verifying session")
        token = admin_utils.parse_session_cookie(event)
        if not token:
            print("ERROR - Not authenticated")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        athlete_id = admin_utils.verify_session_token(token, APP_SECRET)
        if not athlete_id:
            print("ERROR - Invalid session")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        
        print(f"LOG - User {athlete_id} authenticated successfully")
        
        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                print("ERROR - Invalid JSON in request body")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "invalid JSON"})
                }
        
        # Get showOnLeaderboards value from request
        show_on_leaderboards = body.get("show_on_leaderboards")
        
        if show_on_leaderboards is None:
            print("ERROR - Missing show_on_leaderboards field")
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "show_on_leaderboards field required"})
            }
        
        # Validate boolean value
        if not isinstance(show_on_leaderboards, bool):
            print(f"ERROR - Invalid show_on_leaderboards value: {show_on_leaderboards}")
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "show_on_leaderboards must be a boolean"})
            }
        
        print(f"LOG - Updating show_on_leaderboards to {show_on_leaderboards} for user {athlete_id}")
        
        # Update user settings
        sql = """
        UPDATE users
        SET show_on_leaderboards = :show_on_leaderboards, updated_at = now()
        WHERE athlete_id = :athlete_id
        RETURNING show_on_leaderboards
        """
        
        params = [
            {"name": "show_on_leaderboards", "value": {"booleanValue": show_on_leaderboards}},
            {"name": "athlete_id", "value": {"longValue": athlete_id}},
        ]
        
        result = exec_sql(sql, params)
        records = result.get("records", [])
        
        if not records:
            print(f"ERROR - User {athlete_id} not found")
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "user not found"})
            }
        
        # Get updated value
        updated_value = records[0][0].get("booleanValue", False)
        
        print(f"LOG - Successfully updated show_on_leaderboards to {updated_value} for user {athlete_id}")
        print("=" * 80)
        print("UPDATE USER SETTINGS - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "success": True,
                "show_on_leaderboards": updated_value
            })
        }
        
    except Exception as e:
        print(f"CRITICAL ERROR - Unexpected exception in /user/settings handler")
        print(f"ERROR - Exception type: {type(e).__name__}")
        print(f"ERROR - Exception message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("UPDATE USER SETTINGS - FAILED")
        print("=" * 80)
        
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
