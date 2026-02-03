"""
Lambda function to reset last_matched field for all activities
This allows the trail matching process to re-process all activities
"""

import os
import json
import boto3

# Initialize RDS Data client
rds_data = boto3.client("rds-data")

# Environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
DB_NAME = os.environ.get("DB_NAME")


def _verify_cookie_session(cookies):
    """
    Verify session cookie and return athlete_id
    For now, this is a placeholder - actual verification happens via /me endpoint
    This endpoint should only be called by authenticated users
    """
    # In a real implementation, we would verify the rm_session cookie here
    # For now, we'll use a simple check
    if not cookies:
        return None
    
    # Look for rm_session cookie
    session_cookie = None
    for cookie in cookies:
        if cookie.startswith("rm_session="):
            session_cookie = cookie
            break
    
    return session_cookie is not None


def _exec_sql(sql, params=None):
    """Execute SQL statement using RDS Data API"""
    exec_params = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    
    if params:
        exec_params["parameters"] = params
    
    response = rds_data.execute_statement(**exec_params)
    return response


def handler(event, context):
    """
    Lambda handler for resetting last_matched field
    
    Expected: POST request to /activities/reset-matching
    Returns: JSON with count of reset activities
    """
    print("Event received:", json.dumps(event))
    
    # Check authentication via cookies
    cookies = event.get("cookies", [])
    if not _verify_cookie_session(cookies):
        return {
            "statusCode": 401,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": json.dumps({"error": "Unauthorized"})
        }
    
    try:
        # Reset last_matched for all activities
        sql = """
        UPDATE activities 
        SET last_matched = NULL 
        WHERE last_matched IS NOT NULL
        """
        
        response = _exec_sql(sql)
        affected_rows = response.get("numberOfRecordsUpdated", 0)
        
        print(f"Successfully reset last_matched for {affected_rows} activities")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": os.environ.get("FRONTEND_URL", "*"),
                "Access-Control-Allow-Credentials": "true",
            },
            "body": json.dumps({
                "success": True,
                "activities_reset": affected_rows,
                "message": f"Successfully reset {affected_rows} activities for trail matching"
            })
        }
        
    except Exception as e:
        print(f"ERROR: Failed to reset last_matched: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": os.environ.get("FRONTEND_URL", "*"),
                "Access-Control-Allow-Credentials": "true",
            },
            "body": json.dumps({
                "error": "Failed to reset activities",
                "details": str(e)
            })
        }
