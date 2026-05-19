"""
Shared leaderboard aggregation helpers for RabbitMiles.

The leaderboard_agg table is recomputed set-based from activities after each
match or activity delete. This avoids the read-modify-write race that the
incremental delta approach had (two concurrent matchers both reading
old_distance_on_trail=0 and double-counting).

Public surface:
- get_aggregate_types(activity_type)
- get_window_bounds(start_date_local, user_timezone, activity_timezone)
- is_opted_in(exec_sql, athlete_id)
- recompute_for_activity(exec_sql, athlete_id, start_date_local, user_timezone, activity_timezone)
"""

from datetime import datetime, timedelta

import timezone_utils


METRIC = "distance"

# Activity-type buckets the leaderboard aggregates against. We always recompute
# all three so that an activity whose type was edited (e.g. Run -> Ride on
# Strava) doesn't leave a stale value in the old bucket.
ALL_AGG_TYPES = ("all", "foot", "bike")

# Activity.type values that count toward each bucket. "all" has no filter.
TYPE_FILTER_SQL = {
    "all": "",
    "foot": "AND type IN ('Run', 'Walk')",
    "bike": "AND type = 'Ride'",
}


def get_aggregate_types(activity_type):
    """Return the leaderboard buckets a single activity contributes to.

    Kept for callers that still want the pre-recompute "this one activity
    affects buckets X" view. The recompute path uses ALL_AGG_TYPES instead.
    """
    types = ["all"]
    if activity_type in ("Run", "Walk"):
        types.append("foot")
    elif activity_type == "Ride":
        types.append("bike")
    return types


def get_window_bounds(start_date_local, user_timezone=None, activity_timezone=None):
    """Compute (window_key, start_dt, end_dt) for an activity's week/month/year.

    Returns dict keyed by 'week'/'month'/'year' with tuples of
    (window_key, start_datetime_naive, end_datetime_naive). The datetimes are
    naive timestamps in the user's local timezone, matching how
    activities.start_date_local is stored.

    Returns None on parse failure so the caller can decide to skip rather
    than crash the match.
    """
    try:
        dt_str = start_date_local.replace("Z", "+00:00") if isinstance(start_date_local, str) else None
        if dt_str is None:
            return None
        dt = datetime.fromisoformat(dt_str)
    except (ValueError, TypeError) as e:
        print(f"ERROR: Failed to parse activity date {start_date_local!r}: {e}")
        return None

    tz = timezone_utils.get_user_timezone(user_timezone, activity_timezone)
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz).replace(tzinfo=None)

    # Week: Monday 00:00 inclusive, next Monday 00:00 exclusive
    days_since_monday = dt.weekday()
    week_start = dt.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=7)
    week_key = f"week_{week_start.strftime('%Y-%m-%d')}"

    # Month: 1st 00:00 inclusive, next month's 1st 00:00 exclusive
    month_start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    month_key = f"month_{dt.strftime('%Y-%m')}"

    # Year: Jan 1 00:00 inclusive, next year's Jan 1 00:00 exclusive
    year_start = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    year_end = year_start.replace(year=year_start.year + 1)
    year_key = f"year_{dt.strftime('%Y')}"

    return {
        "week": (week_key, week_start, week_end),
        "month": (month_key, month_start, month_end),
        "year": (year_key, year_start, year_end),
    }


def is_opted_in(exec_sql, athlete_id):
    """Return True if the user has show_on_leaderboards = true."""
    sql = "SELECT show_on_leaderboards FROM users WHERE athlete_id = :aid"
    params = [{"name": "aid", "value": {"longValue": int(athlete_id)}}]
    try:
        result = exec_sql(sql, params)
    except Exception as e:
        print(f"ERROR: Failed to check leaderboard opt-in for {athlete_id}: {e}")
        return False

    records = result.get("records", [])
    if not records:
        return False
    field = records[0][0]
    if "booleanValue" in field:
        return bool(field["booleanValue"])
    if "stringValue" in field:
        return field["stringValue"].lower() in ("true", "t", "1")
    return False


def _recompute_one(exec_sql, athlete_id, window_name, window_key, start_dt, end_dt, agg_type):
    """Issue one INSERT…SELECT SUM…ON CONFLICT DO UPDATE for a single bucket."""
    type_filter = TYPE_FILTER_SQL[agg_type]
    sql = f"""
    INSERT INTO leaderboard_agg ("window", window_key, metric, activity_type, athlete_id, value, last_updated)
    SELECT :window, :window_key, :metric, :act_type, :aid,
           COALESCE(SUM(distance_on_trail), 0), now()
      FROM activities
     WHERE athlete_id = :aid
       AND start_date_local >= CAST(:start_dt AS TIMESTAMP)
       AND start_date_local <  CAST(:end_dt AS TIMESTAMP)
       AND distance_on_trail IS NOT NULL
       {type_filter}
    ON CONFLICT (window_key, metric, activity_type, athlete_id)
    DO UPDATE SET value = EXCLUDED.value, last_updated = now()
    """
    params = [
        {"name": "window", "value": {"stringValue": window_name}},
        {"name": "window_key", "value": {"stringValue": window_key}},
        {"name": "metric", "value": {"stringValue": METRIC}},
        {"name": "act_type", "value": {"stringValue": agg_type}},
        {"name": "aid", "value": {"longValue": int(athlete_id)}},
        {"name": "start_dt", "value": {"stringValue": start_dt.isoformat()}},
        {"name": "end_dt", "value": {"stringValue": end_dt.isoformat()}},
    ]
    exec_sql(sql, params)


def recompute_for_activity(exec_sql, athlete_id, start_date_local,
                           user_timezone=None, activity_timezone=None):
    """Recompute leaderboard_agg for the user's three windows × three buckets.

    The current value of every bucket is overwritten with COALESCE(SUM, 0)
    from activities — no incremental math, so concurrent invocations converge
    to the same result.

    No-op if the user is opted out. Returns True on success, False on
    irrecoverable failure (per-bucket failures are logged but don't abort
    the rest of the recompute).
    """
    if not is_opted_in(exec_sql, athlete_id):
        return True

    bounds = get_window_bounds(start_date_local, user_timezone, activity_timezone)
    if not bounds:
        print(f"ERROR: Could not compute window bounds for athlete {athlete_id} date {start_date_local!r}")
        return False

    ok = True
    for window_name, (window_key, start_dt, end_dt) in bounds.items():
        for agg_type in ALL_AGG_TYPES:
            try:
                _recompute_one(exec_sql, athlete_id, window_name, window_key, start_dt, end_dt, agg_type)
            except Exception as e:
                ok = False
                print(
                    f"ERROR: Failed to recompute leaderboard_agg for athlete={athlete_id} "
                    f"window={window_key} type={agg_type}: {e}"
                )
    return ok
