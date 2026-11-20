# rabbitmiles-admin-recalculate-leaderboard (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for session verification)
# FRONTEND_URL (for CORS)
# ADMIN_ATHLETE_IDS (comma-separated list of admin athlete IDs)

import os
import json
import time
from urllib.parse import urlparse
import boto3

import admin_utils

rds = boto3.client("rds-data")
lambda_client = boto3.client("lambda")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
LAMBDA_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")

# Filter activities starting from Jan 1, 2026 00:00:00 UTC
RECALC_START_DATE = "2026-01-01 00:00:00"


def get_cors_origin():
    """Extract origin (scheme + host) from FRONTEND_URL for CORS headers"""
    if not FRONTEND_URL:
        return None
    parsed = urlparse(FRONTEND_URL)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def exec_sql(sql, parameters=None):
    """Execute SQL using RDS Data API"""
    kwargs = dict(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        sql=sql,
        database=DB_NAME
    )
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


# The rebuilt bucket set, shared by the upsert and the stale-row cleanup so the
# two can never disagree. Window keys must match leaderboard_agg.get_window_bounds:
# start_date_local is a naive local timestamp, so week = Monday of that date,
# month = YYYY-MM, year = YYYY. Buckets: 'all' for every activity, plus 'foot'
# (Run, Walk) or 'bike' (Ride), mirroring leaderboard_agg.TYPE_FILTER_SQL.
#
# RECALC_START_DATE is applied per window, not per activity: a window is rebuilt
# when it *starts* on or after the window containing RECALC_START_DATE. Without
# that, the week of 2025-12-29 (which runs into 2026) lost its Dec 29-31
# activities here while the per-activity recompute after each match counted
# them, so the two paths disagreed on that week.
REBUILD_SELECT = """
SELECT w.win AS win, w.win_key AS win_key, t.agg_type AS agg_type,
       a.athlete_id AS athlete_id, SUM(a.distance_on_trail) AS value
  FROM activities a
  JOIN users u ON u.athlete_id = a.athlete_id
 CROSS JOIN LATERAL (VALUES
        ('week',  'week_'  || to_char(date_trunc('week', a.start_date_local), 'YYYY-MM-DD'),
                  date_trunc('week', a.start_date_local), date_trunc('week', CAST(:start_date AS TIMESTAMP))),
        ('month', 'month_' || to_char(a.start_date_local, 'YYYY-MM'),
                  date_trunc('month', a.start_date_local), date_trunc('month', CAST(:start_date AS TIMESTAMP))),
        ('year',  'year_'  || to_char(a.start_date_local, 'YYYY'),
                  date_trunc('year', a.start_date_local), date_trunc('year', CAST(:start_date AS TIMESTAMP)))
       ) AS w(win, win_key, win_start, first_win_start)
 CROSS JOIN LATERAL (VALUES
        ('all'),
        (CASE WHEN a.type IN ('Run', 'Walk') THEN 'foot'
              WHEN a.type = 'Ride' THEN 'bike' END)
       ) AS t(agg_type)
 WHERE u.show_on_leaderboards = true
   AND a.start_date_local >= date_trunc('week', CAST(:start_date AS TIMESTAMP))
   AND w.win_start >= w.first_win_start
   AND a.distance_on_trail IS NOT NULL
   AND t.agg_type IS NOT NULL
 GROUP BY w.win, w.win_key, t.agg_type, a.athlete_id
"""

REBUILD_SQL = f"""
INSERT INTO leaderboard_agg ("window", window_key, metric, activity_type, athlete_id, value, last_updated)
SELECT r.win, r.win_key, 'distance', r.agg_type, r.athlete_id, r.value, now()
  FROM ({REBUILD_SELECT}) AS r
ON CONFLICT (window_key, metric, activity_type, athlete_id)
DO UPDATE SET "window" = EXCLUDED."window", value = EXCLUDED.value, last_updated = now()
"""

