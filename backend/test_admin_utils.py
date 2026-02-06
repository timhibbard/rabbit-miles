#!/usr/bin/env python3
"""
Test for admin_utils module

Tests the admin utility functions for proper authentication and authorization.
"""

import sys
import os
import json
import time
import base64
import hmac
import hashlib
from unittest.mock import Mock, patch

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

import admin_utils


def test_load_admin_athlete_ids():
    """Test loading admin athlete IDs from environment variable"""
    print("Testing load_admin_athlete_ids...")
    
    # Test with valid IDs
    os.environ["ADMIN_ATHLETE_IDS"] = "3519964,12345,67890"
    admin_ids = admin_utils.load_admin_athlete_ids()
    assert admin_ids == {3519964, 12345, 67890}, f"Expected {{3519964, 12345, 67890}}, got {admin_ids}"
    print("✓ Valid IDs loaded correctly")
    
    # Test with whitespace
    os.environ["ADMIN_ATHLETE_IDS"] = " 111 , 222 , 333 "
    admin_ids = admin_utils.load_admin_athlete_ids()
    assert admin_ids == {111, 222, 333}, f"Expected {{111, 222, 333}}, got {admin_ids}"
    print("✓ IDs with whitespace loaded correctly")
    
    # Test with empty string
    os.environ["ADMIN_ATHLETE_IDS"] = ""
    admin_ids = admin_utils.load_admin_athlete_ids()
    assert admin_ids == set(), f"Expected empty set, got {admin_ids}"
    print("✓ Empty string returns empty set")
    
    # Test with invalid IDs (should skip them)
    os.environ["ADMIN_ATHLETE_IDS"] = "123,invalid,456"
    admin_ids = admin_utils.load_admin_athlete_ids()
    assert admin_ids == {123, 456}, f"Expected {{123, 456}}, got {admin_ids}"
    print("✓ Invalid IDs skipped correctly")
    
    # Clean up
    if "ADMIN_ATHLETE_IDS" in os.environ:
        del os.environ["ADMIN_ATHLETE_IDS"]
    
    print("✅ load_admin_athlete_ids tests passed\n")


def test_is_admin():
    """Test checking if an athlete is an admin"""
    print("Testing is_admin...")
    
    admin_ids = {3519964, 12345, 67890}
    
    # Test with admin ID
    assert admin_utils.is_admin(3519964, admin_ids) == True, "Expected True for admin ID"
    print("✓ Admin ID recognized correctly")
    
    # Test with non-admin ID
    assert admin_utils.is_admin(99999, admin_ids) == False, "Expected False for non-admin ID"
    print("✓ Non-admin ID rejected correctly")
    
    # Test with environment variable
    os.environ["ADMIN_ATHLETE_IDS"] = "111,222"
    assert admin_utils.is_admin(111) == True, "Expected True when loading from env var"
    assert admin_utils.is_admin(999) == False, "Expected False when loading from env var"
    print("✓ Environment variable loading works")
    
    # Clean up
    if "ADMIN_ATHLETE_IDS" in os.environ:
        del os.environ["ADMIN_ATHLETE_IDS"]
    
    print("✅ is_admin tests passed\n")


