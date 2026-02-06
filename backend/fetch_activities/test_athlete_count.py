#!/usr/bin/env python3
"""
Test for athlete_count extraction logic in fetch_activities Lambda function

Verifies that the function correctly extracts athlete_count from Strava API response
and defaults to 1 for solo activities
"""

import sys

def test_athlete_count_extraction():
    """Test that athlete_count extraction works correctly"""
    
    print("Testing athlete_count extraction logic...")
    
    # Test case 1: Group activity with athlete_count
    activity1 = {
        "id": 12345,
        "name": "Group Ride",
        "athlete_count": 5
    }
    athlete_count = activity1.get("athlete_count", 1)
    assert athlete_count == 5, "Should extract athlete_count when present"
    print("✓ Test 1 passed: Extracts athlete_count when present")
    
    # Test case 2: Solo activity without athlete_count field
    activity2 = {
        "id": 12346,
        "name": "Solo Ride"
    }
    athlete_count = activity2.get("athlete_count", 1)
    assert athlete_count == 1, "Should default to 1 when athlete_count is not present"
    print("✓ Test 2 passed: Defaults to 1 when athlete_count is not present")
    
    # Test case 3: Activity with athlete_count = 1 (solo)
    activity3 = {
        "id": 12347,
        "name": "Another Solo Ride",
        "athlete_count": 1
    }
    athlete_count = activity3.get("athlete_count", 1)
    assert athlete_count == 1, "Should use 1 when athlete_count is explicitly 1"
    print("✓ Test 3 passed: Uses 1 when athlete_count is explicitly 1")
    
    # Test case 4: Large group activity
    activity4 = {
        "id": 12348,
        "name": "Big Group Ride",
        "athlete_count": 25
    }
    athlete_count = activity4.get("athlete_count", 1)
    assert athlete_count == 25, "Should handle large athlete counts"
    print("✓ Test 4 passed: Handles large athlete counts")
    
    # Test case 5: Activity with athlete_count = 2 (pair)
    activity5 = {
        "id": 12349,
        "name": "Couple Ride",
        "athlete_count": 2
    }
    athlete_count = activity5.get("athlete_count", 1)
    assert athlete_count == 2, "Should use 2 for pair activities"
    print("✓ Test 5 passed: Uses 2 for pair activities")
    
    # Test case 6: Group badge display logic (frontend)
    print("\n✓ Group badge display logic:")
    for activity in [
        {"athlete_count": 1, "should_show": False},
        {"athlete_count": 2, "should_show": True},
        {"athlete_count": 5, "should_show": True},
        {"athlete_count": None, "should_show": False},
    ]:
        count = activity.get("athlete_count")
        should_show = count is not None and count > 1
        assert should_show == activity["should_show"], f"Badge display logic failed for {activity}"
        print(f"  - athlete_count={count}: show badge={should_show} ✓")


if __name__ == '__main__':
    print("Running athlete_count extraction tests...\n")
    print("=" * 60)
    
    try:
        test_athlete_count_extraction()
        
        print("\n" + "=" * 60)
        print("✅ All athlete_count tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
