#!/usr/bin/env python3
"""
stats_period_summary Lambda function

Returns period statistics with projections for distance on trail:
- week (Monday-Sunday)
- month (calendar month)
- year (calendar year)

Each period includes:
- current: actual distance so far
- previous: distance from previous period (null if no data)
- projected: linear extrapolation based on current pace
- trend: "up" or "down" (null if no previous or equal)
- remaining_to_beat: miles needed to beat previous (null if no previous)

Projection formula: projected = (current / elapsed_days) * total_days
Where elapsed_days includes current day and is at least 1.
"""

import os
import json
import base64
import hmac
import hashlib
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse
import boto3

# Add parent directory to path to import admin_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

rds = boto3.client("rds-data")

# Environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

# Conversion constant
METERS_TO_MILES = 1609.34


def get_cors_origin():
    """Extract origin (scheme + host) from FRONTEND_URL for CORS headers"""
    if not FRONTEND_URL:
        return None
    parsed = urlparse(FRONTEND_URL)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def get_cors_headers():
    """Return CORS headers for cross-origin requests"""
    headers = {"Content-Type": "application/json"}
    origin = get_cors_origin()
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers


def verify_session_token(tok):
    """Verify and extract athlete_id from session token"""
    try:
        b, sig = tok.rsplit(".", 1)
        expected = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode())
        if data.get("exp", 0) < __import__("time").time():
            return None
        return int(data.get("aid"))
    except Exception:
        return None


def parse_session_cookie(event):
    """Parse session cookie from event"""
    headers = event.get("headers") or {}
    cookies_array = event.get("cookies") or []
    cookie_header = headers.get("cookie") or headers.get("Cookie")

    # Check cookies array first
    for cookie_str in cookies_array:
        if not cookie_str or "=" not in cookie_str:
            continue
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v

    # Check cookie header
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == "rm_session":
                return v
    return None


