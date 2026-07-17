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
import sys
import json
import boto3
from datetime import datetime

# Add parent directory to path to import shared modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import leaderboard_agg

rds = boto3.client("rds-data")
s3 = boto3.client("s3")
sqs = boto3.client("sqs")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
TRAIL_DATA_BUCKET = os.environ.get("TRAIL_DATA_BUCKET", "rabbitmiles-trail-data")
EMAIL_QUEUE_URL = os.environ.get("EMAIL_QUEUE_URL", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://rabbitmiles.com").rstrip("/")

# Trail tolerance in meters (25m on each side = 50m buffer zone)
TRAIL_TOLERANCE_METERS = 25

# Maximum activity age (in minutes) to send notifications
# Only send notifications for activities created within this window
# This prevents notifications for backfills, historical imports, etc.
MAX_ACTIVITY_AGE_MINUTES = 10


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
    """Fetch activity details from database.

    Returns the metadata `leaderboard_agg.recompute_for_activity` needs
    (start_date_local, activity timezone, user timezone) so the post-match
    leaderboard recompute can run without an extra round-trip.
    """
    sql = """
    SELECT a.athlete_id, a.strava_activity_id, a.polyline, a.moving_time, a.distance,
           a.start_date_local, a.timezone AS activity_timezone, u.timezone AS user_timezone
      FROM activities a
      LEFT JOIN users u ON u.athlete_id = a.athlete_id
     WHERE a.id = :id
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

    start_date_local = record[5].get("stringValue") if not record[5].get("isNull") else ""
    activity_timezone = record[6].get("stringValue") if not record[6].get("isNull") else None
    user_timezone = record[7].get("stringValue") if not record[7].get("isNull") else None

    return {
        "activity_id": activity_id,
        "athlete_id": int(record[0].get("longValue", 0)),
        "strava_activity_id": int(record[1].get("longValue", 0)),
        "polyline": record[2].get("stringValue", ""),
        "moving_time": int(record[3].get("longValue", 0)),
        "distance": distance,
        "start_date_local": start_date_local,
        "activity_timezone": activity_timezone,
        "user_timezone": user_timezone,
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


def get_current_rankings(athlete_id, start_date_local, user_timezone=None, activity_timezone=None):
    """Get user's current rankings before leaderboard is recomputed.

    Returns dict with keys like 'week_all', 'month_foot', 'year_bike' mapping to rank numbers.
    Returns empty dict if window bounds can't be computed or user not found.

    Optimized to use a single query with UNION ALL instead of 9 separate queries.
    """
    bounds = leaderboard_agg.get_window_bounds(start_date_local, user_timezone, activity_timezone)
    if not bounds:
        return {}

    # Build list of window_keys for the query
    window_keys = [window_key for _, (window_key, _, _) in bounds.items()]

    # Single query to get all rankings at once
    sql = """
        WITH ranked AS (
            SELECT
                window_key,
                activity_type,
                athlete_id,
                ROW_NUMBER() OVER (
                    PARTITION BY window_key, activity_type
                    ORDER BY value DESC
                ) as rank
            FROM leaderboard_agg
            WHERE window_key IN (:wk0, :wk1, :wk2)
              AND metric = :metric
              AND value > 0
        )
        SELECT window_key, activity_type, rank
        FROM ranked
        WHERE athlete_id = :athlete_id
    """

    params = [
        {"name": "wk0", "value": {"stringValue": window_keys[0] if len(window_keys) > 0 else ""}},
        {"name": "wk1", "value": {"stringValue": window_keys[1] if len(window_keys) > 1 else ""}},
        {"name": "wk2", "value": {"stringValue": window_keys[2] if len(window_keys) > 2 else ""}},
        {"name": "metric", "value": {"stringValue": "distance"}},
        {"name": "athlete_id", "value": {"longValue": int(athlete_id)}}
    ]

    try:
        result = _exec_sql(sql, params)
        records = result.get("records", [])

        # Build window_key -> window_name mapping for fast lookup
        window_key_to_name = {window_key: name for name, (window_key, _, _) in bounds.items()}

        rankings = {}
        for record in records:
            if len(record) >= 3:
                window_key = record[0].get("stringValue", "")
                activity_type = record[1].get("stringValue", "")
                rank = record[2].get("longValue")

                window_name = window_key_to_name.get(window_key)
                if window_name and rank:
                    rankings[f"{window_name}_{activity_type}"] = rank

        return rankings

    except Exception as e:
        print(f"WARNING: Failed to get rankings: {e}")
        return {}


def check_ranking_changes(athlete_id, old_rankings, start_date_local, user_timezone=None, activity_timezone=None):
    """Compare old vs new rankings and return list of meaningful improvements.

    Only returns changes that are worth notifying about:
    - Entering top 10
    - Multi-position improvement (jumped 2+ positions)
    - Crossing milestone boundaries (e.g., 11→10, 26→25, 51→50, 101→100)

    Returns list of dicts with keys: window, activity_type, old_rank, new_rank
    """
    # Get new rankings after leaderboard recompute
    new_rankings = get_current_rankings(athlete_id, start_date_local, user_timezone, activity_timezone)

    # Milestone thresholds that are worth celebrating
    MILESTONES = [10, 25, 50, 100]

    changes = []
    for key, new_rank in new_rankings.items():
        old_rank = old_rankings.get(key)

        # Check if this is a meaningful improvement
        is_meaningful = False

        if old_rank is None and new_rank:
            # Newly ranked - only notify if in top 10
            is_meaningful = new_rank <= 10
        elif old_rank and new_rank and new_rank < old_rank:
            improvement = old_rank - new_rank

            # Notify if:
            # 1. Now in top 10, OR
            # 2. Jumped 2+ positions, OR
            # 3. Crossed a milestone boundary
            if new_rank <= 10:
                is_meaningful = True
            elif improvement >= 2:
                is_meaningful = True
            else:
                # Check if crossed a milestone (e.g., 11→10, 26→25)
                for milestone in MILESTONES:
                    if old_rank > milestone >= new_rank:
                        is_meaningful = True
                        break

        if is_meaningful:
            window, agg_type = key.rsplit("_", 1)
            changes.append({
                "window": window,
                "activity_type": agg_type,
                "old_rank": old_rank,
                "new_rank": new_rank
            })

    return changes


def queue_email_notification(notification_type, athlete_id, activity_id, metadata):
    """Queue email notification for async processing via SQS.

    Args:
        notification_type: 'trail_milestone' or 'ranking_change'
        athlete_id: User's athlete ID
        activity_id: Activity database ID
        metadata: Dict with notification-specific data
    """
    if not EMAIL_QUEUE_URL:
        print("WARNING: EMAIL_QUEUE_URL not configured, skipping notification queue")
        return False

    try:
        message = {
            "notification_type": notification_type,
            "athlete_id": athlete_id,
            "activity_id": activity_id,
            "metadata": metadata
        }

        sqs.send_message(
            QueueUrl=EMAIL_QUEUE_URL,
            MessageBody=json.dumps(message)
        )

        print(f"Queued {notification_type} notification for athlete {athlete_id}, activity {activity_id}")
        return True

    except Exception as e:
        print(f"ERROR: Failed to queue notification: {e}")
        import traceback
        traceback.print_exc()
        return False


def should_send_notifications(activity_id):
    """Check if notifications should be sent for this activity.

    Returns (should_send, activity_metadata) tuple.
    Only send notifications if:
    1. notifications_sent flag is false
    2. Activity was created within MAX_ACTIVITY_AGE_MINUTES (fresh webhook event)
    """
    sql = """
    SELECT notifications_sent, created_at, start_date_local, name
    FROM activities
    WHERE id = :activity_id
    """
    params = [{"name": "activity_id", "value": {"longValue": activity_id}}]

    try:
        result = _exec_sql(sql, params)
        records = result.get("records", [])

        if not records or not records[0]:
            print(f"Activity {activity_id} not found when checking notification eligibility")
            return False, None

        record = records[0]
        notifications_sent = record[0].get("booleanValue", False) if record[0] else False
        created_at_str = record[1].get("stringValue", "") if record[1] else ""
        start_date_local = record[2].get("stringValue", "") if record[2] else ""
        activity_name = record[3].get("stringValue", "Activity") if record[3] else "Activity"

        # Parse created_at timestamp
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            current_time = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.utcnow()
            activity_age_minutes = (current_time - created_at).total_seconds() / 60
        except (ValueError, AttributeError) as e:
            print(f"Failed to parse created_at timestamp: {e}")
            return False, None

        # Check if we should send notifications
        should_send = (
            not notifications_sent and
            activity_age_minutes <= MAX_ACTIVITY_AGE_MINUTES
        )

        if not should_send:
            print(f"Skipping notifications for activity {activity_id}: "
                  f"notifications_sent={notifications_sent}, age={activity_age_minutes:.1f}min")
            return False, None

        metadata = {
            "start_date_local": start_date_local,
            "activity_name": activity_name
        }

        return True, metadata

    except Exception as e:
        print(f"ERROR: Failed to check notification eligibility for activity {activity_id}: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def mark_notifications_sent(activity_id):
    """Mark activity as having notifications sent to prevent duplicates."""
    sql = """
    UPDATE activities
    SET notifications_sent = true, updated_at = now()
    WHERE id = :activity_id
    """
    params = [{"name": "activity_id", "value": {"longValue": activity_id}}]

    try:
        _exec_sql(sql, params)
        print(f"Marked activity {activity_id} as notifications_sent=true")
    except Exception as e:
        print(f"ERROR: Failed to mark notifications_sent for activity {activity_id}: {e}")


def send_notifications_if_eligible(activity_id, athlete_id, distance_on_trail, start_date_local,
                                   user_timezone=None, activity_timezone=None, ranking_changes=None):
    """Send email notifications if activity is eligible.

    Checks notifications_sent flag and activity age, then queues:
    1. Trail milestone notification (if distance >= user's threshold)
    2. Ranking change notifications (if rankings improved)
    """
    # Check if we should send notifications
    should_send, activity_metadata = should_send_notifications(activity_id)
    if not should_send:
        return

    activity_name = activity_metadata.get("activity_name", "Activity")
    notifications_queued = 0

    # Get user's notification preferences
    sql = """
    SELECT min_trail_distance_miles FROM users WHERE athlete_id = :athlete_id
    """
    params = [{"name": "athlete_id", "value": {"longValue": int(athlete_id)}}]

    try:
        result = _exec_sql(sql, params)
        records = result.get("records", [])
        min_trail_distance_miles = 3.0  # Default
        if records and records[0] and records[0][0]:
            min_trail_distance_miles = records[0][0].get("doubleValue", 3.0)
    except Exception as e:
        print(f"WARNING: Failed to get min_trail_distance_miles for athlete {athlete_id}, using default: {e}")
        min_trail_distance_miles = 3.0

    # Check trail milestone notification
    trail_distance_miles = distance_on_trail / 1609.34  # meters to miles
    if trail_distance_miles >= min_trail_distance_miles:
        trail_metadata = {
            "trail_distance_miles": round(trail_distance_miles, 1),
            "trail_name": "the trail",  # TODO: Could look up actual trail name
            "activity_name": activity_name,
            "activity_url": f"{FRONTEND_URL}/dashboard"
        }

        if queue_email_notification('trail_milestone', athlete_id, activity_id, trail_metadata):
            notifications_queued += 1

    # Check ranking change notifications
    if ranking_changes:
        for change in ranking_changes:
            ranking_metadata = {
                "old_rank": change.get("old_rank"),
                "new_rank": change.get("new_rank"),
                "window": change.get("window"),
                "activity_type": change.get("activity_type"),
                "activity_name": activity_name,
                "trail_distance_miles": round(trail_distance_miles, 1),
                "leaderboard_url": f"{FRONTEND_URL}/leaderboard"
            }

            if queue_email_notification('ranking_change', athlete_id, activity_id, ranking_metadata):
                notifications_queued += 1

    # Always mark as sent after eligibility check to prevent re-evaluation on retries
    # This flag means "we already checked this activity for notifications"
    mark_notifications_sent(activity_id)

    if notifications_queued > 0:
        print(f"Queued {notifications_queued} notification(s) for activity {activity_id}")
    else:
        print(f"No notifications queued for activity {activity_id} (below thresholds or no rank changes)")


def update_leaderboard_after_trail_matching(athlete_id, start_date_local,
                                             user_timezone=None, activity_timezone=None):
    """Recompute leaderboard_agg for the user's three windows from `activities`.

    Set-based and idempotent: concurrent matchers converge to the same totals,
    so we no longer leak +distance per racing webhook.
    """
    try:
        leaderboard_agg.recompute_for_activity(
            _exec_sql, athlete_id, start_date_local,
            user_timezone=user_timezone,
            activity_timezone=activity_timezone,
        )
    except Exception as e:
        # Don't fail the trail matching if leaderboard update fails — the next
        # match (or the admin recalc) will heal the row.
        print(f"ERROR: Failed to recompute leaderboard for athlete {athlete_id}: {e}")
        import traceback
        traceback.print_exc()


def match_activity(activity_id):
    """Match a single activity against trail data"""
    print(f"Matching activity {activity_id} against trail")

    # Initialize variables early to avoid NameError in exception handlers
    athlete_id = None
    start_date_local = ""
    user_timezone = None
    activity_timezone = None

    try:
        # Get activity from database
        activity = get_activity_from_db(activity_id)

        if not activity:
            raise ValueError(f"Activity {activity_id} not found in database")

        athlete_id = activity.get("athlete_id")
        if not athlete_id:
            raise ValueError(f"Activity {activity_id} has no athlete_id")

        start_date_local = activity.get("start_date_local", "")
        user_timezone = activity.get("user_timezone")
        activity_timezone = activity.get("activity_timezone")

        polyline = activity.get("polyline", "")
        if not polyline:
            print(f"Activity {activity_id} has no polyline data, skipping")
            # Still update last_matched to indicate we checked
            update_activity_trail_metrics(activity_id, 0.0, 0)
            # Recompute leaderboard from activities table (set-based, race-safe)
            if start_date_local:
                update_leaderboard_after_trail_matching(
                    athlete_id, start_date_local, user_timezone, activity_timezone
                )
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

            # Capture rankings BEFORE leaderboard recompute (for notification comparison)
            old_rankings = {}
            if start_date_local:
                old_rankings = get_current_rankings(
                    athlete_id, start_date_local, user_timezone, activity_timezone
                )

            # Recompute leaderboard from activities table (set-based, race-safe)
            if start_date_local:
                update_leaderboard_after_trail_matching(
                    athlete_id, start_date_local, user_timezone, activity_timezone
                )

                # Check for ranking changes and queue notifications if eligible
                ranking_changes = check_ranking_changes(
                    athlete_id, old_rankings, start_date_local, user_timezone, activity_timezone
                )

                # Send notifications if activity is eligible (fresh webhook event)
                send_notifications_if_eligible(
                    activity_id, athlete_id, distance_on_trail, start_date_local,
                    user_timezone, activity_timezone, ranking_changes
                )

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
            if athlete_id and start_date_local:
                update_leaderboard_after_trail_matching(
                    athlete_id, start_date_local, user_timezone, activity_timezone
                )
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
