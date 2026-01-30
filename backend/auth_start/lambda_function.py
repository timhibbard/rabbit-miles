import os, secrets
from urllib.parse import urlencode

API_BASE = os.environ["API_BASE_URL"].rstrip("/")

def handler(event, context):
    state = secrets.token_urlsafe(24)
    redirect_uri = f"{API_BASE}/auth/callback"
    params = {
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "read,activity:read_all",
        "state": state,
        "approval_prompt": "auto",
    }
    url = "https://www.strava.com/oauth/authorize?" + urlencode(params)

    cookie_val = f"rm_state={state}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=600"

    return {
        "statusCode": 302,
        "headers": { "Location": url, "Set-Cookie": cookie_val },
        # HTTP API v2: use 'cookies' array to ensure API Gateway returns Set-Cookie
        "cookies": [ cookie_val ],
        "body": ""
    }