# Delete in-season rows that are not in the rebuilt set: buckets for users who
# opted out, or whose activities were deleted, moved to another window, or lost
# their trail distance.
#
# Concurrency with per-match recomputes (leaderboard_agg._recompute_one, the
# only other writer, which always sets last_updated = now()):
#   - Membership is an anti-join against the rebuilt set (computed once as a
#     MATERIALIZED CTE; a correlated NOT EXISTS re-ran the aggregation per row
#     and hit the statement timeout), not a last_updated
#     watermark. now() is transaction *start* time, so a slow concurrent write
#     could carry an older timestamp than the run start.
#   - The candidate rows are captured with their last_updated (stale CTE), and a
#     row is only deleted if last_updated is still unchanged. Under READ
#     COMMITTED, when the DELETE meets a row a concurrent match has just
#     updated, PostgreSQL rechecks the join against the *new* row version but
#     evaluates the anti-join CTE against the original snapshot. Without
#     the last_updated equality, a placeholder that match just made non-zero
#     would still pass NOT EXISTS and be deleted. With it, the changed
#     last_updated fails the recheck and the row is kept.
#   - Rows inserted concurrently are not in the stale snapshot, so they are kept.
#
# Scoped to the windows the rebuild covers, so pre-season buckets (which the
# per-match recompute maintains and the leaderboard can show as "previous
# year") are left alone. Window keys are zero-padded ISO dates, so string
# comparison orders them correctly.
IN_SEASON_SCOPE = """(
        (l."window" = 'week'  AND l.window_key >= 'week_'  || to_char(date_trunc('week',  CAST(:start_date AS TIMESTAMP)), 'YYYY-MM-DD'))
     OR (l."window" = 'month' AND l.window_key >= 'month_' || to_char(date_trunc('month', CAST(:start_date AS TIMESTAMP)), 'YYYY-MM'))
     OR (l."window" = 'year'  AND l.window_key >= 'year_'  || to_char(date_trunc('year',  CAST(:start_date AS TIMESTAMP)), 'YYYY'))
   )"""

DELETE_STALE_SQL = f"""
WITH rebuilt AS MATERIALIZED (
{REBUILD_SELECT}
),
stale AS MATERIALIZED (
    SELECT l.window_key, l.metric, l.activity_type, l.athlete_id, l.last_updated
      FROM leaderboard_agg l
      LEFT JOIN rebuilt r
        ON r.win_key = l.window_key
       AND r.agg_type = l.activity_type
       AND r.athlete_id = l.athlete_id
     WHERE r.athlete_id IS NULL
       AND l.metric = 'distance'
       AND {IN_SEASON_SCOPE}
)
DELETE FROM leaderboard_agg t
 USING stale s
 WHERE t.window_key = s.window_key
   AND t.metric = s.metric
   AND t.activity_type = s.activity_type
   AND t.athlete_id = s.athlete_id
   AND t.last_updated = s.last_updated
"""

# Same activity boundary as REBUILD_SELECT (the Monday of the week containing
# RECALC_START_DATE), so the reported counts match what was aggregated.
COUNT_SQL = """
SELECT COUNT(*), COUNT(DISTINCT a.athlete_id)
  FROM activities a
  JOIN users u ON u.athlete_id = a.athlete_id
 WHERE u.show_on_leaderboards = true
   AND a.start_date_local >= date_trunc('week', CAST(:start_date AS TIMESTAMP))
   AND a.distance_on_trail IS NOT NULL
"""


