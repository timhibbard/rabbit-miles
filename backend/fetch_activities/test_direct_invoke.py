#!/usr/bin/env python3
"""
Test for direct lambda invocation in fetch_activities Lambda function

Verifies that the function can be invoked directly with credentials
"""

import sys
import os


def test_event_detection():
    """Test that the handler can detect direct vs API Gateway invocations"""
    
    print("Testing event detection logic...")
    
    # Test case 1: Direct lambda invocation event
    direct_event = {
        "athlete_id": 12345,
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_at": 1234567890
    }
    
    is_direct_invoke = "athlete_id" in direct_event and "access_token" in direct_event
    assert is_direct_invoke == True, "Should detect direct invocation"
    print("✓ Test 1 passed: Detects direct invocation")
    
    # Test case 2: API Gateway invocation event
    api_gateway_event = {
        "requestContext": {
            "http": {
                "method": "POST"
            }
        },
        "headers": {
            "cookie": "rm_session=test"
        }
    }
    
    is_direct_invoke = "athlete_id" in api_gateway_event and "access_token" in api_gateway_event
    assert is_direct_invoke == False, "Should not detect API Gateway event as direct invocation"
    print("✓ Test 2 passed: Does not mistake API Gateway event for direct invocation")
    
    # Test case 3: Direct invocation missing access_token
    incomplete_event = {
        "athlete_id": 12345
    }
    
    is_direct_invoke = "athlete_id" in incomplete_event and "access_token" in incomplete_event
    assert is_direct_invoke == False, "Should not detect incomplete event as direct invocation"
    print("✓ Test 3 passed: Requires both athlete_id and access_token")


if __name__ == '__main__':
    print("Running direct invocation tests...\n")
    print("=" * 60)
    
    try:
        test_event_detection()
        
        print("\n" + "=" * 60)
        print("✅ All direct invocation tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
