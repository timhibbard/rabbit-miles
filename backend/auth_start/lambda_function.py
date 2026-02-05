# rabbitmiles-auth-start (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# API_BASE_URL (ex: https://9zke9jame0.execute-api.us-east-1.amazonaws.com)
# FRONTEND_URL (ex: https://timhibbard.github.io/rabbit-miles)
# STRAVA_CLIENT_ID

import os, secrets, time
from urllib.parse import urlencode, urlparse
import boto3

# Get environment variables safely - validation happens in handler
API_BASE = os.environ.get("API_BASE_URL", "").rstrip("/")
FRONTEND = os.environ.get("FRONTEND_URL", "").rstrip("/")

rds = boto3.client("rds-data")
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")

# Extract path from API_BASE_URL for cookie Path attribute
# API_BASE_URL format: https://domain.com/stage or https://domain.com
# Use a root path to avoid path mismatches across stages.
_parsed_api_base = urlparse(API_BASE) if API_BASE else None
API_BASE_PATH = _parsed_api_base.path if _parsed_api_base and _parsed_api_base.path else ""
COOKIE_PATH = "/"

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
    print("=" * 80)
    print("AUTH START LAMBDA - START")
    print("=" * 80)
    
    print(f"LOG - Environment configuration:")
    print(f"LOG -   FRONTEND_URL: {FRONTEND}")
    print(f"LOG -   API_BASE_URL: {API_BASE}")
    print(f"LOG -   STRAVA_CLIENT_ID: {os.environ.get('STRAVA_CLIENT_ID', 'NOT SET')[:20]}...")
    
    # Validate required environment variables
    if not FRONTEND:
        print("ERROR - FRONTEND_URL environment variable not set")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Server configuration error. Please contact support at tim@rabbitmiles.com."}'
        }
    
    if not os.environ.get("STRAVA_CLIENT_ID"):
        print("ERROR - STRAVA_CLIENT_ID environment variable not set")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Server configuration error. Please contact support at tim@rabbitmiles.com."}'
        }
    
    if API_BASE_PATH:
        print(f"LOG - API_BASE_URL path detected: {API_BASE_PATH}")
    print(f"LOG - Cookie path configured as: {COOKIE_PATH}")
    
    # Log request context
    request_context = event.get("requestContext", {})
    http_context = request_context.get("http", {})
    print(f"LOG - Request method: {http_context.get('method', 'UNKNOWN')}")
    print(f"LOG - Request path: {http_context.get('path', 'UNKNOWN')}")
    print(f"LOG - Source IP: {http_context.get('sourceIp', 'UNKNOWN')}")
    
    headers = event.get("headers") or {}
    user_agent = headers.get("user-agent") or headers.get("User-Agent") or ""
    if user_agent:
        print(f"LOG - User-Agent: {user_agent}")
    
    print(f"LOG - Generating OAuth state token")
    state = secrets.token_urlsafe(24)
    print(f"LOG - State token generated: {state[:10]}...{state[-10:]} (length: {len(state)})")
    
    # Store state in database with 10-minute expiration
    expires_at = int(time.time()) + 600
    print(f"LOG - State expires_at: {expires_at} (in 600 seconds)")
    
    sql = """
    INSERT INTO oauth_states (state, expires_at, created_at)
    VALUES (:state, :expires_at, now());
    """
    params = [
        {"name": "state", "value": {"stringValue": state}},
        {"name": "expires_at", "value": {"longValue": expires_at}},
    ]
    try:
        print(f"LOG - Storing state in database")
        _exec_sql(sql, params)
        print(f"LOG - State stored successfully in oauth_states table")
    except Exception as e:
        # If table doesn't exist yet, return error (migration must be run first)
        print(f"ERROR - Failed to store state in database: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Database configuration error. Please contact support at tim@rabbitmiles.com."}'
        }
    
    redirect_uri = f"{FRONTEND}/callback"
    print(f"LOG - OAuth redirect_uri: {redirect_uri}")
    
    params = {
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "read,activity:read_all",
        "state": state,
        "approval_prompt": "force",  # Force re-authorization to ensure correct scope
    }
    url = "https://www.strava.com/oauth/authorize?" + urlencode(params)
    print(f"LOG - Strava OAuth URL length: {len(url)} chars")
    print(f"LOG - Strava OAuth URL: {url[:100]}...")

    # Partitioned attribute is required for cross-site cookies in Chrome and modern browsers
    cookie_val = f"rm_state={state}; HttpOnly; Secure; SameSite=None; Partitioned; Path={COOKIE_PATH}; Max-Age=600"
    print(f"LOG - Setting rm_state cookie:")
    print(f"LOG -   Name: rm_state")
    print(f"LOG -   Value: {state[:10]}...{state[-10:]}")
    print(f"LOG -   HttpOnly: Yes")
    print(f"LOG -   Secure: Yes")
    print(f"LOG -   SameSite: None")
    print(f"LOG -   Partitioned: Yes")
    print(f"LOG -   Path: {COOKIE_PATH}")
    print(f"LOG -   Max-Age: 600 seconds (10 minutes)")
    print(f"LOG - Cookie string length: {len(cookie_val)} chars")

    print(f"LOG - Redirecting to Strava OAuth page (302)")
    print("=" * 80)
    print("AUTH START LAMBDA - SUCCESS")
    print("=" * 80)

    return {
        "statusCode": 302,
        "headers": { "Location": url },
        # HTTP API v2: use 'cookies' array to ensure API Gateway returns Set-Cookie
        # Do not use Set-Cookie header with cookies array to avoid conflicts
        "cookies": [ cookie_val ],
        "body": ""
    }
