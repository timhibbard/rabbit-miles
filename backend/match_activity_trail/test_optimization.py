#!/usr/bin/env python3
"""
Performance tests for match_activity_trail.calculate_trail_intersection.

These guard against the Lambda timing out on activities far from (or only
partly on) the trail. calculate_trail_intersection takes trail_segments as a
list of segments, each a list of (lat, lon) points, so the single synthetic
trails below are passed as [trail_coords].

The sampled "quick rejection" pass was removed in #335 (it falsely scored
on-trail activities as 0). The "off-trail" tests below now exercise the
whole-trail bounding box check and the per-piece bounding box prefilter in
the main loop, which keep the same speed guarantees.
"""

import sys
import os
import time
import json
from unittest.mock import patch

# Add lambda function directory to path
lambda_dir = os.path.dirname(__file__)
if lambda_dir not in sys.path:
    sys.path.insert(0, lambda_dir)

# Test data: Polyline from issue #116 (PFO hill repeats activity)
# This represents a real activity with 407 coordinate points
TEST_POLYLINE_NO_MATCH = (
    "ubrsEx~ouNOs@]w@QAm@XM@WEOQm@eBu@oC@[FKbB}@tGyCf@_@n@k@x@GjAe@xAu@z@i@f@c@j@Ct@W|KcFrB{@ZIJ@LLBLNRLFT?^"
    "`@^TZr@h@Zv@~@Vb@^\\LXz@h@BTK?QQu@[UU_@e@Oc@GKk@Sk@s@eAiA]k@Kq@KGEPNNPJZDx@r@^t@d@Vx@`A\\h@p@v@r@d@@LAFKAc@[e@Ss@u@Ss@e@"
    "MOKq@}@}@aAO]Qw@EGECID?R\\Th@Jl@h@b@x@b@Vd@d@d@v@`@\\Xd@p@b@DFAPMAUUs@[s@u@K_@ISc@KMIi@w@aAgAa@kAIMGEKFBJJJr@Rx@r@d@x@`@Xj@j@`@"
    "n@VT`@l@h@XJNAHK?QMw@_@w@w@Qo@GGk@OwBmCIOWaAGCKJDJTPh@HLLj@l@Xl@b@Zl@j@d@t@`@\\\\d@d@XHL@HEDGCSSu@[w@u@Kg@IMk@O_CwCM[Kq@KAKJDLLHh@"
    "Nz@t@JHVj@r@f@d@f@Vf@x@`Al@\\NVCJMCQUw@[i@i@MSSm@q@W{AiBYi@_@iAKCKJDJTPj@Lt@n@`@r@f@\\^`@n@bAx@z@n@d@BZ}@`Ak@`@eB~@aA`@g@\\y@XaC"
    "fA}BjAEFAH`@pADrAIhAQbAMXOPo@Zq@Q_B_GIMc@Bi@ISDc@v@k@PONEV@JJVJFRCfBiALOBOAWKWQI]DOPO`@GFk@PIFKT?JJZPLLArBwAFWAWEMOMc@@MNQb@"
    "GFg@NMHIJC\\HVJHT?fBiALOBi@IWKGa@BOJQb@KJk@PKJGTBVFNPHLAlBkAFKDYCYEMQK_@DOLSh@KHa@HOLIT@JJXJHR?rBuAD]AOGUQKY@SNQd@KJe@LQLEL?XL"
    "VRFRIdBkAFM@SGa@IIKCW@QJWp@SJa@JGFIVDXHLHDTAlBqAHYA[EMQM[BQJQf@KJk@NKJEHANDXFJJDRAjBoAHUAg@MOc@CURWj@m@PMLE\\BNLPTD|@g@r@i@DGD"
    "W?QGUKK_@?UNOd@IFu@ZKT?NHVHFTBjBqAJS@MA[CIUKYBONUj@o@ROLGTDXLPLBHChBmALU@SAMMWUE[Ja@r@KFe@L[^c@L[T_KrE[@IEs@eB"
)


def test_quick_rejection_bounding_box():
    """Test that activities completely outside trail bounding box are quickly rejected"""
    print("\nTesting bounding box quick rejection...")
    
    # Set required environment variables
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    with patch('boto3.client'):
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        import lambda_function
        
        # Trail in Greenville, SC area
        trail_coords = [
            (34.85, -82.39),
            (34.86, -82.40),
            (34.87, -82.41),
        ]
        
        # Activity completely outside (in New York)
        activity_coords = [
            (40.71, -74.01),  # New York City
            (40.72, -74.02),
            (40.73, -74.03),
        ]
        
        start_time = time.time()
        distance, time_ratio = lambda_function.calculate_trail_intersection(
            activity_coords, [trail_coords], 50
        )
        elapsed = time.time() - start_time
        
        assert distance == 0.0, f"Expected 0 distance, got {distance}"
        assert time_ratio == 0.0, f"Expected 0 time_ratio, got {time_ratio}"
        assert elapsed < 0.1, f"Expected quick rejection (<0.1s), took {elapsed:.3f}s"
        
        print(f"✓ Bounding box rejection completed in {elapsed:.3f}s")


