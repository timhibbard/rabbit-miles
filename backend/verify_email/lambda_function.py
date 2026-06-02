# rabbitmiles-verify-email (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for token verification)
# FRONTEND_URL (for CORS)
# FROM_EMAIL (email sender address, e.g., notifications@rabbitmiles.com)

import os
import sys
import json
import hmac
import hashlib
import html
import time
from urllib.parse import urlparse
import boto3

# Add parent directory to path to import admin_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import admin_utils

rds = boto3.client("rds-data")
ses = boto3.client("sesv2")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "notifications@rabbitmiles.com")

# Token expiry: 24 hours
TOKEN_EXPIRY_SECONDS = 24 * 60 * 60


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


def generate_verification_token(athlete_id, email):
    """Generate HMAC-based verification token"""
    timestamp = int(time.time())
    message = f"{athlete_id}:{email}:{timestamp}".encode()
    token_hash = hmac.new(APP_SECRET, message, hashlib.sha256).hexdigest()
    # Token format: <athlete_id>:<timestamp>:<hash>
    return f"{athlete_id}:{timestamp}:{token_hash}"


def verify_token(token):
    """Verify and parse token, return (athlete_id, email) or (None, None)"""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None, None

        athlete_id_str, timestamp_str, token_hash = parts
        athlete_id = int(athlete_id_str)
        timestamp = int(timestamp_str)

        # Check if token expired
        if time.time() - timestamp > TOKEN_EXPIRY_SECONDS:
            print(f"LOG - Token expired (age: {int(time.time() - timestamp)} seconds)")
            return None, None

        # Get user's email from database
        sql = "SELECT email FROM users WHERE athlete_id = :athlete_id"
        params = [{"name": "athlete_id", "value": {"longValue": athlete_id}}]
        result = exec_sql(sql, params)
        records = result.get("records", [])

        if not records or not records[0] or not records[0][0] or records[0][0].get("isNull"):
            print(f"LOG - No email found for athlete {athlete_id}")
            return None, None

        email = records[0][0].get("stringValue")

        # Verify token hash
        expected_message = f"{athlete_id}:{email}:{timestamp}".encode()
        expected_hash = hmac.new(APP_SECRET, expected_message, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(token_hash, expected_hash):
            print("LOG - Token hash mismatch")
            return None, None

        return athlete_id, email

    except (ValueError, IndexError) as e:
        print(f"LOG - Token parse error: {e}")
        return None, None


def send_verification_email(athlete_id, email, display_name):
    """Send verification email via SES"""
    token = generate_verification_token(athlete_id, email)
    # Route to API Gateway endpoint, not frontend
    verification_url = f"https://api.rabbitmiles.com/verify-email?token={token}"

    # Escape user-controlled values
    safe_display_name = html.escape(display_name)

    # Simple HTML email
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #333;">Verify your RabbitMiles email address</h1>
        <p>Hi {safe_display_name},</p>
        <p>Please verify your email address to receive notifications from RabbitMiles.</p>
        <p style="margin: 30px 0;">
            <a href="{verification_url}"
               style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                Verify Email
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">
            Or copy and paste this link into your browser:<br>
            <a href="{verification_url}">{verification_url}</a>
        </p>
        <p style="color: #666; font-size: 14px;">
            This link expires in 24 hours.
        </p>
        <p style="color: #666; font-size: 14px;">
            If you didn't request this, you can safely ignore this email.
        </p>
        <p style="color: #999; font-size: 12px; margin-top: 40px;">
            🐰 RabbitMiles
        </p>
    </body>
    </html>
    """

    text_body = f"""
Hi {safe_display_name},

Please verify your email address to receive notifications from RabbitMiles.

Verify your email: {verification_url}

This link expires in 24 hours.

If you didn't request this, you can safely ignore this email.

🐰 RabbitMiles
    """.strip()

    try:
        ses.send_email(
            FromEmailAddress=FROM_EMAIL,
            Destination={'ToAddresses': [email]},
            Content={
                'Simple': {
                    'Subject': {
                        'Data': 'Verify your RabbitMiles email address',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        },
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            }
        )
        print(f"LOG - Verification email sent to {email}")
        return True
    except Exception as e:
        print(f"ERROR - Failed to send verification email: {e}")
        return False


def handler(event, context):
    """
    Handle two operations:
    1. POST /verify-email/send - Send verification email
    2. GET /verify-email?token=... - Verify token and mark email as verified
    """
    print("=" * 80)
    print("VERIFY EMAIL - START")
    print("=" * 80)

    cors_headers = get_cors_headers()

    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        print("LOG - OPTIONS preflight request")
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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

        http_method = event.get("requestContext", {}).get("http", {}).get("method")

        # POST /verify-email/send - Send verification email
        if http_method == "POST":
            # Verify session
            print("LOG - Verifying session")
            token_cookie = admin_utils.parse_session_cookie(event)
            if not token_cookie:
                print("ERROR - Not authenticated")
                return {
                    "statusCode": 401,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "not authenticated"})
                }

            athlete_id = admin_utils.verify_session_token(token_cookie, APP_SECRET)
            if not athlete_id:
                print("ERROR - Invalid session")
                return {
                    "statusCode": 401,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "invalid session"})
                }

            print(f"LOG - User {athlete_id} authenticated successfully")

            # Get user's email and display name
            sql = """
            SELECT email, display_name
            FROM users
            WHERE athlete_id = :athlete_id
            """
            params = [{"name": "athlete_id", "value": {"longValue": athlete_id}}]
            result = exec_sql(sql, params)
            records = result.get("records", [])

            if not records or not records[0]:
                print(f"ERROR - User {athlete_id} not found")
                return {
                    "statusCode": 404,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "user not found"})
                }

            if not records[0][0] or records[0][0].get("isNull"):
                print(f"ERROR - User {athlete_id} has no email set")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "email address required"})
                }

            email = records[0][0].get("stringValue")
            display_name = records[0][1].get("stringValue", "Runner") if len(records[0]) > 1 and records[0][1] else "Runner"

            # Send verification email
            success = send_verification_email(athlete_id, email, display_name)

            if not success:
                return {
                    "statusCode": 500,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "failed to send verification email"})
                }

            print("=" * 80)
            print("VERIFY EMAIL SEND - SUCCESS")
            print("=" * 80)

            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({"success": True, "message": "verification email sent"})
            }

        # GET /verify-email?token=... - Verify token
        elif http_method == "GET":
            # Get token from query string
            query_params = event.get("queryStringParameters", {}) or {}
            token = query_params.get("token")

            if not token:
                print("ERROR - Missing token parameter")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "token required"})
                }

            # Verify token
            athlete_id, email = verify_token(token)

            if not athlete_id or not email:
                print(f"ERROR - Invalid or expired token")
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "invalid or expired token"})
                }

            # Mark email as verified
            sql = """
            UPDATE users
            SET email_verified = true, updated_at = now()
            WHERE athlete_id = :athlete_id AND email = :email
            RETURNING email_verified
            """
            params = [
                {"name": "athlete_id", "value": {"longValue": athlete_id}},
                {"name": "email", "value": {"stringValue": email}}
            ]
            result = exec_sql(sql, params)
            records = result.get("records", [])

            if not records:
                print(f"ERROR - User {athlete_id} not found or email mismatch")
                return {
                    "statusCode": 404,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "user not found"})
                }

            print(f"LOG - Email {email} verified for athlete {athlete_id}")
            print("=" * 80)
            print("VERIFY EMAIL - SUCCESS")
            print("=" * 80)

            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({"success": True, "message": "email verified successfully"})
            }

        else:
            return {
                "statusCode": 405,
                "headers": cors_headers,
                "body": json.dumps({"error": "method not allowed"})
            }

    except Exception as e:
        print(f"CRITICAL ERROR - Unexpected exception in /verify-email handler")
        print(f"ERROR - Exception type: {type(e).__name__}")
        print(f"ERROR - Exception message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("VERIFY EMAIL - FAILED")
        print("=" * 80)

        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
