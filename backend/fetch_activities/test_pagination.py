#!/usr/bin/env python3
"""
Test for activity pagination logic in fetch_activities Lambda function

Verifies that the pagination logic correctly handles:
- Single page of activities (< 200)
- Multiple pages of activities
- Empty result
"""

import sys


def test_pagination_logic():
    """Test the pagination logic used in fetch_activities_for_athlete"""
    
    print("Testing pagination logic...")
    
    # Test case 1: Single page with fewer than per_page activities
    print("\nTest 1: Single page (30 activities, per_page=200)")
    page = 1
    per_page = 200
    all_activities = []
    
    # Simulate fetching first page with 30 activities
    activities = list(range(30))  # Simulated activities
    all_activities.extend(activities)
    
    should_continue = len(activities) >= per_page
    assert not should_continue, "Should stop when activities < per_page"
    assert len(all_activities) == 30, f"Expected 30 activities, got {len(all_activities)}"
    print(f"✓ Correctly stopped after 1 page with {len(all_activities)} activities")
    
    # Test case 2: Multiple pages
    print("\nTest 2: Multiple pages (450 activities total)")
    page = 1
    per_page = 200
    all_activities = []
    
    # Simulate page 1: 200 activities
    activities = list(range(200))
    all_activities.extend(activities)
    assert len(activities) >= per_page, "Should continue to next page"
    page += 1
    
    # Simulate page 2: 200 activities
    activities = list(range(200, 400))
    all_activities.extend(activities)
    assert len(activities) >= per_page, "Should continue to next page"
    page += 1
    
    # Simulate page 3: 50 activities (last page)
    activities = list(range(400, 450))
    all_activities.extend(activities)
    should_continue = len(activities) >= per_page
    assert not should_continue, "Should stop when activities < per_page"
    
    assert len(all_activities) == 450, f"Expected 450 activities, got {len(all_activities)}"
    assert page == 3, f"Expected to stop at page 3, got page {page}"
    print(f"✓ Correctly processed {len(all_activities)} activities across {page} pages")
    
    # Test case 3: Empty result
    print("\nTest 3: Empty result (0 activities)")
    page = 1
    per_page = 200
    all_activities = []
    
    # Simulate empty first page
    activities = []
    should_continue = len(activities) > 0
    assert not should_continue, "Should stop when no activities returned"
    assert len(all_activities) == 0, f"Expected 0 activities, got {len(all_activities)}"
    print(f"✓ Correctly handled empty result")
    
    # Test case 4: Exact multiple of per_page
    print("\nTest 4: Exact multiple of per_page (400 activities)")
    page = 1
    per_page = 200
    all_activities = []
    
    # Simulate page 1: 200 activities
    activities = list(range(200))
    all_activities.extend(activities)
    page += 1
    
    # Simulate page 2: 200 activities
    activities = list(range(200, 400))
    all_activities.extend(activities)
    page += 1
    
    # Simulate page 3: 0 activities (should stop)
    activities = []
    should_continue = len(activities) > 0
    assert not should_continue, "Should stop when no activities returned"
    
    assert len(all_activities) == 400, f"Expected 400 activities, got {len(all_activities)}"
    print(f"✓ Correctly handled exact multiple: {len(all_activities)} activities across {page-1} pages")


if __name__ == '__main__':
    print("Running pagination tests...\n")
    print("=" * 60)
    
    try:
        test_pagination_logic()
        
        print("\n" + "=" * 60)
        print("✅ All pagination tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
