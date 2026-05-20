# webhook_processor Lambda function (SQS triggered)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)
# MATCH_ACTIVITY_LAMBDA_ARN (optional, for trail matching)
#
# This Lambda is triggered by SQS messages from the webhook handler.
# It processes Strava webhook events asynchronously:
# - Fetches activity details from Strava API
# - Updates the activities table in the database
# - Updates leaderboard aggregations
# - Handles token refresh if needed
# - Implements idempotency to avoid duplicate processing

import os
import sys
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import boto3

# Add parent directory to path to import shared modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import leaderboard_agg

rds = boto3.client("rds-data")
sm = boto3.client("secretsmanager")
lambda_client = boto3.client("lambda")
sqs = boto3.client("sqs")

# Default visibility-timeout extension when Strava returns 429 with no Retry-After.
# 15 minutes is one full Strava rate-limit window.
DEFAULT_RATE_LIMIT_DEFER_SECONDS = 15 * 60
MIN_RATE_LIMIT_DEFER_SECONDS = 60
# SQS caps per-message visibility-timeout extensions at 12 hours.
MAX_VISIBILITY_TIMEOUT_SECONDS = 12 * 60 * 60
# Strava rate limit state (read endpoints) observed via response headers.
_rate_limit_used = 0
_rate_limit_limit = 100  # Strava default read limit per 15-minute window.
_rate_limit_last_updated_epoch = 0
RATE_LIMIT_SAFETY_MARGIN = 5
RATE_LIMIT_WINDOW_SECONDS = 15 * 60
RATE_LIMIT_RESET_BUFFER_SECONDS = 5
RATE_LIMIT_STATE_TTL_SECONDS = 30 * 60
# In-memory cooldown expiry timestamp (epoch seconds) for warm Lambda containers
# to avoid repeated Strava 429 calls. Assumes Lambda's single-invocation-per-
# execution-environment model.
_strava_cooldown_expires_epoch = 0

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
MATCH_ACTIVITY_LAMBDA_ARN = os.environ.get("MATCH_ACTIVITY_LAMBDA_ARN", "")

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITY_URL = "https://www.strava.com/api/v3/activities"

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300


class StravaRateLimitError(Exception):
    """Raised when Strava returns 429 and we want SQS to retry the message later."""
    def __init__(self, retry_after_seconds=None):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Strava rate limit hit (retry_after={retry_after_seconds}s)")


def _get_strava_creds():
    """Get Strava client credentials from env or Secrets Manager"""
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    secret_arn = os.environ.get("STRAVA_SECRET_ARN")

    if (not client_id or not client_secret) and secret_arn:
        resp = sm.get_secret_value(SecretId=secret_arn)
        data = json.loads(resp["SecretString"])
        client_id = client_id or str(data.get("client_id") or data.get("clientId"))
        client_secret = client_secret or str(data.get("client_secret") or data.get("clientSecret"))

    if not client_id or not client_secret:
        raise RuntimeError("Missing STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET")

    return client_id, client_secret


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


