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
import re
from urllib.parse import urlparse
from decimal import Decimal, InvalidOperation
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


def validate_email(email):
    """Validate email format"""
    if not email or not isinstance(email, str):
        return False
    if len(email) > 255:
        return False
    # Simple email regex - matches most valid emails
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


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
        
        # Get settings from request
        show_on_leaderboards = body.get("show_on_leaderboards")
        timezone = body.get("timezone")
        email = body.get("email")
        email_notifications_enabled = body.get("email_notifications_enabled")
        send_trail_milestone = body.get("send_trail_milestone")
        send_ranking_change = body.get("send_ranking_change")
        min_trail_distance_miles = body.get("min_trail_distance_miles")

        # At least one field must be provided
        if all(v is None for v in [show_on_leaderboards, timezone, email, email_notifications_enabled,
                                     send_trail_milestone, send_ranking_change, min_trail_distance_miles]):
            print("ERROR - No fields to update")
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "at least one field required"})
            }
        
        # Build dynamic UPDATE query
        set_clauses = []
        params = []
        
        # Validate and add show_on_leaderboards if provided
        if show_on_leaderboards is not None:
            if not isinstance(show_on_leaderboards, bool):
                print(f"ERROR - Invalid show_on_leaderboards value: {show_on_leaderboards}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "show_on_leaderboards must be a boolean"})
                }
            set_clauses.append("show_on_leaderboards = :show_on_leaderboards")
            params.append({"name": "show_on_leaderboards", "value": {"booleanValue": show_on_leaderboards}})
            print(f"LOG - Updating show_on_leaderboards to {show_on_leaderboards}")
        
        # Validate and add timezone if provided
        if timezone is not None:
            if not isinstance(timezone, str) or len(timezone) > 100:
                print(f"ERROR - Invalid timezone value: {timezone}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "timezone must be a string (max 100 chars)"})
                }
            set_clauses.append("timezone = :timezone")
            params.append({"name": "timezone", "value": {"stringValue": timezone}})
            print(f"LOG - Updating timezone to {timezone}")

        # Validate and add email if provided
        email_changed = False
        if email is not None:
            if not validate_email(email):
                print(f"ERROR - Invalid email value: {email}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "email must be a valid email address (max 255 chars)"})
                }
            set_clauses.append("email = :email")
            params.append({"name": "email", "value": {"stringValue": email}})
            # When email changes, set email_verified to false
            set_clauses.append("email_verified = false")
            email_changed = True
            print(f"LOG - Updating email to {email} (will require verification)")

        # Validate and add email_notifications_enabled if provided
        if email_notifications_enabled is not None:
            if not isinstance(email_notifications_enabled, bool):
                print(f"ERROR - Invalid email_notifications_enabled value: {email_notifications_enabled}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "email_notifications_enabled must be a boolean"})
                }

            # If enabling notifications, check if email is verified
            if email_notifications_enabled and not email_changed:
                check_sql = "SELECT email, email_verified FROM users WHERE athlete_id = :athlete_id"
                check_params = [{"name": "athlete_id", "value": {"longValue": athlete_id}}]
                check_result = exec_sql(check_sql, check_params)
                check_records = check_result.get("records", [])

                if check_records and check_records[0]:
                    user_email = check_records[0][0].get("stringValue") if check_records[0][0].get("isNull") is not True else None
                    email_verified = check_records[0][1].get("booleanValue", False) if len(check_records[0]) > 1 else False

                    if not user_email:
                        print("ERROR - Cannot enable notifications without an email address")
                        return {
                            "statusCode": 400,
                            "headers": cors_headers,
                            "body": json.dumps({"error": "email required before enabling notifications"})
                        }

                    if not email_verified:
                        print("ERROR - Cannot enable notifications with unverified email")
                        return {
                            "statusCode": 400,
                            "headers": cors_headers,
                            "body": json.dumps({"error": "email must be verified before enabling notifications"})
                        }

            set_clauses.append("email_notifications_enabled = :email_notifications_enabled")
            params.append({"name": "email_notifications_enabled", "value": {"booleanValue": email_notifications_enabled}})
            print(f"LOG - Updating email_notifications_enabled to {email_notifications_enabled}")

        # Validate and add send_trail_milestone if provided
        if send_trail_milestone is not None:
            if not isinstance(send_trail_milestone, bool):
                print(f"ERROR - Invalid send_trail_milestone value: {send_trail_milestone}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "send_trail_milestone must be a boolean"})
                }
            set_clauses.append("send_trail_milestone = :send_trail_milestone")
            params.append({"name": "send_trail_milestone", "value": {"booleanValue": send_trail_milestone}})
            print(f"LOG - Updating send_trail_milestone to {send_trail_milestone}")

        # Validate and add send_ranking_change if provided
        if send_ranking_change is not None:
            if not isinstance(send_ranking_change, bool):
                print(f"ERROR - Invalid send_ranking_change value: {send_ranking_change}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "send_ranking_change must be a boolean"})
                }
            set_clauses.append("send_ranking_change = :send_ranking_change")
            params.append({"name": "send_ranking_change", "value": {"booleanValue": send_ranking_change}})
            print(f"LOG - Updating send_ranking_change to {send_ranking_change}")

        # Validate and add min_trail_distance_miles if provided
        if min_trail_distance_miles is not None:
            try:
                distance = float(min_trail_distance_miles)
                if distance < 0.1 or distance > 100.0:
                    raise ValueError("out of range")
            except (ValueError, TypeError):
                print(f"ERROR - Invalid min_trail_distance_miles value: {min_trail_distance_miles}")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "min_trail_distance_miles must be a number between 0.1 and 100.0"})
                }
            set_clauses.append("min_trail_distance_miles = :min_trail_distance_miles")
            params.append({"name": "min_trail_distance_miles", "value": {"doubleValue": distance}})
            print(f"LOG - Updating min_trail_distance_miles to {distance}")
        
        # Always update updated_at
        set_clauses.append("updated_at = now()")
        
        # Add athlete_id parameter
        params.append({"name": "athlete_id", "value": {"longValue": athlete_id}})
        
        # Build SQL query
        sql = f"""
        UPDATE users
        SET {", ".join(set_clauses)}
        WHERE athlete_id = :athlete_id
        RETURNING show_on_leaderboards, timezone, email, email_verified, email_notifications_enabled,
                  send_trail_milestone, send_ranking_change, min_trail_distance_miles
        """
        
        print(f"LOG - Updating settings for user {athlete_id}")
        result = exec_sql(sql, params)
        records = result.get("records", [])
        
        if not records:
            print(f"ERROR - User {athlete_id} not found")
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "user not found"})
            }
        
        # Parse updated values from records
        record = records[0]
        result_data = {
            "success": True,
            "show_on_leaderboards": record[0].get("booleanValue", False) if record[0] else False,
            "timezone": record[1].get("stringValue") if len(record) > 1 and record[1] and not record[1].get("isNull") else None,
            "email": record[2].get("stringValue") if len(record) > 2 and record[2] and not record[2].get("isNull") else None,
            "email_verified": record[3].get("booleanValue", False) if len(record) > 3 and record[3] else False,
            "email_notifications_enabled": record[4].get("booleanValue", False) if len(record) > 4 and record[4] else False,
            "send_trail_milestone": record[5].get("booleanValue", True) if len(record) > 5 and record[5] else True,
            "send_ranking_change": record[6].get("booleanValue", True) if len(record) > 6 and record[6] else True,
            "min_trail_distance_miles": record[7].get("doubleValue", 3.0) if len(record) > 7 and record[7] else 3.0
        }

        print(f"LOG - Successfully updated settings for user {athlete_id}")
        for key, value in result_data.items():
            if key != "success":
                print(f"LOG -   {key}: {value}")
        print("=" * 80)
        print("UPDATE USER SETTINGS - SUCCESS")
        print("=" * 80)

        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(result_data)
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
