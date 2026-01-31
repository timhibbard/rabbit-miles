# rabbitmiles-auth-disconnect
# Handler: lambda_function.handler
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

DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ.get("DB_NAME", "postgres")
API_BASE = os.environ["API_BASE_URL"].rstrip("/")
FRONTEND = os.environ["FRONTEND_URL"].rstrip("/")
APP_SECRET = os.environ["APP_SECRET"].encode()

# Extract path from API_BASE_URL for cookie Path attribute
# API_BASE_URL format: https://domain.com/stage or https://domain.com
# We need the path portion (e.g., /stage) for cookies to work with API Gateway
_parsed_api_base = urlparse(API_BASE)
COOKIE_PATH = _parsed_api_base.path or "/"


def _parse_cookies(headers: dict) -> dict:
    cookie_header = (headers or {}).get("cookie") or (headers or {}).get("Cookie") or ""
    out = {}
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
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
    headers = event.get("headers") or {}
    cookies = _parse_cookies(headers)
    session = cookies.get("rm_session")
    if not session:
        # still clear cookie and redirect
        clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
        return {
            "statusCode": 302,
            "headers": {"Location": f"{FRONTEND}/?connected=0"},
            "cookies": [clear],
            "body": "",
        }

    aid = _verify_session_token(session)
    if not aid:
        # invalid session: clear cookie
        clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
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
    except Exception as e:
        # best-effort: clear cookie and redirect even on DB failures, but surface minimal error
        clear = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
        return {
            "statusCode": 302,
            "headers": {"Location": f"{FRONTEND}/?connected=0&error=disconnect_failed"},
            "cookies": [clear],
            "body": "",
        }

    # Clear session cookie and redirect to frontend
    clear_session = f"rm_session=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"
    # also clear any leftover rm_state just in case
    clear_state = f"rm_state=; HttpOnly; Secure; SameSite=None; Path={COOKIE_PATH}; Max-Age=0"

    return {
        "statusCode": 302,
        "headers": {"Location": f"{FRONTEND}/?connected=0"},
        "cookies": [clear_session, clear_state],
        "body": "",
    }