def refresh_access_token(athlete_id, refresh_token):
    """Refresh expired Strava access token"""
    client_id, client_secret = _get_strava_creds()
    
    body = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    
    req = Request(STRAVA_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    
    try:
        with urlopen(req, timeout=20) as resp:
            token_resp = json.loads(resp.read().decode())
        
        access_token = token_resp.get("access_token")
        new_refresh_token = token_resp.get("refresh_token")
        expires_at = int(token_resp.get("expires_at") or 0)
        
        if not access_token:
            raise RuntimeError(f"Token refresh failed: {token_resp}")
        
        # Update tokens in database
        sql = """
        UPDATE users 
        SET access_token = :at, refresh_token = :rt, expires_at = :exp, updated_at = now()
        WHERE athlete_id = :aid
        """
        params = [
            {"name": "at", "value": {"stringValue": access_token}},
            {"name": "rt", "value": {"stringValue": new_refresh_token}},
            {"name": "exp", "value": {"longValue": expires_at}},
            {"name": "aid", "value": {"longValue": athlete_id}},
        ]
        _exec_sql(sql, params)
        
        print(f"Refreshed access token for athlete {athlete_id}")
        return access_token
    except Exception as e:
        print(f"Failed to refresh token for athlete {athlete_id}: {e}")
        raise


def get_user_tokens(athlete_id):
    """Get user's tokens from database"""
    sql = "SELECT access_token, refresh_token, expires_at FROM users WHERE athlete_id = :aid"
    params = [{"name": "aid", "value": {"longValue": athlete_id}}]
    result = _exec_sql(sql, params)
    
    records = result.get("records", [])
    if not records:
        print(f"User {athlete_id} not found in database")
        return None, None, 0
    
    record = records[0]
    access_token = record[0].get("stringValue", "")
    refresh_token = record[1].get("stringValue", "")
    expires_at = int(record[2].get("longValue", 0))
    
    return access_token, refresh_token, expires_at


def _parse_retry_after(retry_after_header):
    """Parse Retry-After header value (seconds-only) into an int. Returns None on failure."""
    if not retry_after_header:
        return None
    try:
        return max(0, int(retry_after_header))
    except (TypeError, ValueError):
        return None


def _parse_rate_limit_pair(header_value):
    """Parse Strava rate-limit header values ('short,daily') into ints."""
    if not header_value:
        return None, None
    try:
        parts = [int(part.strip()) for part in str(header_value).split(",") if part.strip()]
    except (TypeError, ValueError):
        return None, None
    if not parts:
        return None, None
    short_term = parts[0]
    daily = parts[1] if len(parts) > 1 else None
    return short_term, daily


def _get_header_value(headers, header_names):
    """Return the first matching header value from a list of candidate names."""
    for name in header_names:
        value = headers.get(name)
        if value is not None:
            return value
    return None


def _update_rate_limit_from_headers(headers):
    """Parse and store Strava read rate-limit headers from a response."""
    global _rate_limit_used, _rate_limit_limit, _rate_limit_last_updated_epoch
    usage_header = _get_header_value(
        headers,
        [
            "X-ReadRateLimit-Usage",
            "x-readratelimit-usage",
            "X-RateLimit-Usage",
            "x-ratelimit-usage",
        ],
    )
    limit_header = _get_header_value(
        headers,
        [
            "X-ReadRateLimit-Limit",
            "x-readratelimit-limit",
            "X-RateLimit-Limit",
            "x-ratelimit-limit",
        ],
    )
    used_short, _ = _parse_rate_limit_pair(usage_header)
    limit_short, _ = _parse_rate_limit_pair(limit_header)
    updated = False
    if used_short is not None:
        _rate_limit_used = used_short
        updated = True
    if limit_short is not None:
        _rate_limit_limit = limit_short
        updated = True
    if updated:
        _rate_limit_last_updated_epoch = int(time.time())


def _capture_rate_limit_headers(headers):
    """Safely capture rate limit headers if present."""
    if not headers:
        return
    try:
        header_map = headers if isinstance(headers, dict) else dict(headers)
        _update_rate_limit_from_headers(header_map)
    except Exception:
        pass


def _seconds_until_rate_limit_reset():
    """Seconds until the next 15-minute Strava rate limit window resets.

    Strava documents fixed reset boundaries at :00, :15, :30, :45 UTC. Unix
    epoch time is in UTC, so modulo arithmetic aligns to those boundaries.
    """
    now = time.time()
    seconds_into_window = now % RATE_LIMIT_WINDOW_SECONDS
    return RATE_LIMIT_WINDOW_SECONDS - seconds_into_window + RATE_LIMIT_RESET_BUFFER_SECONDS


def _maybe_start_rate_limit_cooldown():
    """Start cooldown if we're at/near the Strava read rate limit."""
    if not _rate_limit_last_updated_epoch:
        return None
    if time.time() - _rate_limit_last_updated_epoch > RATE_LIMIT_STATE_TTL_SECONDS:
        return None
    if _rate_limit_used >= _rate_limit_limit - RATE_LIMIT_SAFETY_MARGIN:
        wait_seconds = _seconds_until_rate_limit_reset()
        cooldown_seconds = _set_rate_limit_cooldown(wait_seconds)
        print(f"Strava rate limit nearing ({_rate_limit_used}/{_rate_limit_limit}); enabling cooldown for {cooldown_seconds}s")
        return cooldown_seconds
    return None


def fetch_activity_details(access_token, activity_id):
    """Fetch detailed activity data from Strava API.

    On HTTP 429 we surface a StravaRateLimitError so the caller can defer the
    SQS message instead of letting it cycle through retries and land in the DLQ.
    """
    url = f"{STRAVA_ACTIVITY_URL}/{activity_id}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})

    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            _capture_rate_limit_headers(resp.headers)
            _maybe_start_rate_limit_cooldown()
            activity = json.loads(body)
        print(f"Fetched activity {activity_id} from Strava API")
        return activity
    except HTTPError as e:
        print(f"Failed to fetch activity {activity_id} from Strava: HTTP {e.code}")
        try:
            error_body = e.read().decode()
            print(f"Error response body: {error_body}")
        except Exception:
            pass
        _capture_rate_limit_headers(e.headers)
        if e.code == 429:
            retry_after = _parse_retry_after(e.headers.get("Retry-After") if e.headers else None)
            raise StravaRateLimitError(retry_after_seconds=retry_after) from e
        raise
    except Exception as e:
        print(f"Failed to fetch activity {activity_id} from Strava: {e}")
        raise


def store_activity(athlete_id, activity):
    """Store or update activity in database, returns activity_id if successful"""
    strava_activity_id = activity.get("id")
    if not strava_activity_id:
        print(f"ERROR: Activity missing id: {activity}")
        return None
    
    # Extract activity data
    name = activity.get("name", "")
    distance = activity.get("distance", 0)  # meters
    moving_time = activity.get("moving_time", 0)  # seconds
    elapsed_time = activity.get("elapsed_time", 0)  # seconds
    total_elevation_gain = activity.get("total_elevation_gain", 0)
    activity_type = activity.get("type", "")
    start_date = activity.get("start_date", "")
    start_date_local = activity.get("start_date_local", "")
    timezone = activity.get("timezone", "")
    
    # Get polyline from map - prefer full polyline over summary_polyline
    polyline = ""
    if activity.get("map"):
        # Try full polyline first, fallback to summary_polyline
        polyline = activity["map"].get("polyline") or activity["map"].get("summary_polyline", "")
    
    # Insert or update activity and return the activity ID
    sql = """
    INSERT INTO activities (
        athlete_id, strava_activity_id, name, distance, moving_time, elapsed_time,
        total_elevation_gain, type, start_date, start_date_local, timezone, polyline, updated_at
    )
    VALUES (:aid, :sid, :name, :dist, :mt, :et, :elev, :type, CAST(:sd AS TIMESTAMP), CAST(:sdl AS TIMESTAMP), :tz, :poly, now())
    ON CONFLICT (athlete_id, strava_activity_id) 
    DO UPDATE SET
        name = EXCLUDED.name,
        distance = EXCLUDED.distance,
        moving_time = EXCLUDED.moving_time,
        elapsed_time = EXCLUDED.elapsed_time,
        total_elevation_gain = EXCLUDED.total_elevation_gain,
        type = EXCLUDED.type,
        start_date = EXCLUDED.start_date,
        start_date_local = EXCLUDED.start_date_local,
        timezone = EXCLUDED.timezone,
        polyline = EXCLUDED.polyline,
        updated_at = now()
    RETURNING id
    """
    
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "sid", "value": {"longValue": strava_activity_id}},
        {"name": "name", "value": {"stringValue": name}},
        {"name": "dist", "value": {"doubleValue": float(distance)}},
        {"name": "mt", "value": {"longValue": moving_time}},
        {"name": "et", "value": {"longValue": elapsed_time}},
        {"name": "elev", "value": {"doubleValue": float(total_elevation_gain)}},
        {"name": "type", "value": {"stringValue": activity_type}},
        {"name": "sd", "value": {"stringValue": start_date} if start_date else {"isNull": True}},
        {"name": "sdl", "value": {"stringValue": start_date_local} if start_date_local else {"isNull": True}},
        {"name": "tz", "value": {"stringValue": timezone}},
        {"name": "poly", "value": {"stringValue": polyline} if polyline else {"isNull": True}},
    ]
    
    try:
        result = _exec_sql(sql, params)
        # Get the returned activity ID
        records = result.get("records", [])
        if records:
            activity_id = int(records[0][0].get("longValue", 0))
            print(f"Successfully stored activity {strava_activity_id}: {name} (id={activity_id})")
            return activity_id
        else:
            print(f"WARNING: Activity stored but no ID returned for {strava_activity_id}")
            return None
    except Exception as e:
        print(f"ERROR: Failed to store activity {strava_activity_id}: {e}")
        return None


