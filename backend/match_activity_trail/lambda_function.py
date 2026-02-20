# match_activity_trail Lambda function
# Calculates how much of an activity was on the trail
# 
# This Lambda can be triggered by:
# 1. SQS message with activity details (automated webhook processing)
# 2. Direct invocation with activity_id for testing
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# TRAIL_DATA_BUCKET (e.g., rabbitmiles-trail-data)

import os
import json
import boto3
from datetime import datetime, timedelta

rds = boto3.client("rds-data")
s3 = boto3.client("s3")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
TRAIL_DATA_BUCKET = os.environ.get("TRAIL_DATA_BUCKET", "rabbitmiles-trail-data")

# Trail tolerance in meters (25m on each side = 50m buffer zone)
TRAIL_TOLERANCE_METERS = 25


def _exec_sql(sql, parameters=None):
    """Execute SQL statement using RDS Data API"""
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


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


def load_trail_data_from_s3():
    """Load trail GeoJSON data from S3 bucket"""
    print(f"Loading trail data from S3 bucket: {TRAIL_DATA_BUCKET}")
    
    trail_segments = []
    
    # Load main trail
    try:
        response = s3.get_object(Bucket=TRAIL_DATA_BUCKET, Key="trails/main.geojson")
        main_geojson = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extract coordinates from GeoJSON features
        # Keep each feature's coordinates as a separate segment to avoid spurious connections
        for feature in main_geojson.get('features', []):
            geometry = feature.get('geometry', {})
            if geometry.get('type') == 'LineString':
                coords = geometry.get('coordinates', [])
                # GeoJSON uses [lon, lat] format, convert to [lat, lon]
                segment = [(lat, lon) for lon, lat in coords]
                if len(segment) >= 2:  # Only add segments with at least 2 points
                    trail_segments.append(segment)
            elif geometry.get('type') == 'MultiLineString':
                for line in geometry.get('coordinates', []):
                    segment = [(lat, lon) for lon, lat in line]
                    if len(segment) >= 2:
                        trail_segments.append(segment)
        
        print(f"Loaded {len(trail_segments)} trail segments from main trail")
    except Exception as e:
        print(f"Error loading main trail: {e}")
    
    # Load spurs trail
    try:
        response = s3.get_object(Bucket=TRAIL_DATA_BUCKET, Key="trails/spurs.geojson")
        spurs_geojson = json.loads(response['Body'].read().decode('utf-8'))
        
        spur_segments = 0
        for feature in spurs_geojson.get('features', []):
            geometry = feature.get('geometry', {})
            if geometry.get('type') == 'LineString':
                coords = geometry.get('coordinates', [])
                segment = [(lat, lon) for lon, lat in coords]
                if len(segment) >= 2:
                    trail_segments.append(segment)
                    spur_segments += 1
            elif geometry.get('type') == 'MultiLineString':
                for line in geometry.get('coordinates', []):
                    segment = [(lat, lon) for lon, lat in line]
                    if len(segment) >= 2:
                        trail_segments.append(segment)
                        spur_segments += 1
        
        print(f"Loaded {spur_segments} trail segments from spurs trail")
    except Exception as e:
        print(f"Error loading spurs trail: {e}")
    
    if not trail_segments:
        raise RuntimeError("No trail data loaded from S3")
    
    return trail_segments


