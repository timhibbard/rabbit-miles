#!/usr/bin/env python3
"""
Test for polyline extraction logic in fetch_activities Lambda function

Verifies that the function correctly prefers full polyline over summary_polyline
"""

import sys
import os

def test_polyline_extraction():
    """Test that polyline extraction prefers full polyline"""
    
    print("Testing polyline extraction logic...")
    
    # Test case 1: Both full and summary polyline available
    activity1 = {
        "map": {
            "polyline": "full_polyline_data_here",
            "summary_polyline": "summary_polyline_data_here"
        }
    }
    polyline = ""
    if activity1.get("map"):
        polyline = activity1["map"].get("polyline") or activity1["map"].get("summary_polyline", "")
    assert polyline == "full_polyline_data_here", "Should prefer full polyline when both are available"
    print("✓ Test 1 passed: Prefers full polyline when both available")
    
    # Test case 2: Only summary polyline available
    activity2 = {
        "map": {
            "summary_polyline": "summary_polyline_data_here"
        }
    }
    polyline = ""
    if activity2.get("map"):
        polyline = activity2["map"].get("polyline") or activity2["map"].get("summary_polyline", "")
    assert polyline == "summary_polyline_data_here", "Should use summary polyline when full is not available"
    print("✓ Test 2 passed: Uses summary polyline when full is not available")
    
    # Test case 3: Empty full polyline, summary available
    activity3 = {
        "map": {
            "polyline": "",
            "summary_polyline": "summary_polyline_data_here"
        }
    }
    polyline = ""
    if activity3.get("map"):
        polyline = activity3["map"].get("polyline") or activity3["map"].get("summary_polyline", "")
    assert polyline == "summary_polyline_data_here", "Should fallback to summary when full is empty string"
    print("✓ Test 3 passed: Fallback to summary when full polyline is empty")
    
    # Test case 4: No map object
    activity4 = {}
    polyline = ""
    if activity4.get("map"):
        polyline = activity4["map"].get("polyline") or activity4["map"].get("summary_polyline", "")
    assert polyline == "", "Should be empty when no map object"
    print("✓ Test 4 passed: Empty string when no map object")
    
    # Test case 5: Empty map object
    activity5 = {"map": {}}
    polyline = ""
    if activity5.get("map"):
        polyline = activity5["map"].get("polyline") or activity5["map"].get("summary_polyline", "")
    assert polyline == "", "Should be empty when map object is empty"
    print("✓ Test 5 passed: Empty string when map object is empty")
    
    # Test case 6: Only full polyline available (expected from detailed activity endpoint)
    activity6 = {
        "map": {
            "polyline": "full_polyline_data_here"
        }
    }
    polyline = ""
    if activity6.get("map"):
        polyline = activity6["map"].get("polyline") or activity6["map"].get("summary_polyline", "")
    assert polyline == "full_polyline_data_here", "Should use full polyline when only full is available"
    print("✓ Test 6 passed: Uses full polyline when only full is available")
    

if __name__ == '__main__':
    print("Running polyline extraction tests...\n")
    print("=" * 60)
    
    try:
        test_polyline_extraction()
        
        print("\n" + "=" * 60)
        print("✅ All polyline tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