def delete_activity(athlete_id, strava_activity_id):
    """Delete activity from database"""
    sql = "DELETE FROM activities WHERE athlete_id = :aid AND strava_activity_id = :sid"
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "sid", "value": {"longValue": strava_activity_id}},
    ]
    
    try:
        _exec_sql(sql, params)
        print(f"Successfully deleted activity {strava_activity_id} for athlete {athlete_id}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to delete activity {strava_activity_id}: {e}")
        return False


def trigger_trail_matching(activity_id):
    """Trigger trail matching Lambda for an activity"""
    if not MATCH_ACTIVITY_LAMBDA_ARN:
        print("WARNING: MATCH_ACTIVITY_LAMBDA_ARN not configured, skipping trail matching")
        return False
    
    try:
        payload = json.dumps({"activity_id": activity_id})
        response = lambda_client.invoke(
            FunctionName=MATCH_ACTIVITY_LAMBDA_ARN,
            InvocationType='Event',  # Async invocation
            Payload=payload
        )
        print(f"Triggered trail matching for activity {activity_id}: status {response['StatusCode']}")
        return True
    except Exception as e:
        print(f"WARNING: Failed to trigger trail matching for activity {activity_id}: {e}")
        # Don't fail the webhook processing if trail matching fails
        return False


def get_activity_window_metadata(athlete_id, strava_activity_id):
    """Fetch the metadata needed to recompute leaderboard windows for an activity.

    Returns a dict {start_date_local, activity_timezone, user_timezone} or None
    if the activity isn't in the DB yet. Must be called BEFORE delete_activity
    on the delete path so we still know which windows to recompute.
    """
    sql = """
    SELECT a.start_date_local, a.timezone AS activity_timezone, u.timezone AS user_timezone
      FROM activities a
      LEFT JOIN users u ON u.athlete_id = a.athlete_id
     WHERE a.athlete_id = :aid AND a.strava_activity_id = :sid
    """
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "sid", "value": {"longValue": strava_activity_id}},
    ]
    try:
        result = _exec_sql(sql, params)
    except Exception as e:
        print(f"ERROR: Failed to read activity metadata for {strava_activity_id}: {e}")
        return None

    records = result.get("records", [])
    if not records:
        return None
    record = records[0]
    return {
        "start_date_local": record[0].get("stringValue", "") if not record[0].get("isNull") else "",
        "activity_timezone": record[1].get("stringValue") if not record[1].get("isNull") else None,
        "user_timezone": record[2].get("stringValue") if not record[2].get("isNull") else None,
    }


