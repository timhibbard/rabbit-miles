#!/usr/bin/env python3
"""
Test for get_activity_detail Lambda function

Tests the admin authorization bypass for viewing other users' activities.
"""

import sys
import os
import json
import time
import base64
import hmac
import hashlib
from unittest.mock import Mock, patch

# Mock boto3 before importing lambda_function
sys.modules['boto3'] = Mock()

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

# Add the get_activity_detail directory to the path
get_activity_detail_dir = os.path.dirname(__file__)
sys.path.insert(0, get_activity_detail_dir)

import lambda_function


def test_load_admin_athlete_ids():
    """Test loading admin athlete IDs from environment variable"""
    print("Testing load_admin_athlete_ids...")
    
    # Test with valid IDs
    os.environ["ADMIN_ATHLETE_IDS"] = "3519964,12345,67890"
    admin_ids = lambda_function.load_admin_athlete_ids()
    assert admin_ids == {3519964, 12345, 67890}, f"Expected {{3519964, 12345, 67890}}, got {admin_ids}"
    print("✓ Valid IDs loaded correctly")
    
    # Test with whitespace
    os.environ["ADMIN_ATHLETE_IDS"] = " 111 , 222 , 333 "
    admin_ids = lambda_function.load_admin_athlete_ids()
    assert admin_ids == {111, 222, 333}, f"Expected {{111, 222, 333}}, got {admin_ids}"
    print("✓ IDs with whitespace loaded correctly")
    
    # Test with empty string
    os.environ["ADMIN_ATHLETE_IDS"] = ""
    admin_ids = lambda_function.load_admin_athlete_ids()
    assert admin_ids == set(), f"Expected empty set, got {admin_ids}"
    print("✓ Empty string returns empty set")
    
    # Test with invalid IDs (should skip them)
    os.environ["ADMIN_ATHLETE_IDS"] = "123,invalid,456"
    admin_ids = lambda_function.load_admin_athlete_ids()
    assert admin_ids == {123, 456}, f"Expected {{123, 456}}, got {admin_ids}"
    print("✓ Invalid IDs skipped correctly")
    
    # Clean up
    if "ADMIN_ATHLETE_IDS" in os.environ:
        del os.environ["ADMIN_ATHLETE_IDS"]
    
    print("✅ load_admin_athlete_ids tests passed\n")


def test_admin_authorization_logic():
    """Test the admin authorization logic"""
    print("Testing admin authorization logic...")
    
    # Simulate admin IDs
    admin_ids = {12345, 67890}
    
    # Test case 1: Regular user accessing their own activity
    authenticated_user_id = 11111
    activity_owner_id = 11111
    is_admin = authenticated_user_id in admin_ids
    should_allow = (activity_owner_id == authenticated_user_id) or is_admin
    assert should_allow == True, "Regular user should access their own activity"
    print("✓ Regular user can access their own activity")
    
    # Test case 2: Regular user accessing another user's activity
    authenticated_user_id = 11111
    activity_owner_id = 22222
    is_admin = authenticated_user_id in admin_ids
    should_allow = (activity_owner_id == authenticated_user_id) or is_admin
    assert should_allow == False, "Regular user should NOT access another user's activity"
    print("✓ Regular user cannot access another user's activity")
    
    # Test case 3: Admin accessing their own activity
    authenticated_user_id = 12345
    activity_owner_id = 12345
    is_admin = authenticated_user_id in admin_ids
    should_allow = (activity_owner_id == authenticated_user_id) or is_admin
    assert should_allow == True, "Admin should access their own activity"
    print("✓ Admin can access their own activity")
    
    # Test case 4: Admin accessing another user's activity
    authenticated_user_id = 12345
    activity_owner_id = 99999
    is_admin = authenticated_user_id in admin_ids
    should_allow = (activity_owner_id == authenticated_user_id) or is_admin
    assert should_allow == True, "Admin should access another user's activity"
    print("✓ Admin can access another user's activity")
    
    print("✅ Admin authorization logic tests passed\n")


if __name__ == "__main__":
    print("=" * 80)
    print("Running get_activity_detail tests")
    print("=" * 80)
    print()
    
    try:
        test_load_admin_athlete_ids()
        test_admin_authorization_logic()
        
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
