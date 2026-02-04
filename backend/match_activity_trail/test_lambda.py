#!/usr/bin/env python3
"""
Test for match_activity_trail Lambda function

Tests:
1. Polyline decoding
2. Haversine distance calculation
3. Point to segment distance calculation
4. Handler activity_id extraction from different event formats
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

# Test the utility functions directly without importing boto3 clients


def decode_polyline(polyline_str):
    """
    Decode Google encoded polyline to list of (lat, lon) tuples.
    Algorithm: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    coordinates = []
    index = 0
    lat = 0
    lng = 0
    
    while index < len(polyline_str):
        # Decode latitude
        result = 0
        shift = 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        
        # Decode longitude
        result = 0
        shift = 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        
        coordinates.append((lat / 1e5, lng / 1e5))
    
    return coordinates


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees).
    """
    from math import radians, cos, sin, asin, sqrt
    
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    return c * r


def point_to_segment_distance(px, py, ax, ay, bx, by):
    """
    Calculate the minimum distance from a point (px, py) to a line segment (ax, ay) -> (bx, by).
    Uses the cross product method to find perpendicular distance.
    Returns distance in the same units as the input coordinates.
    """
    # Vector from a to b
    abx = bx - ax
    aby = by - ay
    
    # Vector from a to p
    apx = px - ax
    apy = py - ay
    
    # If segment is a point
    if abx == 0 and aby == 0:
        return haversine_distance(py, px, ay, ax)
    
    # Project point onto line (calculate t parameter)
    # t represents position along segment: 0 = point a, 1 = point b
    ab_ab = abx * abx + aby * aby
    ap_ab = apx * abx + apy * aby
    t = ap_ab / ab_ab
    
    # Clamp t to [0, 1] to stay within segment
    t = max(0, min(1, t))
    
    # Find closest point on segment
    closest_x = ax + t * abx
    closest_y = ay + t * aby
    
    # Return distance from point to closest point on segment
    return haversine_distance(py, px, closest_y, closest_x)


def test_decode_polyline():
    """Test Google polyline decoding"""
    print("Testing polyline decoding...")
    
    # Simple test polyline (represents a short path)
    # This is "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    polyline = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    coords = decode_polyline(polyline)
    
    # Should decode to approximately these coordinates
    assert len(coords) == 3, f"Expected 3 coordinates, got {len(coords)}"
    
    # Check first coordinate (approximately San Francisco)
    lat1, lon1 = coords[0]
    assert abs(lat1 - 38.5) < 1.0, f"Unexpected latitude: {lat1}"
    assert abs(lon1 + 120.2) < 1.0, f"Unexpected longitude: {lon1}"
    
    print(f"✓ Decoded {len(coords)} coordinates")
    print(f"  First point: ({lat1:.5f}, {lon1:.5f})")


def test_haversine_distance():
    """Test haversine distance calculation"""
    print("\nTesting haversine distance...")
    
    # Distance between two known points
    # Greenville, SC coordinates
    lat1, lon1 = 34.8526, -82.3940
    lat2, lon2 = 34.8500, -82.3900
    
    distance = haversine_distance(lat1, lon1, lat2, lon2)
    
    # Should be approximately 400-500 meters
    assert 300 < distance < 600, f"Unexpected distance: {distance}m"
    print(f"✓ Distance between test points: {distance:.2f}m")


def test_point_to_segment_distance():
    """Test point to segment distance calculation"""
    print("\nTesting point to segment distance...")
    
    # Simple test: point perpendicular to a segment
    # Segment from (0, 0) to (0, 1)
    # Point at (0.5, 0.5) should be approximately sqrt(2)/2 * 111km away
    
    # Using actual coordinates near Greenville, SC
    seg_lat1, seg_lon1 = 34.8526, -82.3940
    seg_lat2, seg_lon2 = 34.8500, -82.3940  # Straight north-south line
    
    # Point to the east
    point_lat, point_lon = 34.8513, -82.3900
    
    distance = point_to_segment_distance(point_lon, point_lat, seg_lon1, seg_lat1, seg_lon2, seg_lat2)
    
    # Should be approximately 300-400 meters (0.004 degrees longitude ≈ 350m at this latitude)
    assert 200 < distance < 500, f"Unexpected distance: {distance}m"
    print(f"✓ Point to segment distance: {distance:.2f}m")


def test_trail_tolerance():
    """Test that our tolerance value makes sense"""
    print("\nTesting trail tolerance...")
    
    # 50 meters is about 0.00045 degrees at this latitude
    # This is a reasonable tolerance for trail matching
    tolerance_meters = 50
    
    # Convert to approximate degrees at Greenville, SC latitude (34.85°)
    meters_per_degree_lat = 111000  # Approximately
    meters_per_degree_lon = 91000   # At 34.85° latitude
    
    tolerance_degrees_lat = tolerance_meters / meters_per_degree_lat
    tolerance_degrees_lon = tolerance_meters / meters_per_degree_lon
    
    print(f"✓ Tolerance: {tolerance_meters}m")
    print(f"  ≈ {tolerance_degrees_lat:.6f}° latitude")
    print(f"  ≈ {tolerance_degrees_lon:.6f}° longitude at 34.85°N")
    
    assert tolerance_degrees_lat < 0.001, "Tolerance should be less than 0.001 degrees"
    assert tolerance_degrees_lon < 0.001, "Tolerance should be less than 0.001 degrees"


def test_handler_activity_id_extraction():
    """Test that handler correctly extracts activity_id from different event formats"""
    print("\nTesting handler activity_id extraction...")
    
    # Add lambda function directory to path
    lambda_dir = os.path.dirname(__file__)
    if lambda_dir not in sys.path:
        sys.path.insert(0, lambda_dir)
    
    # Set required environment variables
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    # Import lambda_function with mocked boto3
    with patch('boto3.client'):
        if 'lambda_function' in sys.modules:
            del sys.modules['lambda_function']
        import lambda_function
        
        # Mock the match_activity function to avoid actual processing
        with patch.object(lambda_function, 'match_activity') as mock_match:
            mock_match.return_value = {
                "activity_id": 123,
                "distance_on_trail": 1000.0,
                "time_on_trail": 300,
                "message": "Test match"
            }
            
            # Test 1: Direct Lambda invocation (as used by match_unmatched_activities)
            print("  Test 1: Direct Lambda invocation format...")
            event1 = {"activity_id": 123}
            result1 = lambda_function.handler(event1, None)
            assert result1['statusCode'] == 200, "Expected status 200"
            mock_match.assert_called_with(123)
            print("  ✓ Direct invocation format works")
            
            mock_match.reset_mock()
            
            # Test 2: API Gateway with query string
            print("  Test 2: API Gateway query string format...")
            event2 = {"queryStringParameters": {"activity_id": "456"}}
            result2 = lambda_function.handler(event2, None)
            assert result2['statusCode'] == 200, "Expected status 200"
            mock_match.assert_called_with(456)
            print("  ✓ Query string format works")
            
            mock_match.reset_mock()
            
            # Test 3: API Gateway with JSON body
            print("  Test 3: API Gateway JSON body format...")
            event3 = {"body": json.dumps({"activity_id": 789})}
            result3 = lambda_function.handler(event3, None)
            assert result3['statusCode'] == 200, "Expected status 200"
            mock_match.assert_called_with(789)
            print("  ✓ JSON body format works")
            
            # Test 4: Missing activity_id
            print("  Test 4: Missing activity_id...")
            event4 = {}
            result4 = lambda_function.handler(event4, None)
            assert result4['statusCode'] == 400, f"Expected status 400, got {result4['statusCode']}"
            body = json.loads(result4['body'])
            assert 'error' in body, "Expected error in response"
            assert 'activity_id is required' in body['error'], "Expected activity_id required error"
            print("  ✓ Missing activity_id handled correctly")
    
    print("✓ All activity_id extraction tests passed")



if __name__ == '__main__':
    print("Running match_activity_trail tests...\n")
    print("=" * 60)
    
    try:
        test_decode_polyline()
        test_haversine_distance()
        test_point_to_segment_distance()
        test_trail_tolerance()
        test_handler_activity_id_extraction()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