def recompute_leaderboard_for_activity_window(athlete_id, metadata):
    """Recompute leaderboard_agg for the user's windows that contain this activity.

    Set-based: derives the user's totals from the current `activities` rows. Run
    this after a create/update/delete to keep the leaderboard consistent without
    incremental delta math.
    """
    if not metadata or not metadata.get("start_date_local"):
        return True

    start_time = time.time()
    print(f"TELEMETRY - leaderboard_agg_recompute_start athlete_id={athlete_id}")
    try:
        leaderboard_agg.recompute_for_activity(
            _exec_sql,
            athlete_id,
            metadata["start_date_local"],
            user_timezone=metadata.get("user_timezone"),
            activity_timezone=metadata.get("activity_timezone"),
        )
        duration_ms = (time.time() - start_time) * 1000
        print(f"TELEMETRY - leaderboard_agg_recompute_complete athlete_id={athlete_id} duration_ms={duration_ms:.2f}")
        return True
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"TELEMETRY - leaderboard_agg_recompute_error athlete_id={athlete_id} error={e} duration_ms={duration_ms:.2f}")
        import traceback
        traceback.print_exc()
        return False


def check_idempotency(idempotency_key):
    """Check if event has already been processed"""
    sql = "SELECT processed_at FROM webhook_events WHERE idempotency_key = :key"
    params = [{"name": "key", "value": {"stringValue": idempotency_key}}]
    
    try:
        result = _exec_sql(sql, params)
        return len(result.get("records", [])) > 0
    except Exception as e:
        # If table doesn't exist yet, event hasn't been processed
        print(f"Idempotency check failed (table may not exist): {e}")
        return False


