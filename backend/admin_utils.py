"""
Admin utility functions for RabbitMiles backend.

Provides shared functionality for admin endpoints:
- Loading and parsing admin athlete IDs from environment variables
- Verifying if a user is an admin
- Session verification and admin authorization
- Audit logging for admin actions
- Admin-specific response headers
"""

import os
import json
import base64
import hmac
import hashlib
from typing import Optional, Set, Tuple


def load_admin_athlete_ids() -> Set[int]:
    """
    Load admin athlete IDs from ADMIN_ATHLETE_IDS environment variable.
    
    Expected format: "3519964,12345,67890" (comma-separated list of IDs)
    
    Returns:
        Set of admin athlete IDs (integers)
    """
    admin_ids_str = os.environ.get("ADMIN_ATHLETE_IDS", "")
    if not admin_ids_str:
        print("LOG - No ADMIN_ATHLETE_IDS configured")
        return set()
    
    admin_ids = set()
    for id_str in admin_ids_str.split(","):
        id_str = id_str.strip()
        if id_str:
            try:
                admin_ids.add(int(id_str))
            except ValueError:
                print(f"WARNING - Invalid athlete_id in ADMIN_ATHLETE_IDS: {id_str}")
    
    print(f"LOG - Loaded {len(admin_ids)} admin athlete IDs")
    return admin_ids


def is_admin(athlete_id: int, admin_ids: Optional[Set[int]] = None) -> bool:
    """
    Check if an athlete_id is in the admin allowlist.
    
    Args:
        athlete_id: The athlete ID to check
        admin_ids: Optional set of admin IDs. If not provided, loads from env var.
    
    Returns:
        True if the athlete is an admin, False otherwise
    """
    if admin_ids is None:
        admin_ids = load_admin_athlete_ids()
    
    return athlete_id in admin_ids


def verify_session_token(token: str, app_secret: bytes) -> Optional[int]:
    """
    Verify a session token and return the athlete_id if valid.
    
    Args:
        token: The session token string
        app_secret: The APP_SECRET bytes for verification
    
    Returns:
        The athlete_id if token is valid, None otherwise
    """
    try:
        b, sig = token.rsplit(".", 1)
        expected = hmac.new(app_secret, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode())
        if data.get("exp", 0) < __import__("time").time():
            return None
        return int(data.get("aid"))
    except Exception:
        return None


def parse_session_cookie(event: dict) -> Optional[str]:
    """
    Parse session token from cookies in API Gateway event.
    
    Args:
        event: The API Gateway event dict
    
    Returns:
        The rm_session cookie value if found, None otherwise
    """
    headers = event.get("headers") or {}
    
    # Check cookies array first (v2 format)
    cookies_array = event.get("cookies") or []
    for cookie_str in cookies_array:
        if not cookie_str or "=" not in cookie_str:
            continue
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v
    
    # Check cookie header (fallback)
    cookie_header = headers.get("cookie") or headers.get("Cookie")
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v
    
    return None


def verify_admin_session(event: dict, app_secret: bytes, admin_ids: Optional[Set[int]] = None) -> Tuple[Optional[int], bool]:
    """
    Verify session and check if the authenticated user is an admin.
    
    Args:
        event: The API Gateway event dict
        app_secret: The APP_SECRET bytes for verification
        admin_ids: Optional set of admin IDs. If not provided, loads from env var.
    
    Returns:
        Tuple of (athlete_id, is_admin)
        - (None, False) if not authenticated
        - (athlete_id, False) if authenticated but not admin
        - (athlete_id, True) if authenticated and is admin
    """
    token = parse_session_cookie(event)
    if not token:
        return None, False
    
    athlete_id = verify_session_token(token, app_secret)
    if not athlete_id:
        return None, False
    
    if admin_ids is None:
        admin_ids = load_admin_athlete_ids()
    
    return athlete_id, athlete_id in admin_ids


def get_admin_headers(cors_origin: Optional[str] = None) -> dict:
    """
    Get headers for admin endpoints with no-store cache control.
    
    Args:
        cors_origin: Optional CORS origin to include in headers
    
    Returns:
        Dict of headers for admin responses
    """
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
    }
    
    if cors_origin:
        headers["Access-Control-Allow-Origin"] = cors_origin
        headers["Access-Control-Allow-Credentials"] = "true"
    
    return headers


def audit_log_admin_action(athlete_id: int, endpoint: str, action: str, details: Optional[dict] = None):
    """
    Log admin action for audit purposes.
    
    Args:
        athlete_id: The admin's athlete ID
        endpoint: The endpoint that was accessed
        action: Description of the action
        details: Optional dict of additional details
    """
    import time
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    log_entry = {
        "timestamp": timestamp,
        "admin_athlete_id": athlete_id,
        "endpoint": endpoint,
        "action": action,
    }
    if details:
        log_entry["details"] = details
    
    print(f"AUDIT - {json.dumps(log_entry)}")