def exec_sql(sql, parameters=None):
    """Execute SQL query using RDS Data API"""
    kwargs = dict(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        sql=sql,
        database=DB_NAME
    )
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def get_period_boundaries(now):
    """
    Calculate period boundaries for week, month, and year.
    
    Uses local date boundaries matching Dashboard.jsx logic:
    - Week: Monday 00:00:00 to Sunday 23:59:59
    - Month: First day 00:00:00 to last day 23:59:59
    - Year: January 1 00:00:00 to December 31 23:59:59
    
    Returns dict with period keys containing start, end, prev_start, prev_end, elapsed_days, total_days
    """
    periods = {}
    
    # WEEK: Monday to Sunday
    # For Monday-based week: if Sunday (0), go back 6 days; otherwise go back (day - 1) days
    day_of_week = now.weekday()  # Monday=0, Sunday=6
    days_since_monday = day_of_week
    start_of_week = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    # Previous week
    prev_week_end = start_of_week - timedelta(seconds=1)
    prev_week_start = (prev_week_end - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate elapsed days (including today)
    elapsed_days_week = (now - start_of_week).days + 1
    elapsed_days_week = max(1, elapsed_days_week)  # Minimum 1
    
    periods["week"] = {
        "start": start_of_week,
        "end": end_of_week,
        "prev_start": prev_week_start,
        "prev_end": prev_week_end,
        "elapsed_days": elapsed_days_week,
        "total_days": 7
    }
    
    # MONTH: Calendar month
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Last day of month: go to first day of next month, then subtract 1 second
    if now.month == 12:
        start_of_next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_of_next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_month = start_of_next_month - timedelta(seconds=1)
    
    # Previous month
    prev_month_end = start_of_month - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate elapsed days (including today)
    elapsed_days_month = now.day
    elapsed_days_month = max(1, elapsed_days_month)  # Minimum 1
    
    # Total days in current month
    total_days_month = (end_of_month - start_of_month).days + 1
    
    periods["month"] = {
        "start": start_of_month,
        "end": end_of_month,
        "prev_start": prev_month_start,
        "prev_end": prev_month_end,
        "elapsed_days": elapsed_days_month,
        "total_days": total_days_month
    }
    
    # YEAR: Calendar year
    start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_year = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
    
    # Previous year
    prev_year_start = start_of_year.replace(year=now.year - 1)
    prev_year_end = end_of_year.replace(year=now.year - 1)
    
    # Calculate elapsed days (including today)
    elapsed_days_year = (now - start_of_year).days + 1
    elapsed_days_year = max(1, elapsed_days_year)  # Minimum 1
    
    # Total days in current year (account for leap years)
    total_days_year = (end_of_year - start_of_year).days + 1
    
    periods["year"] = {
        "start": start_of_year,
        "end": end_of_year,
        "prev_start": prev_year_start,
        "prev_end": prev_year_end,
        "elapsed_days": elapsed_days_year,
        "total_days": total_days_year
    }
    
    return periods


def aggregate_distance(athlete_id, start_date, end_date):
    """
    Aggregate distance_on_trail for the given period.
    
    Uses start_date_local field to match Dashboard.jsx behavior.
    Returns distance in meters.
    """
    # Format dates as ISO strings for SQL comparison
    start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
    
    sql = """
        SELECT COALESCE(SUM(distance_on_trail), 0) as total_distance
        FROM activities
        WHERE athlete_id = :athlete_id
          AND start_date_local >= :start_date::timestamp
          AND start_date_local <= :end_date::timestamp
          AND distance_on_trail IS NOT NULL
    """
    
    parameters = [
        {"name": "athlete_id", "value": {"longValue": athlete_id}},
        {"name": "start_date", "value": {"stringValue": start_str}},
        {"name": "end_date", "value": {"stringValue": end_str}}
    ]
    
    result = exec_sql(sql, parameters)
    records = result.get("records", [])
    
    if not records or not records[0]:
        return 0.0
    
    # Extract distance value (could be longValue or doubleValue)
    distance_field = records[0][0]
    distance = distance_field.get("doubleValue") or distance_field.get("longValue", 0)
    
    return float(distance)


def calculate_projection(current_distance, elapsed_days, total_days):
    """
    Calculate linear projection.
    
    projected = (current / elapsed_days) * total_days
    
    Guards against division by zero and returns 0 if calculation fails.
    """
    if elapsed_days <= 0 or total_days <= 0:
        return 0.0
    
    try:
        projected = (current_distance / elapsed_days) * total_days
        # Guard against NaN and Infinity
        import math
        if math.isnan(projected) or math.isinf(projected):
            return 0.0
        return projected
    except Exception:
        return 0.0


def calculate_trend(projected, previous):
    """
    Calculate trend direction.
    
    Returns:
    - "up" if projected > previous
    - "down" if projected < previous
    - None if previous is None or projected == previous
    """
    if previous is None:
        return None
    
    if projected > previous:
        return "up"
    elif projected < previous:
        return "down"
    else:
        return None


def calculate_remaining_to_beat(current, previous):
    """
    Calculate miles needed to beat previous period.
    
    Returns:
    - None if previous is None
    - max(previous - current, 0) otherwise
    """
    if previous is None:
        return None
    
    remaining = max(previous - current, 0)
    return remaining


def handler(event, context):
    """Lambda handler for GET /stats/period_summary"""
    print("=" * 80)
    print("/STATS/PERIOD_SUMMARY LAMBDA - START")
    print("=" * 80)
    
    cors_headers = get_cors_headers()
    
    # Handle OPTIONS preflight
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        print("OPTIONS preflight request")
        return {
            "statusCode": 200,
            "headers": {
                **cors_headers,
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Cookie",
                "Access-Control-Max-Age": "86400"
            },
            "body": ""
        }
    
    try:
        # Validate environment variables
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN or not APP_SECRET:
            print("ERROR: Missing required environment variables")
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        # Authenticate
        tok = parse_session_cookie(event)
        if not tok:
            print("ERROR: No session cookie found")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        athlete_id = verify_session_token(tok)
        if not athlete_id:
            print("ERROR: Invalid session token")
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "invalid session"})
            }
        
        print(f"Authenticated as athlete_id: {athlete_id}")
        
        # Get current time (using UTC)
        # Note: Using datetime.now(timezone.utc) for Python 3.12+ compatibility
        # Calculations use start_date_local from DB which stores local time
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)  # Remove timezone for consistency with existing logic
        print(f"Current UTC time: {now.isoformat()}")
        
        # Calculate period boundaries
        periods = get_period_boundaries(now)
        
        # Build response
        response_data = {}
        
        for period_name, period_info in periods.items():
            print(f"\nProcessing {period_name}:")
            print(f"  Current period: {period_info['start']} to {period_info['end']}")
            print(f"  Previous period: {period_info['prev_start']} to {period_info['prev_end']}")
            print(f"  Elapsed days: {period_info['elapsed_days']}, Total days: {period_info['total_days']}")
            
            # Query current period
            current_distance_meters = aggregate_distance(
                athlete_id,
                period_info['start'],
                period_info['end']
            )
            current_distance_miles = current_distance_meters / METERS_TO_MILES
            
            print(f"  Current distance: {current_distance_miles:.2f} miles")
            
            # Query previous period
            previous_distance_meters = aggregate_distance(
                athlete_id,
                period_info['prev_start'],
                period_info['prev_end']
            )
            previous_distance_miles = previous_distance_meters / METERS_TO_MILES if previous_distance_meters > 0 else None
            
            if previous_distance_miles is None:
                print(f"  Previous period: no data")
            else:
                print(f"  Previous distance: {previous_distance_miles:.2f} miles")
            
            # Calculate projection
            projected_miles = calculate_projection(
                current_distance_miles,
                period_info['elapsed_days'],
                period_info['total_days']
            )
            print(f"  Projected distance: {projected_miles:.2f} miles")
            
            # Calculate trend
            trend = calculate_trend(projected_miles, previous_distance_miles)
            print(f"  Trend: {trend}")
            
            # Calculate remaining to beat
            remaining = calculate_remaining_to_beat(current_distance_miles, previous_distance_miles)
            if remaining is not None:
                print(f"  Remaining to beat: {remaining:.2f} miles")
            else:
                print(f"  Remaining to beat: N/A (no previous data)")
            
            response_data[period_name] = {
                "current": round(current_distance_miles, 2),
                "previous": round(previous_distance_miles, 2) if previous_distance_miles is not None else None,
                "projected": round(projected_miles, 2),
                "trend": trend,
                "remaining_to_beat": round(remaining, 2) if remaining is not None else None
            }
        
        print(f"\nResponse data: {json.dumps(response_data, indent=2)}")
        print("=" * 80)
        print("/STATS/PERIOD_SUMMARY LAMBDA - SUCCESS")
        print("=" * 80)
        
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(response_data)
        }
        
    except Exception as e:
        print(f"ERROR: Unexpected exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("/STATS/PERIOD_SUMMARY LAMBDA - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal server error"})
        }