def mark_event_processed(idempotency_key, webhook_event):
    """Mark event as processed in database"""
    sql = """
    INSERT INTO webhook_events (
        idempotency_key, subscription_id, object_type, object_id, 
        aspect_type, owner_id, event_time, processed_at
    )
    VALUES (:key, :sub_id, :obj_type, :obj_id, :aspect, :owner, :evt_time, now())
    ON CONFLICT (idempotency_key) DO NOTHING
    """
    
    params = [
        {"name": "key", "value": {"stringValue": idempotency_key}},
        {"name": "sub_id", "value": {"longValue": int(webhook_event.get("subscription_id", 0))}},
        {"name": "obj_type", "value": {"stringValue": webhook_event.get("object_type", "")}},
        {"name": "obj_id", "value": {"longValue": int(webhook_event.get("object_id", 0))}},
        {"name": "aspect", "value": {"stringValue": webhook_event.get("aspect_type", "")}},
        {"name": "owner", "value": {"longValue": int(webhook_event.get("owner_id", 0))}},
        {"name": "evt_time", "value": {"longValue": int(webhook_event.get("event_time", 0))}},
    ]
    
    try:
        _exec_sql(sql, params)
        print(f"Marked event as processed: {idempotency_key}")
    except Exception as e:
        # If table doesn't exist, that's okay - we'll create it later
        print(f"WARNING: Failed to mark event as processed (table may not exist): {e}")


def update_last_webhook_received(athlete_id):
    """Record that we just successfully processed a webhook event for this athlete.

    Used by the hourly scheduled_activity_update job to skip users whose data
    is already being kept fresh by webhooks.
    """
    sql = "UPDATE users SET last_webhook_received_at = now() WHERE athlete_id = :aid"
    params = [{"name": "aid", "value": {"longValue": athlete_id}}]
    try:
        _exec_sql(sql, params)
    except Exception as e:
        # Non-fatal: column may not exist yet (pre-migration). Do not fail the event.
        print(f"WARNING: Failed to update last_webhook_received_at for {athlete_id}: {e}")