def test_nearby_off_trail_activity_is_fast():
    """An activity parallel to the trail but ~1 km away scores 0, quickly.

    It sits inside the trail's bounding box, so it can't be rejected up front;
    the per-piece bounding box prefilter keeps the full scan cheap.
    """
    print("\nTesting nearby off-trail activity...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    with patch('boto3.client'):
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        import lambda_function
        
        # Trail in Greenville, SC area
        trail_coords = [(34.85 + i * 0.001, -82.39) for i in range(100)]
        
        # Activity nearby but not on trail (1km away)
        # 1km ≈ 0.009 degrees at this latitude
        activity_coords = [(34.85 + i * 0.001, -82.38) for i in range(100)]
        
        start_time = time.time()
        distance, time_ratio = lambda_function.calculate_trail_intersection(
            activity_coords, [trail_coords], 50  # 50m tolerance
        )
        elapsed = time.time() - start_time
        
        # ~1 km is far outside the 50 m tolerance
        assert distance == 0.0, f"Expected 0 distance, got {distance}"
        assert elapsed < 0.5, f"Expected fast off-trail scan (<0.5s), took {elapsed:.3f}s"

        print(f"✓ Off-trail scan completed in {elapsed:.3f}s")


def test_spatial_filtering_performance():
    """Test that spatial filtering reduces comparisons for activities with many points"""
    print("\nTesting spatial filtering performance...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    with patch('boto3.client'):
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        import lambda_function
        
        # Large trail with many points
        trail_coords = [(34.85 + i * 0.0001, -82.39 + (i % 10) * 0.0001) for i in range(1000)]
        
        # Activity with many points that overlaps trail
        activity_coords = [(34.85 + i * 0.0001, -82.39 + (i % 5) * 0.00005) for i in range(200)]
        
        start_time = time.time()
        distance, time_ratio = lambda_function.calculate_trail_intersection(
            activity_coords, [trail_coords], 50
        )
        elapsed = time.time() - start_time
        
        # Should complete reasonably fast with spatial filtering
        assert elapsed < 5.0, f"Expected completion <5s with spatial filtering, took {elapsed:.3f}s"
        
        print(f"✓ Spatial filtering test completed in {elapsed:.3f}s")
        print(f"  Distance on trail: {distance:.2f}m ({time_ratio * 100:.1f}%)")


def test_partly_on_trail_activity():
    """An activity that starts on the trail and then goes far away.

    Only the on-trail stretch counts, and the long off-trail tail stays cheap
    (early termination was removed in f8bfd8a; the per-piece prefilter keeps
    this fast instead).
    """
    print("\nTesting partly on-trail activity...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    with patch('boto3.client'):
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        import lambda_function
        
        # Trail
        trail_coords = [(34.85 + i * 0.0001, -82.39) for i in range(100)]
        
        # Activity that starts on trail then goes far away for many segments
        activity_coords = []
        # First 10 segments on trail
        for i in range(10):
            activity_coords.append((34.85 + i * 0.0001, -82.39))
        # Then 200 segments far away
        for i in range(200):
            activity_coords.append((40.71 + i * 0.0001, -74.01))
        
        start_time = time.time()
        distance, time_ratio = lambda_function.calculate_trail_intersection(
            activity_coords, [trail_coords], 50
        )
        elapsed = time.time() - start_time
        
        assert elapsed < 2.0, f"Expected completion <2s, took {elapsed:.3f}s"
        assert distance > 0, f"Expected some distance on trail, got {distance}"
        # The on-trail stretch is 9 x ~11 m; the jump to New York must not count.
        assert distance < 200, f"Expected only the on-trail stretch to count, got {distance:.0f}m"

        print(f"✓ Partly on-trail test completed in {elapsed:.3f}s")
        print(f"  Found {distance:.2f}m on trail")


def test_realistic_no_match_scenario():
    """Test with realistic coordinates that don't match (similar to the issue)"""
    print("\nTesting realistic no-match scenario...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    with patch('boto3.client'):
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        import lambda_function
        
        # Decode the actual polyline from the issue (defined as constant at top of file)
        activity_coords = lambda_function.decode_polyline(TEST_POLYLINE_NO_MATCH)
        
        # Create trail coordinates in Greenville SC area (different from the activity)
        # This simulates the Rabbit Trail
        trail_coords = [(34.85 + i * 0.0001, -82.39 + (i % 20) * 0.00005) for i in range(3600)]
        
        print(f"  Activity has {len(activity_coords)} coordinates")
        print(f"  Trail has {len(trail_coords)} coordinates")
        print(f"  Without optimization: {len(activity_coords)} * {len(trail_coords)} = {len(activity_coords) * len(trail_coords):,} potential comparisons")
        
        start_time = time.time()
        distance, time_ratio = lambda_function.calculate_trail_intersection(
            activity_coords, [trail_coords], 50
        )
        elapsed = time.time() - start_time
        
        # Should complete quickly (well under 45s timeout)
        assert elapsed < 5.0, f"Expected completion <5s, took {elapsed:.3f}s"
        print(f"✓ Realistic scenario completed in {elapsed:.3f}s (vs 45s timeout)")
        print(f"  Result: {distance:.2f}m on trail ({time_ratio * 100:.1f}%)")


if __name__ == '__main__':
    print("Running match_activity_trail optimization tests...\n")
    print("=" * 60)
    
    try:
        test_quick_rejection_bounding_box()
        test_nearby_off_trail_activity_is_fast()
        test_spatial_filtering_performance()
        test_partly_on_trail_activity()
        test_realistic_no_match_scenario()
        
        print("\n" + "=" * 60)
        print("✅ All optimization tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