def calculate_trail_intersection(activity_coords, trail_segments, tolerance_meters):
    """
    Calculate how much of the activity was on the trail.
    
    Args:
        activity_coords: List of (lat, lon) tuples for activity
        trail_segments: List of trail segments, where each segment is a list of (lat, lon) tuples
        tolerance_meters: Distance tolerance in meters
    
    Returns:
        tuple: (distance_on_trail_meters, time_ratio)
    """
    if not activity_coords or not trail_segments:
        return 0.0, 0.0
    
    # Flatten trail segments to calculate bounding box
    all_trail_points = [point for segment in trail_segments for point in segment]
    
    print(f"Calculating intersection: {len(activity_coords)} activity points vs {len(trail_segments)} trail segments")
    
    # OPTIMIZATION 1: Quick rejection test using bounding boxes
    # Calculate bounding boxes for both activity and trail
    activity_lats = [lat for lat, lon in activity_coords]
    activity_lons = [lon for lat, lon in activity_coords]
    trail_lats = [lat for lat, lon in all_trail_points]
    trail_lons = [lon for lat, lon in all_trail_points]
    
    activity_bbox = {
        'min_lat': min(activity_lats), 'max_lat': max(activity_lats),
        'min_lon': min(activity_lons), 'max_lon': max(activity_lons)
    }
    trail_bbox = {
        'min_lat': min(trail_lats), 'max_lat': max(trail_lats),
        'min_lon': min(trail_lons), 'max_lon': max(trail_lons)
    }
    
    # Convert tolerance to approximate degrees (rough approximation: 1 degree ≈ 111km)
    tolerance_degrees = tolerance_meters / 111000.0
    
    # Check if bounding boxes are completely separated (with tolerance buffer)
    if (activity_bbox['max_lat'] + tolerance_degrees < trail_bbox['min_lat'] or
        activity_bbox['min_lat'] - tolerance_degrees > trail_bbox['max_lat'] or
        activity_bbox['max_lon'] + tolerance_degrees < trail_bbox['min_lon'] or
        activity_bbox['min_lon'] - tolerance_degrees > trail_bbox['max_lon']):
        print(f"Quick rejection: Activity bounding box completely outside trail area")
        return 0.0, 0.0
    
    # OPTIMIZATION 2: Sample-based quick check
    # Check a sample of activity points to see if any are near the trail.
    # Use a larger sample and a more forgiving tolerance to avoid false negatives.
    sample_size = min(20, len(activity_coords))
    sample_indices = [i * (len(activity_coords) - 1) // max(1, sample_size - 1) for i in range(sample_size)]
    found_nearby = False
    
    for idx in sample_indices:
        if idx >= len(activity_coords):
            continue
        lat, lon = activity_coords[idx]
        
        # Check against trail segments (sample more segments for better coverage)
        for seg_idx in range(0, len(trail_segments), max(1, len(trail_segments) // 20)):
            segment = trail_segments[seg_idx]
            
            # Check a sample of points in this segment
            for j in range(0, len(segment) - 1, max(1, len(segment) // 10)):
                trail_lat1, trail_lon1 = segment[j]
                trail_lat2, trail_lon2 = segment[j + 1] if j + 1 < len(segment) else segment[j]
                
                distance_to_trail = point_to_segment_distance(
                    lon, lat,
                    trail_lon1, trail_lat1,
                    trail_lon2, trail_lat2
                )
                
                if distance_to_trail <= tolerance_meters * 5:  # Use 5x tolerance for sampling
                    found_nearby = True
                    break
            
            if found_nearby:
                break
        
        if found_nearby:
            break
    
    # If no sample points are even remotely near the trail, return 0
    if not found_nearby:
        print(f"Quick rejection: No sample points within 5x tolerance of trail")
        return 0.0, 0.0
    
    # Process activity segments to determine which portions are on the trail
    # Track which activity segments are on the trail
    on_trail_segments = []
    total_distance = 0.0
    
    # Check each segment of the activity path
    for i in range(len(activity_coords) - 1):
        lat1, lon1 = activity_coords[i]
        lat2, lon2 = activity_coords[i + 1]
        
        # Calculate segment length
        segment_distance = haversine_distance(lat1, lon1, lat2, lon2)
        total_distance += segment_distance
        
        # Check if segment midpoint is within tolerance of any trail segment
        mid_lat = (lat1 + lat2) / 2
        mid_lon = (lon1 + lon2) / 2
        
        is_on_trail = False
        
        # OPTIMIZATION 4: Check each trail segment separately (avoids spurious connections)
        for segment in trail_segments:
            if is_on_trail:
                break
                
            # Check each line segment within this trail segment
            for j in range(len(segment) - 1):
                trail_lat1, trail_lon1 = segment[j]
                trail_lat2, trail_lon2 = segment[j + 1]
                
                # Quick bounding box check before expensive distance calculation
                trail_seg_min_lat = min(trail_lat1, trail_lat2) - tolerance_degrees
                trail_seg_max_lat = max(trail_lat1, trail_lat2) + tolerance_degrees
                trail_seg_min_lon = min(trail_lon1, trail_lon2) - tolerance_degrees
                trail_seg_max_lon = max(trail_lon1, trail_lon2) + tolerance_degrees
                
                # Skip if activity point is clearly outside this trail segment's bounding box
                if (mid_lat < trail_seg_min_lat or mid_lat > trail_seg_max_lat or
                    mid_lon < trail_seg_min_lon or mid_lon > trail_seg_max_lon):
                    continue
                
                # Calculate distance from activity segment midpoint to trail segment
                distance_to_trail = point_to_segment_distance(
                    mid_lon, mid_lat,
                    trail_lon1, trail_lat1,
                    trail_lon2, trail_lat2
                )
                
                if distance_to_trail <= tolerance_meters:
                    is_on_trail = True
                    break
        
        on_trail_segments.append((is_on_trail, segment_distance))
    
    # Calculate distance on trail
    distance_on_trail = sum(dist for on_trail, dist in on_trail_segments if on_trail)
    
    # Calculate time ratio (proportional to distance)
    # This is a simplified estimation assuming constant speed
    time_ratio = distance_on_trail / total_distance if total_distance > 0 else 0.0
    
    print(f"Results: {distance_on_trail:.2f}m on trail out of {total_distance:.2f}m total ({time_ratio * 100:.1f}%)")
    
    return distance_on_trail, time_ratio


def get_activity_from_db(activity_id):
    """Fetch activity details from database"""
    sql = """
    SELECT athlete_id, strava_activity_id, polyline, moving_time, distance, COALESCE(distance_on_trail, 0) as distance_on_trail
    FROM activities
    WHERE id = :id
    """
    params = [{"name": "id", "value": {"longValue": activity_id}}]
    
    result = _exec_sql(sql, params)
    records = result.get("records", [])
    
    if not records:
        return None
    
    record = records[0]
    
    # Handle DECIMAL fields that come back as stringValue
    distance_str = record[4].get("stringValue")
    distance = float(distance_str) if distance_str else 0.0
    
    distance_on_trail_field = record[5]
    if "doubleValue" in distance_on_trail_field:
        old_distance_on_trail = float(distance_on_trail_field["doubleValue"])
    elif "stringValue" in distance_on_trail_field:
        old_distance_on_trail = float(distance_on_trail_field["stringValue"])
    else:
        old_distance_on_trail = 0.0
    
    return {
        "activity_id": activity_id,
        "athlete_id": int(record[0].get("longValue", 0)),
        "strava_activity_id": int(record[1].get("longValue", 0)),
        "polyline": record[2].get("stringValue", ""),
        "moving_time": int(record[3].get("longValue", 0)),
        "distance": distance,
        "old_distance_on_trail": old_distance_on_trail
    }


def update_activity_trail_metrics(activity_id, distance_on_trail, time_on_trail):
    """Update activity with trail metrics and last_matched timestamp"""
    sql = """
    UPDATE activities
    SET distance_on_trail = :dist,
        time_on_trail = :time,
        last_matched = CAST(:matched_at AS TIMESTAMP)
    WHERE id = :id
    """
    
    params = [
        {"name": "dist", "value": {"doubleValue": float(distance_on_trail)}},
        {"name": "time", "value": {"longValue": time_on_trail}},
        {"name": "matched_at", "value": {"stringValue": datetime.utcnow().isoformat()}},
        {"name": "id", "value": {"longValue": activity_id}},
    ]
    
    _exec_sql(sql, params)
    print(f"Updated activity {activity_id} with trail metrics")


def get_window_keys(start_date_local):
    """
    Calculate window keys (week, month, year) for an activity based on its start date.
    
    Args:
        start_date_local: ISO 8601 timestamp string (e.g., "2026-02-15T10:30:00Z")
    
    Returns:
        Dict with 'week', 'month', 'year' keys containing window_key strings
    """
    try:
        # Parse ISO 8601 timestamp (can be with or without timezone)
        dt_str = start_date_local.replace('Z', '+00:00')
        if '+' not in dt_str and dt_str.count(':') == 2:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str)
        
        # Week: ISO week format, Monday is start of week
        # Window key format: week_YYYY-MM-DD (Monday of the week)
        days_since_monday = dt.weekday()  # Monday is 0
        monday = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if days_since_monday > 0:
            monday = monday - timedelta(days=days_since_monday)
        week_key = f"week_{monday.strftime('%Y-%m-%d')}"
        
        # Month: YYYY-MM
        month_key = f"month_{dt.strftime('%Y-%m')}"
        
        # Year: YYYY
        year_key = f"year_{dt.strftime('%Y')}"
        
        return {
            'week': week_key,
            'month': month_key,
            'year': year_key
        }
    except Exception as e:
        print(f"ERROR: Failed to parse activity date {start_date_local}: {e}")
        return None


def update_leaderboard_after_trail_matching(activity_id, athlete_id, distance_on_trail, old_distance_on_trail):
    """
    Update leaderboard aggregates after trail matching completes.
    
    Args:
        activity_id: The activity ID
        athlete_id: The athlete ID
        distance_on_trail: New distance_on_trail value (after matching)
        old_distance_on_trail: Old distance_on_trail value (before matching, usually 0)
    """
    try:
        # Check if user has opted in to leaderboards
        check_sql = "SELECT show_on_leaderboards FROM users WHERE athlete_id = :aid"
        check_params = [{"name": "aid", "value": {"longValue": athlete_id}}]
        check_result = _exec_sql(check_sql, check_params)
        
        if not check_result.get("records") or not check_result["records"][0][0].get("booleanValue", False):
            print(f"User {athlete_id} has opted out of leaderboards, skipping aggregation")
            return
        
        # Get activity details for window calculation
        sql = "SELECT start_date_local, type FROM activities WHERE id = :id"
        params = [{"name": "id", "value": {"longValue": activity_id}}]
        result = _exec_sql(sql, params)
        
        if not result.get("records"):
            print(f"Activity {activity_id} not found")
            return
        
        record = result["records"][0]
        start_date_local = record[0].get("stringValue", "")
        activity_type = record[1].get("stringValue", "")
        
        if not start_date_local:
            print(f"Activity {activity_id} has no start_date_local")
            return
        
        # Calculate delta (new - old distance_on_trail)
        distance_delta = distance_on_trail - old_distance_on_trail
        
        if distance_delta == 0:
            print(f"No change in distance_on_trail for activity {activity_id}, skipping leaderboard update")
            return
        
        # Calculate window keys
        window_keys = get_window_keys(start_date_local)
        if not window_keys:
            print(f"Failed to calculate window keys for activity {activity_id}")
            return
        
        # Determine aggregate activity types to update
        agg_types = ["all"]  # Always update 'all'
        if activity_type in ["Run", "Walk"]:
            agg_types.append("foot")
        elif activity_type == "Ride":
            agg_types.append("bike")
        
        # Update aggregates for each window (week, month, year) and each activity type
        metric = "distance"
        for window, window_key in window_keys.items():
            for agg_activity_type in agg_types:
                sql = """
                INSERT INTO leaderboard_agg ("window", window_key, metric, activity_type, athlete_id, value, last_updated)
                VALUES (:window, :window_key, :metric, :act_type, :aid, :value, now())
                ON CONFLICT (window_key, metric, activity_type, athlete_id)
                DO UPDATE SET
                    value = leaderboard_agg.value + EXCLUDED.value,
                    last_updated = now()
                """
                
                params = [
                    {"name": "window", "value": {"stringValue": window}},
                    {"name": "window_key", "value": {"stringValue": window_key}},
                    {"name": "metric", "value": {"stringValue": metric}},
                    {"name": "act_type", "value": {"stringValue": agg_activity_type}},
                    {"name": "aid", "value": {"longValue": athlete_id}},
                    {"name": "value", "value": {"doubleValue": distance_delta}},
                ]
                
                _exec_sql(sql, params)
                print(f"Updated leaderboard aggregate after trail matching: {window_key} athlete={athlete_id} type={agg_activity_type} delta={distance_delta:.2f}m")
        
        print(f"Leaderboard updated for activity {activity_id}")
        
    except Exception as e:
        print(f"ERROR: Failed to update leaderboard for activity {activity_id}: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the trail matching if leaderboard update fails


def match_activity(activity_id):
    """Match a single activity against trail data"""
    print(f"Matching activity {activity_id} against trail")
    
    # Initialize variables early to avoid NameError in exception handlers
    athlete_id = None
    old_distance_on_trail = 0.0
    
    try:
        # Get activity from database
        activity = get_activity_from_db(activity_id)
        
        if not activity:
            raise ValueError(f"Activity {activity_id} not found in database")
        
        athlete_id = activity.get("athlete_id")
        if not athlete_id:
            raise ValueError(f"Activity {activity_id} has no athlete_id")
        
        old_distance_on_trail = activity.get("old_distance_on_trail", 0.0)
        
        polyline = activity.get("polyline", "")
        if not polyline:
            print(f"Activity {activity_id} has no polyline data, skipping")
            # Still update last_matched to indicate we checked
            update_activity_trail_metrics(activity_id, 0.0, 0)
            # Update leaderboard if distance_on_trail changed
            update_leaderboard_after_trail_matching(activity_id, athlete_id, 0.0, old_distance_on_trail)
            return {
                "activity_id": activity_id,
                "distance_on_trail": 0.0,
                "time_on_trail": 0,
                "message": "No polyline data"
            }
        
        # Decode activity polyline
        print(f"Decoding polyline for activity {activity_id}")
        activity_coords = decode_polyline(polyline)
        print(f"Decoded {len(activity_coords)} coordinates")
        
        # Try to match against trail data
        # If any error occurs (trail data unavailable, calculation fails, etc.),
        # still update the database with 0 values to indicate we attempted matching
        try:
            # Load trail data from S3
            trail_segments = load_trail_data_from_s3()
            
            # Calculate intersection
            distance_on_trail, time_ratio = calculate_trail_intersection(
                activity_coords, trail_segments, TRAIL_TOLERANCE_METERS
            )
            
            # Calculate time on trail based on moving_time
            moving_time = activity.get("moving_time", 0)
            time_on_trail = int(moving_time * time_ratio)
            
            # Update database
            update_activity_trail_metrics(activity_id, distance_on_trail, time_on_trail)
            
            # Update leaderboard aggregates
            update_leaderboard_after_trail_matching(activity_id, athlete_id, distance_on_trail, old_distance_on_trail)
            
            print(f"Activity {activity_id} matched: {distance_on_trail:.2f}m, {time_on_trail}s on trail")
            
            return {
                "activity_id": activity_id,
                "distance_on_trail": distance_on_trail,
                "time_on_trail": time_on_trail,
                "message": "Successfully matched"
            }
        except Exception as e:
            # If matching fails for any reason, still update last_matched with 0 values
            print(f"Failed to match activity {activity_id} against trail: {e}")
            print("Setting distance_on_trail=0, time_on_trail=0, and updating last_matched")
            update_activity_trail_metrics(activity_id, 0.0, 0)
            # Update leaderboard if athlete_id is available
            if athlete_id:
                update_leaderboard_after_trail_matching(activity_id, athlete_id, 0.0, old_distance_on_trail)
            return {
                "activity_id": activity_id,
                "distance_on_trail": 0.0,
                "time_on_trail": 0,
                "message": f"Matching failed: {str(e)}"
            }
    except Exception as outer_e:
        # Handle errors in the outer try block (e.g., activity not found)
        print(f"ERROR: Failed to process activity {activity_id}: {outer_e}")
        import traceback
        traceback.print_exc()
        return {
            "activity_id": activity_id,
            "distance_on_trail": 0.0,
            "time_on_trail": 0,
            "message": f"Processing failed: {str(outer_e)}"
        }


def handler(event, context):
    """
    Lambda handler for matching activities to trail.
    
    Accepts:
    1. Direct invocation with activity_id in body/query: {"activity_id": 123}
    2. SQS message with activity details (from webhook processor)
    """
    print(f"match_activity_trail handler invoked")
    print(f"Event: {json.dumps(event, default=str)}")
    
    # Validate required environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }
    
    if not TRAIL_DATA_BUCKET:
        print("ERROR: Missing TRAIL_DATA_BUCKET")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }
    
    try:
        # Handle SQS trigger
        if "Records" in event:
            print(f"Processing {len(event['Records'])} SQS records")
            results = []
            
            for record in event["Records"]:
                message_body = json.loads(record.get("body", "{}"))
                activity_id = message_body.get("activity_id")
                
                if not activity_id:
                    print(f"Skipping SQS record without activity_id: {record.get('messageId')}")
                    continue
                
                try:
                    result = match_activity(activity_id)
                    results.append(result)
                except Exception as e:
                    print(f"Error matching activity {activity_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue processing other records
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": f"Processed {len(results)} activities",
                    "results": results
                })
            }
        
        # Handle direct invocation
        else:
            # Parse activity_id from body
            # For direct Lambda invocation, pass: {"activity_id": 123}
            # For API Gateway invocation, can use query string: ?activity_id=123
            body = {}
            if event.get("body"):
                try:
                    body = json.loads(event["body"])
                except json.JSONDecodeError:
                    pass
            
            # Try multiple sources for activity_id:
            # 1. Direct in event (for Lambda-to-Lambda invocation)
            # 2. In body (for API Gateway with body)
            # 3. In queryStringParameters (for API Gateway with query string)
            activity_id = event.get("activity_id")
            if not activity_id:
                activity_id = body.get("activity_id")
            if not activity_id:
                query_params = event.get("queryStringParameters") or {}
                activity_id = query_params.get("activity_id")
            
            if not activity_id:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "activity_id is required in body or query string"})
                }
            
            activity_id = int(activity_id)
            result = match_activity(activity_id)
            
            return {
                "statusCode": 200,
                "body": json.dumps(result)
            }
    
    except ValueError as e:
        print(f"Validation error: {e}")
        return {
            "statusCode": 404,
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        print(f"Error in match_activity_trail handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error"})
        }