def process_webhook_event(webhook_event):
    """Process a single webhook event.

    Returns True on success, False on retryable failure. Raises
    StravaRateLimitError when we want the caller to defer the SQS message
    rather than rely on normal retry/DLQ behavior.
    """
    object_type = webhook_event.get("object_type")
    aspect_type = webhook_event.get("aspect_type")
    object_id = int(webhook_event.get("object_id", 0))
    owner_id = int(webhook_event.get("owner_id", 0))
    subscription_id = webhook_event.get("subscription_id")
    event_time = webhook_event.get("event_time")

    print(f"Processing webhook event: {object_type} {aspect_type} {object_id} for athlete {owner_id}")

    # Create idempotency key
    idempotency_key = f"{subscription_id}:{object_id}:{aspect_type}:{event_time}"

    # Check if already processed
    if check_idempotency(idempotency_key):
        print(f"Event already processed: {idempotency_key}")
        return True

    # Get user tokens
    access_token, refresh_token, expires_at = get_user_tokens(owner_id)

    if not access_token or not refresh_token:
        print(f"User {owner_id} not found or not connected to Strava")
        # Mark as processed to avoid retrying
        mark_event_processed(idempotency_key, webhook_event)
        return True

    # Check if token needs refresh
    current_time = int(time.time())
    if expires_at < current_time + TOKEN_REFRESH_BUFFER_SECONDS:
        print(f"Access token expired or expiring soon for athlete {owner_id}, refreshing...")
        try:
            access_token = refresh_access_token(owner_id, refresh_token)
        except Exception as e:
            print(f"ERROR: Token refresh failed: {e}")
            # Don't mark as processed, allow retry
            return False

    # Handle different event types
    success = False
    activity_id = None

    if aspect_type == "delete":
        # Capture the activity's window metadata BEFORE the row is gone, then
        # delete, then recompute the user's leaderboard windows from the
        # remaining activities (set-based, race-safe).
        metadata = get_activity_window_metadata(owner_id, object_id)
        success = delete_activity(owner_id, object_id)
        if success and metadata:
            recompute_leaderboard_for_activity_window(owner_id, metadata)
    elif aspect_type in ["create", "update"]:
        # Fetch activity details from Strava and store
        try:
            activity = fetch_activity_details(access_token, object_id)
            activity_id = store_activity(owner_id, activity)
            success = activity_id is not None

            # No leaderboard update here. distance_on_trail is set by trail
            # matching, which calls leaderboard_agg.recompute_for_activity
            # when it completes.
            if success and activity_id:
                trigger_trail_matching(activity_id)
        except StravaRateLimitError:
            # Bubble up so the SQS handler can defer the message rather than
            # letting it churn through retries and end up in the DLQ.
            raise
        except Exception as e:
            print(f"ERROR: Failed to fetch/store activity: {e}")
            # Don't mark as processed if fetch failed (might be temporary)
            return False
    else:
        print(f"Unknown aspect_type: {aspect_type}")
        success = True  # Mark as processed to avoid retrying unknown types

    # Mark event as processed
    if success:
        mark_event_processed(idempotency_key, webhook_event)
        update_last_webhook_received(owner_id)

    return success


def _defer_message_for_rate_limit(record, retry_after_seconds):
    """Extend the SQS visibility timeout for a single message so it isn't redelivered
    while we're still rate-limited. Falls back to letting SQS handle retry naturally
    if the API call fails (e.g. permissions issue)."""
    queue_arn = record.get("eventSourceARN")
    receipt_handle = record.get("receiptHandle")
    if not queue_arn or not receipt_handle:
        return False

    # Convert ARN -> URL: arn:aws:sqs:region:account:queue-name
    parts = queue_arn.split(":")
    if len(parts) < 6:
        return False
    region, account, queue_name = parts[3], parts[4], parts[5]
    queue_url = f"https://sqs.{region}.amazonaws.com/{account}/{queue_name}"

    timeout = _normalize_defer_seconds(retry_after_seconds)

    try:
        sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=timeout,
        )
        print(f"Deferred message {record.get('messageId')} for {timeout}s due to Strava 429")
        return True
    except Exception as e:
        print(f"WARNING: change_message_visibility failed for {record.get('messageId')}: {e}")
        return False


def _set_rate_limit_cooldown(retry_after_seconds):
    """Record a temporary in-memory cooldown for this warm Lambda runtime."""
    global _strava_cooldown_expires_epoch
    defer_seconds = _normalize_defer_seconds(retry_after_seconds)
    _strava_cooldown_expires_epoch = max(_strava_cooldown_expires_epoch, int(time.time()) + defer_seconds)
    return defer_seconds