def test_verify_session_token():
    """Test session token verification"""
    print("Testing verify_session_token...")
    
    app_secret = b"test_secret_key"
    
    # Create a valid token
    exp = int(time.time()) + 3600  # Expires in 1 hour
    data = {"aid": 12345, "exp": exp}
    b64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    signature = hmac.new(app_secret, b64_data.encode(), hashlib.sha256).hexdigest()
    valid_token = f"{b64_data}.{signature}"
    
    # Test with valid token
    athlete_id = admin_utils.verify_session_token(valid_token, app_secret)
    assert athlete_id == 12345, f"Expected 12345, got {athlete_id}"
    print("✓ Valid token verified correctly")
    
    # Test with invalid signature
    invalid_token = f"{b64_data}.invalid_signature"
    athlete_id = admin_utils.verify_session_token(invalid_token, app_secret)
    assert athlete_id is None, f"Expected None for invalid signature, got {athlete_id}"
    print("✓ Invalid signature rejected")
    
    # Test with expired token
    exp = int(time.time()) - 3600  # Expired 1 hour ago
    data = {"aid": 12345, "exp": exp}
    b64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    signature = hmac.new(app_secret, b64_data.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{b64_data}.{signature}"
    athlete_id = admin_utils.verify_session_token(expired_token, app_secret)
    assert athlete_id is None, f"Expected None for expired token, got {athlete_id}"
    print("✓ Expired token rejected")
    
    # Test with malformed token
    athlete_id = admin_utils.verify_session_token("not.a.valid.token", app_secret)
    assert athlete_id is None, f"Expected None for malformed token, got {athlete_id}"
    print("✓ Malformed token rejected")
    
    print("✅ verify_session_token tests passed\n")


def test_parse_session_cookie():
    """Test parsing session cookie from API Gateway event"""
    print("Testing parse_session_cookie...")
    
    # Test with cookies array (v2 format)
    event = {
        "cookies": ["rm_session=test_token_123"],
        "headers": {}
    }
    token = admin_utils.parse_session_cookie(event)
    assert token == "test_token_123", f"Expected 'test_token_123', got {token}"
    print("✓ Cookie from cookies array parsed correctly")
    
    # Test with cookie header
    event = {
        "headers": {
            "cookie": "rm_session=test_token_456; other_cookie=value"
        }
    }
    token = admin_utils.parse_session_cookie(event)
    assert token == "test_token_456", f"Expected 'test_token_456', got {token}"
    print("✓ Cookie from header parsed correctly")
    
    # Test with no cookies
    event = {"headers": {}}
    token = admin_utils.parse_session_cookie(event)
    assert token is None, f"Expected None, got {token}"
    print("✓ No cookie returns None")
    
    print("✅ parse_session_cookie tests passed\n")


def test_verify_admin_session():
    """Test verifying admin session"""
    print("Testing verify_admin_session...")
    
    app_secret = b"test_secret_key"
    admin_ids = {12345}
    
    # Create valid admin token
    exp = int(time.time()) + 3600
    data = {"aid": 12345, "exp": exp}
    b64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    signature = hmac.new(app_secret, b64_data.encode(), hashlib.sha256).hexdigest()
    admin_token = f"{b64_data}.{signature}"
    
    # Create valid non-admin token
    data = {"aid": 99999, "exp": exp}
    b64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    signature = hmac.new(app_secret, b64_data.encode(), hashlib.sha256).hexdigest()
    user_token = f"{b64_data}.{signature}"
    
    # Test with admin token
    event = {"cookies": [f"rm_session={admin_token}"], "headers": {}}
    athlete_id, is_admin = admin_utils.verify_admin_session(event, app_secret, admin_ids)
    assert athlete_id == 12345, f"Expected athlete_id 12345, got {athlete_id}"
    assert is_admin == True, f"Expected is_admin True, got {is_admin}"
    print("✓ Admin session verified correctly")
    
    # Test with non-admin token
    event = {"cookies": [f"rm_session={user_token}"], "headers": {}}
    athlete_id, is_admin = admin_utils.verify_admin_session(event, app_secret, admin_ids)
    assert athlete_id == 99999, f"Expected athlete_id 99999, got {athlete_id}"
    assert is_admin == False, f"Expected is_admin False, got {is_admin}"
    print("✓ Non-admin session handled correctly")
    
    # Test with no token
    event = {"headers": {}}
    athlete_id, is_admin = admin_utils.verify_admin_session(event, app_secret, admin_ids)
    assert athlete_id is None, f"Expected athlete_id None, got {athlete_id}"
    assert is_admin == False, f"Expected is_admin False, got {is_admin}"
    print("✓ No token handled correctly")
    
    print("✅ verify_admin_session tests passed\n")


def test_get_admin_headers():
    """Test getting admin headers"""
    print("Testing get_admin_headers...")
    
    # Test without CORS
    headers = admin_utils.get_admin_headers()
    assert "Content-Type" in headers, "Expected Content-Type header"
    assert "Cache-Control" in headers, "Expected Cache-Control header"
    assert headers["Cache-Control"] == "no-store", f"Expected 'no-store', got {headers['Cache-Control']}"
    print("✓ Headers without CORS correct")
    
    # Test with CORS
    headers = admin_utils.get_admin_headers("https://example.com")
    assert headers["Access-Control-Allow-Origin"] == "https://example.com", "Expected CORS origin"
    assert headers["Access-Control-Allow-Credentials"] == "true", "Expected credentials true"
    print("✓ Headers with CORS correct")
    
    print("✅ get_admin_headers tests passed\n")


def test_audit_log_admin_action():
    """Test audit logging"""
    print("Testing audit_log_admin_action...")
    
    # This function just prints to stdout, so we'll just make sure it doesn't crash
    admin_utils.audit_log_admin_action(12345, "/admin/users", "list_users")
    print("✓ Basic audit log works")
    
    admin_utils.audit_log_admin_action(12345, "/admin/users", "list_users", {"extra": "data"})
    print("✓ Audit log with details works")
    
    print("✅ audit_log_admin_action tests passed\n")


if __name__ == "__main__":
    print("=" * 80)
    print("Running admin_utils tests")
    print("=" * 80)
    print()
    
    try:
        test_load_admin_athlete_ids()
        test_is_admin()
        test_verify_session_token()
        test_parse_session_cookie()
        test_verify_admin_session()
        test_get_admin_headers()
        test_audit_log_admin_action()
        
        print("=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
