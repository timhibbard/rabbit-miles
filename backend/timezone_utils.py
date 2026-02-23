"""
Timezone utilities for RabbitMiles

Provides consistent timezone handling across all Lambda functions.
Falls back to US Eastern timezone when user timezone is not available.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Default timezone: US Eastern
DEFAULT_TIMEZONE = "America/New_York"


def parse_strava_timezone(strava_tz_string):
    """
    Parse Strava timezone string to extract IANA timezone identifier.
    
    Strava timezone format is typically:
    - "(GMT-08:00) America/Los_Angeles"
    - "America/Los_Angeles"
    
    Args:
        strava_tz_string: Timezone string from Strava API
        
    Returns:
        IANA timezone identifier (e.g., "America/Los_Angeles") or None if parsing fails
    """
    if not strava_tz_string:
        return None
    
    try:
        # If there's a space, extract the part after it (IANA identifier)
        if " " in strava_tz_string:
            tz_name = strava_tz_string.split(" ", 1)[1]
        else:
            tz_name = strava_tz_string
        
        # Validate the timezone exists
        ZoneInfo(tz_name)
        return tz_name
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        # ZoneInfoNotFoundError: timezone not found in IANA database
        # KeyError: invalid timezone string format
        # ValueError: invalid timezone string
        return None


def get_user_timezone(user_timezone=None, activity_timezone=None):
    """
    Get user timezone with proper fallback logic.
    
    Precedence:
    1. User's stored timezone preference (from users.timezone)
    2. User's most recent activity timezone (from activities.timezone)
    3. Default to US Eastern timezone
    
    Args:
        user_timezone: User's stored timezone preference (from users table)
        activity_timezone: Most recent activity timezone (from activities table)
        
    Returns:
        ZoneInfo object for the appropriate timezone
    """
    # Try user's stored timezone preference first
    if user_timezone:
        tz_name = parse_strava_timezone(user_timezone)
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except (ZoneInfoNotFoundError, KeyError):
                # Timezone not found or invalid, continue to fallback
                pass
    
    # Try activity timezone
    if activity_timezone:
        tz_name = parse_strava_timezone(activity_timezone)
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except (ZoneInfoNotFoundError, KeyError):
                # Timezone not found or invalid, continue to fallback
                pass
    
    # Fall back to US Eastern
    return ZoneInfo(DEFAULT_TIMEZONE)


def get_timezone_name(user_timezone=None, activity_timezone=None):
    """
    Get the IANA timezone name as a string.
    
    Uses the same fallback logic as get_user_timezone.
    
    Args:
        user_timezone: User's stored timezone preference
        activity_timezone: Most recent activity timezone
        
    Returns:
        IANA timezone identifier string (e.g., "America/New_York")
    """
    tz = get_user_timezone(user_timezone, activity_timezone)
    return str(tz)
