# rabbitmiles-auth-disconnect
# Handler: lambda_function.handler
# Method: GET (user navigates to this endpoint, it clears session and redirects)
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# API_BASE_URL (e.g. https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod)
# FRONTEND_URL (e.g. https://<you>.github.io/rabbitmiles)
# APP_SECRET (same secret used by auth callback / me)

import os
import json
import base64
import hmac
import hashlib
from urllib.parse import urlparse
import boto3

rds = boto3.client("rds-data")

# Get environment variables safely - validation happens in handler
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
API_BASE = os.environ.get("API_BASE_URL", "").rstrip("/")
FRONTEND = os.environ.get("FRONTEND_URL", "").rstrip("/")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""

# Extract path from API_BASE_URL for cookie Path attribute
# API_BASE_URL format: https://domain.com/stage or https://domain.com
# We need the path portion (e.g., /stage) for cookies to work with API Gateway
_parsed_api_base = urlparse(API_BASE) if API_BASE else None
COOKIE_PATH = _parsed_api_base.path if _parsed_api_base and _parsed_api_base.path else "/"


def _parse_cookies(event: dict) -> dict:
    """Parse cookies from API Gateway HTTP API v2 event format or headers"""
    out = {}
    
    # API Gateway HTTP API v2 provides cookies in event['cookies'] array
    cookies_array = event.get("cookies") or []
    for cookie_str in cookies_array:
        if not cookie_str or "=" not in cookie_str:
            continue
        # Handle cookie strings that might have multiple cookies separated by semicolons
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            out[k] = v
    
    # Also check headers for backwards compatibility
    headers = event.get("headers") or {}
    cookie_header = headers.get("cookie") or headers.get("Cookie") or ""
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            # Prefer cookies from event['cookies'] array (v2 format) over headers (v1 format)
            if k not in out:
                out[k] = v
    
    return out


def _verify_session_token(tok: str):
    try:
        b, sig = tok.rsplit(".", 1)
        expected = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload_json = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        data = json.loads(payload_json)
        # check expiration
        if data.get("exp", 0) < int(__import__("time").time()):
            return None
        return int(data.get("aid"))
    except Exception:
        return None


def _exec_sql(sql: str, parameters: list = None):
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
    cookies = _parse_cookies(event)
    session = cookies.get("rm_session")
    if not session:
        # still clear cookie and redirect
        # Partitioned attribute is required for cross-site cookies in Chrome and modern browsers
        clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Partitioned; Path={COOKIE_PATH}; Max-Age=0"
        print("No session cookie found, clearing and redirecting")
        return {
            "statusCode": 302,
            "headers": {"Location": f"{FRONTEND}/?connected=0"},
            "cookies": [clear],
            "body": "",
        }

    aid = _verify_session_token(session)
    if not aid:
        # invalid session: clear cookie
        # Partitioned attribute is required for cross-site cookies in Chrome and modern browsers
        clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Partitioned; Path={COOKIE_PATH}; Max-Age=0"
        print("Invalid session token, clearing and redirecting")
        return {
            "statusCode": 302,
            "headers": {"Location": f"{FRONTEND}/?connected=0"},
            "cookies": [clear],
            "body": "",
        }

    # Remove sensitive tokens from the users row but keep the account (so we don't lose preferences)
    sql = """
    UPDATE users
    SET access_token = NULL,
        refresh_token = NULL,
        expires_at = NULL,
        updated_at = now()
    WHERE athlete_id = :aid
    """
    params = [{"name": "aid", "value": {"longValue": aid}}]
    try:
        _exec_sql(sql, params)
        print(f"Successfully cleared tokens for athlete_id: {aid}")
    except Exception as e:
        # best-effort: clear cookie and redirect even on DB failures, but surface minimal error
        # Log generic error to avoid exposing sensitive database details
        print(f"Failed to clear tokens in database: database error occurred")
        # Partitioned attribute is required for cross-site cookies in Chrome and modern browsers
        clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Partitioned; Path={COOKIE_PATH}; Max-Age=0"
        return {
            "statusCode": 302,
            "headers": {"Location": f"{FRONTEND}/?connected=0&error=disconnect_failed"},
            "cookies": [clear],
            "body": "",
        }

    # Clear session cookie and redirect to frontend
    # Partitioned attribute is required for cross-site cookies in Chrome and modern browsers
    clear_session = f"rm_session=; HttpOnly; Secure; SameSite=None; Partitioned; Path={COOKIE_PATH}; Max-Age=0"
    # also clear any leftover rm_state just in case
    clear_state = f"rm_state=; HttpOnly; Secure; SameSite=None; Partitioned; Path={COOKIE_PATH}; Max-Age=0"
    print(f"Clearing session cookies and redirecting to frontend for athlete_id: {aid}")

    return {
        "statusCode": 302,
        "headers": {"Location": f"{FRONTEND}/?connected=0"},
        "cookies": [clear_session, clear_state],
        "body": "",
    }
