# rabbitmiles-auth-start (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# API_BASE_URL (ex: https://9zke9jame0.execute-api.us-east-1.amazonaws.com)
# STRAVA_CLIENT_ID

import os, secrets, time
from urllib.parse import urlencode, urlparse
import boto3

API_BASE = os.environ["API_BASE_URL"].rstrip("/")

rds = boto3.client("rds-data")
DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ.get("DB_NAME", "postgres")

# Extract path from API_BASE_URL for cookie Path attribute
# API_BASE_URL format: https://domain.com/stage or https://domain.com
# We need the path portion (e.g., /stage) for cookies to work with API Gateway
_parsed_api_base = urlparse(API_BASE)
COOKIE_PATH = _parsed_api_base.path or "/"

def _exec_sql(sql: str, parameters: list | None = None):
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)

def handler(event, context):
    state = secrets.token_urlsafe(24)
    
    # Store state in database with 10-minute expiration
    expires_at = int(time.time()) + 600
    sql = """
    INSERT INTO oauth_states (state, expires_at, created_at)
    VALUES (:state, :expires_at, now());
    """
    params = [
        {"name": "state", "value": {"stringValue": state}},
        {"name": "expires_at", "value": {"longValue": expires_at}},
    ]
    try:
        _exec_sql(sql, params)
    except Exception as e:
        # If table doesn't exist yet, return error (migration must be run first)
        print(f"ERROR: Failed to store state in database: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Database configuration error. Please contact support."}'
        }
    
    redirect_uri = f"{API_BASE}/auth/callback"
    params = {
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "read,activity:read",
        "state": state,
        "approval_prompt": "force",  # Force re-authorization to ensure correct scope
    }
    url = "https://www.strava.com/oauth/authorize?" + urlencode(params)

    cookie_val = f"rm_state={state}; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=600"

    return {
        "statusCode": 302,
        "headers": { "Location": url, "Set-Cookie": cookie_val },
        # HTTP API v2: use 'cookies' array to ensure API Gateway returns Set-Cookie
        "cookies": [ cookie_val ],
        "body": ""
    }