def recalculate_leaderboard():
    """
    Rebuild leaderboard_agg from activities since RECALC_START_DATE.

    Set-based and never reads activities into the Lambda, so the Data API's
    1 MB result limit no longer applies (the previous version SELECTed every
    activity and failed once that passed 1 MB). Runs as two atomic statements
    with no transaction (Lambda roles only grant rds-data:ExecuteStatement):

      1. Upsert every rebuilt bucket.
      2. Delete in-season rows that are not in the rebuilt set (see
         DELETE_STALE_SQL). Pre-season buckets are kept.

    The table is never empty in between. The previous version DELETEd
    everything first and then failed on the 1 MB query, leaving the leaderboard
    empty. If step 1 fails, nothing changes; if step 2 fails, the only effect
    is that a few stale rows remain until the next run.

    Returns:
        Tuple of (activities_processed, athletes_processed, error_message,
        activities_skipped, insert_failed, athletes_with_errors). The last three
        are always 0/0/[]: each statement applies completely or not at all.
    """
    print("=== recalculate_leaderboard START ===")
    print(f"LOG - Recalculating leaderboard aggregates from {RECALC_START_DATE}")

    params = [{"name": "start_date", "value": {"stringValue": RECALC_START_DATE}}]

    try:
        # Step 0: Verify that leaderboard_agg table exists
        check_table_sql = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'leaderboard_agg'
        )
        """
        records = exec_sql(check_table_sql).get("records", [])
        table_exists = bool(records and records[0] and records[0][0].get("booleanValue", False))
        if not table_exists:
            error_msg = (
                "The leaderboard_agg table does not exist. "
                "Please run the database migration: backend/migrations/008_create_leaderboard_agg_table.sql"
            )
            print(f"ERROR: {error_msg}")
            return 0, 0, error_msg, 0, 0, []

        # Step 1: Count what will be aggregated (two numbers, not every row)
        count_record = exec_sql(COUNT_SQL, params).get("records", [[{}, {}]])[0]
        activities_processed = int(count_record[0].get("longValue", 0))
        athletes_processed = int(count_record[1].get("longValue", 0))
        print(f"LOG - {activities_processed} activities from {athletes_processed} opted-in athletes")

        # Step 2: Upsert every rebuilt bucket
        upserted = exec_sql(REBUILD_SQL, params).get("numberOfRecordsUpdated", 0)
        print(f"LOG - Upserted {upserted} leaderboard_agg rows")

        # Step 3: Remove in-season buckets the rebuild no longer produces
        deleted = exec_sql(DELETE_STALE_SQL, params).get("numberOfRecordsUpdated", 0)
        print(f"LOG - Deleted {deleted} stale leaderboard_agg rows")

        print("=== recalculate_leaderboard END: SUCCESS ===")
        return activities_processed, athletes_processed, None, 0, 0, []

    except Exception as e:
        error = f"Recalculation failed: {e}"
        print(f"ERROR: {error}")
        import traceback
        traceback.print_exc()
        return 0, 0, error, 0, 0, []


def handler(event, context):
    print("=" * 80)
    print("ADMIN RECALCULATE LEADERBOARD - START")
    print("=" * 80)
    
    start_time = time.time()
    
    cors_origin = get_cors_origin()
    headers = admin_utils.get_admin_headers(cors_origin)
    
    # Check if this is an async invocation (no API Gateway requestContext)
    # When invoked asynchronously by itself, skip auth and run recalculation directly
    is_async_invocation = event.get("async_invocation") is True
    
    if is_async_invocation:
        print("LOG - Running as async invocation (background task)")
        
        # Validate required environment variables
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        # Perform recalculation directly (no auth check needed - already verified)
        result = recalculate_leaderboard()
        activities_processed, athletes_processed, error_message, activities_skipped, insert_failed, athletes_with_errors = result
        
        if error_message:
            print(f"ERROR - Recalculation failed: {error_message}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "recalculation failed",
                    "message": error_message
                })
            }
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"LOG - Recalculation successful in {duration_ms:.2f}ms")
        print(f"LOG - Processed {activities_processed} activities from {athletes_processed} athletes")
        if activities_skipped > 0 or insert_failed > 0:
            print(f"LOG - Skipped {activities_skipped} activities and {insert_failed} inserts due to errors")
        print("=" * 80)
        print("ADMIN RECALCULATE LEADERBOARD - SUCCESS")
        print("=" * 80)
        
        response_data = {
            "message": "Leaderboard recalculation completed successfully",
            "activities_processed": activities_processed,
            "athletes_processed": athletes_processed,
            "duration_ms": round(duration_ms, 2)
        }
        
        # Include warning information if there were errors
        if activities_skipped > 0 or insert_failed > 0:
            response_data["warnings"] = {
                "activities_skipped": activities_skipped,
                "insert_failed": insert_failed,
                "athletes_with_errors": athletes_with_errors
            }
            response_data["message"] = f"Leaderboard recalculation completed with {activities_skipped + insert_failed} items skipped due to errors"
        
        return {
            "statusCode": 200,
            "body": json.dumps(response_data)
        }
    
    # Handle OPTIONS preflight requests
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        print("LOG - OPTIONS preflight request")
        return {
            "statusCode": 200,
            "headers": {
                **headers,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Cookie",
                "Access-Control-Max-Age": "86400"
            },
            "body": ""
        }
    
    try:
        # Validate required environment variables
        if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
            print("ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        if not APP_SECRET:
            print("ERROR - Missing APP_SECRET")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        if not LAMBDA_FUNCTION_NAME:
            print("ERROR - Missing AWS_LAMBDA_FUNCTION_NAME")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "server configuration error"})
            }
        
        # Verify session and admin status
        print("LOG - Verifying admin session")
        athlete_id, is_admin = admin_utils.verify_admin_session(event, APP_SECRET)
        
        if not athlete_id:
            print("ERROR - Not authenticated")
            return {
                "statusCode": 401,
                "headers": headers,
                "body": json.dumps({"error": "not authenticated"})
            }
        
        if not is_admin:
            print(f"ERROR - User {athlete_id} is not an admin")
            admin_utils.audit_log_admin_action(
                athlete_id,
                "/admin/leaderboard/recalculate",
                "access_denied",
                {"reason": "not in admin allowlist"}
            )
            return {
                "statusCode": 403,
                "headers": headers,
                "body": json.dumps({"error": "forbidden"})
            }
        
        print(f"LOG - Admin {athlete_id} authenticated successfully")
        print("LOG - Triggering asynchronous leaderboard recalculation")
        
        # Audit log
        admin_utils.audit_log_admin_action(
            athlete_id,
            "/admin/leaderboard/recalculate",
            "recalculate_leaderboard_triggered",
            {"start_date": RECALC_START_DATE}
        )
        
        # Invoke this Lambda asynchronously to perform the actual recalculation
        # This allows us to return immediately to the client (avoiding 30s API Gateway timeout)
        try:
            async_event = {
                "async_invocation": True,
                "triggered_by_athlete_id": athlete_id
            }
            
            response = lambda_client.invoke(
                FunctionName=LAMBDA_FUNCTION_NAME,
                InvocationType='Event',  # Async invocation - returns immediately
                Payload=json.dumps(async_event)
            )
            
            status_code = response.get('StatusCode')
            print(f"LOG - Successfully triggered async recalculation: Lambda invocation status {status_code}")
            
            # Status codes: 202 = Accepted (async), 200 = OK (sync but shouldn't happen)
            # Any other status code indicates a problem
            if status_code not in [200, 202]:
                error_msg = f"Lambda invocation returned unexpected status code: {status_code}"
                print(f"ERROR - {error_msg}")
                return {
                    "statusCode": 500,
                    "headers": headers,
                    "body": json.dumps({
                        "error": "Failed to trigger recalculation",
                        "message": error_msg
                    })
                }
        
        except Exception as e:
            print(f"ERROR - Failed to trigger async recalculation: {e}")
            import traceback
            traceback.print_exc()
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": "Failed to trigger recalculation",
                    "message": str(e)
                })
            }
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"LOG - Async trigger completed in {duration_ms:.2f}ms")
        print("=" * 80)
        print("ADMIN RECALCULATE LEADERBOARD - ASYNC TRIGGERED")
        print("=" * 80)
        
        return {
            "statusCode": 202,  # 202 Accepted - processing in background
            "headers": headers,
            "body": json.dumps({
                "message": "Leaderboard recalculation started successfully. This process runs in the background and may take up to 1 minute to complete.",
                "status": "processing"
            })
        }
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        print(f"ERROR - Unexpected exception: {type(e).__name__}: {str(e)}")
        print(f"ERROR - Duration: {duration_ms:.2f}ms")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("ADMIN RECALCULATE LEADERBOARD - FAILED")
        print("=" * 80)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "internal server error"})
        }