def _get_rate_limit_cooldown_seconds():
    """Return remaining in-memory cooldown seconds, or 0 when no cooldown is active."""
    remaining = _strava_cooldown_expires_epoch - int(time.time())
    return max(0, remaining)


def _normalize_defer_seconds(retry_after_seconds):
    """Clamp retry/defer duration into the SQS-supported visibility timeout range."""
    base_seconds = retry_after_seconds if retry_after_seconds is not None else DEFAULT_RATE_LIMIT_DEFER_SECONDS
    return max(
        MIN_RATE_LIMIT_DEFER_SECONDS,
        min(base_seconds, MAX_VISIBILITY_TIMEOUT_SECONDS),
    )


def _apply_active_cooldown(rate_limited, defer_seconds_for_batch, batch_scope):
    """Apply an active cooldown to the current batch if needed."""
    if rate_limited:
        return rate_limited, defer_seconds_for_batch
    cooldown_seconds = _get_rate_limit_cooldown_seconds()
    if cooldown_seconds > 0:
        print(f"Strava cooldown active; deferring {batch_scope} for {cooldown_seconds}s")
        return True, cooldown_seconds
    return rate_limited, defer_seconds_for_batch


def handler(event, context):
    """
    Lambda handler triggered by SQS.
    Processes webhook events from the queue.

    Uses partial-batch failure reporting (ReportBatchItemFailures) so a single
    bad message doesn't recycle the entire batch. Requires the event source
    mapping to have FunctionResponseTypes=["ReportBatchItemFailures"] enabled.
    """
    print(f"webhook_processor handler invoked")

    # Validate required environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        raise RuntimeError("Missing database configuration")

    records = event.get("Records", [])
    print(f"Processing {len(records)} SQS records")

    batch_item_failures = []
    rate_limited = False
    cooldown_seconds = _get_rate_limit_cooldown_seconds()
    defer_seconds_for_batch = None
    if cooldown_seconds > 0:
        defer_seconds_for_batch = cooldown_seconds
        print(f"Strava cooldown active; deferring entire batch for {cooldown_seconds}s")
        rate_limited = True

    for record in records:
        message_id = record.get("messageId")
        try:
            message_body = record.get("body", "{}")
            webhook_event = json.loads(message_body)

            print(f"Processing SQS record: {message_id}")

            if rate_limited:
                # We've already hit the rate limit on this batch; don't burn more
                # of the budget. Defer the rest and let them retry later.
                _defer_message_for_rate_limit(record, defer_seconds_for_batch)
                batch_item_failures.append({"itemIdentifier": message_id})
                continue

            success = process_webhook_event(webhook_event)

            if not success:
                print(f"Failed to process event: {webhook_event}")
                batch_item_failures.append({"itemIdentifier": message_id})
            else:
                rate_limited, defer_seconds_for_batch = _apply_active_cooldown(
                    rate_limited,
                    defer_seconds_for_batch,
                    "remaining batch",
                )
        except StravaRateLimitError as rle:
            # Bound the retry window so we don't burn the SQS receive count
            # while Strava is throttling us. Defer this message and every
            # remaining message in the batch.
            cooldown_seconds = _set_rate_limit_cooldown(rle.retry_after_seconds)
            defer_seconds_for_batch = cooldown_seconds
            print(f"Strava rate-limited; deferring {message_id} (retry_after={rle.retry_after_seconds}, cooldown={cooldown_seconds}s)")
            _defer_message_for_rate_limit(record, cooldown_seconds)
            batch_item_failures.append({"itemIdentifier": message_id})
            rate_limited = True
        except Exception as e:
            print(f"ERROR processing SQS record {message_id}: {e}")
            import traceback
            traceback.print_exc()
            batch_item_failures.append({"itemIdentifier": message_id})

    if batch_item_failures:
        print(f"{len(batch_item_failures)} of {len(records)} records failed; reporting partial batch failure")

    return {"batchItemFailures": batch_item_failures}
