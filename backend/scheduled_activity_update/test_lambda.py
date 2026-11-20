#!/usr/bin/env python3
"""
Tests for scheduled_activity_update user selection and sweep stamping.

Run: python3 backend/scheduled_activity_update/test_lambda.py
"""

import os
import sys
from unittest.mock import patch, MagicMock

LAMBDA_DIR = os.path.dirname(os.path.abspath(__file__))
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)


def _import_lambda():
    with patch("boto3.client", return_value=MagicMock()):
        if "lambda_function" in sys.modules:
            del sys.modules["lambda_function"]
        import lambda_function
        return lambda_function


def test_selection_is_sweep_only():
    """The primary selection must not treat webhook-stale users as due.

    Webhook-stale only means "hasn't uploaded in 6h", so OR-ing it in polled
    most users every hour and blew the Strava read budget.
    """
    print("\nTesting poll selection uses the refresh sweep only...")
    lf = _import_lambda()
    seen = []

    def fake_exec(sql, params=None):
        seen.append(sql)
        return {"records": []}

    with patch.object(lf, "_exec_sql", side_effect=fake_exec):
        lf.get_users_needing_poll()

    primary = seen[0]
    assert "last_metadata_refresh_at" in primary, "primary query should filter on the sweep stamp"
    assert "last_webhook_received_at" not in primary, (
        "primary query must not select users by webhook staleness"
    )
    assert len(seen) == 1, "fallback queries should not run when the primary succeeds"
    print("  ✓ primary query selects on last_metadata_refresh_at only")


def test_selection_falls_back_before_migration_016():
    """If the sweep column is missing, fall back to the previous selection."""
    print("\nTesting pre-migration fallback...")
    lf = _import_lambda()
    seen = []

    def fake_exec(sql, params=None):
        seen.append(sql)
        if len(seen) == 1:
            raise Exception('column "last_metadata_refresh_at" does not exist')
        return {"records": []}

    with patch.object(lf, "_exec_sql", side_effect=fake_exec):
        lf.get_users_needing_poll()

    assert len(seen) == 2, "should fall back exactly once"
    assert "last_webhook_received_at" in seen[1], "fallback keeps webhook-freshness filter"
    print("  ✓ falls back to webhook-freshness selection")


def _run_user(lf, store_results):
    user = {
        "athlete_id": 42,
        "access_token": "a",
        "refresh_token": "r",
        "expires_at": 9999999999,
        "profile_pic_stale": False,
    }
    activities = [{"id": i} for i in range(len(store_results))]
    with patch.object(lf, "ensure_valid_token", return_value="a"), \
         patch.object(lf, "fetch_strava_activities", return_value=activities), \
         patch.object(lf, "store_activity", side_effect=store_results), \
         patch.object(lf, "mark_metadata_refreshed") as mark:
        result = lf.update_recent_activities_for_user(user)
    return result, mark


def test_stamp_only_on_clean_pass():
    print("\nTesting sweep stamp is only written on a clean pass...")
    lf = _import_lambda()

    result, mark = _run_user(lf, [True, True, True])
    assert result["failed"] == 0
    mark.assert_called_once_with(42)
    print("  ✓ all writes succeeded -> stamped")

    result, mark = _run_user(lf, [True, False, True])
    assert result["failed"] == 1
    mark.assert_not_called()
    print("  ✓ one write failed -> not stamped (retried next run)")


def _run_handler(lf, n_users, remaining_ms_seq, rate_limit_at=None):
    """Run the handler over n_users with a context whose remaining time follows
    remaining_ms_seq (one value per check). Returns (_self_continue mock, processed ids)."""
    os.environ["DB_CLUSTER_ARN"] = "arn:test"
    os.environ["DB_SECRET_ARN"] = "arn:test"
    users = [{"athlete_id": i, "access_token": "a", "refresh_token": "r",
              "expires_at": 9999999999, "profile_pic_stale": False} for i in range(n_users)]
    times = iter(remaining_ms_seq)
    context = MagicMock()
    context.get_remaining_time_in_millis.side_effect = lambda: next(times, 0)
    processed = []

    def fake_update(user, context=None):
        if rate_limit_at is not None and user["athlete_id"] == rate_limit_at:
            raise lf.RateLimitExhaustedError("quota")
        processed.append(user["athlete_id"])
        return {"athlete_id": user["athlete_id"], "success": True, "stored": 0, "failed": 0}

    with patch.object(lf, "get_users_needing_poll", return_value=users), \
         patch.object(lf, "update_recent_activities_for_user", side_effect=fake_update), \
         patch.object(lf, "_self_continue") as cont, \
         patch.object(lf.time, "sleep"):
        lf.handler({}, context)
    return cont, processed


def test_time_budget_abort_self_continues():
    """Running out of Lambda time must continue in a fresh invocation, not wait
    an hour. Deferring capped each run at ~18 users with the 123 s timeout."""
    print("\nTesting time-budget abort self-continues...")
    lf = _import_lambda()
    plenty, low = 120_000, 10_000
    cont, processed = _run_handler(lf, 10, [plenty] * 4 + [low] * 10)
    assert processed == [0, 1, 2, 3], processed
    cont.assert_called_once()
    assert cont.call_args[0][1] == [4, 5, 6, 7, 8, 9], cont.call_args
    print("  ✓ processed 4, continued with the remaining 6 immediately")


def test_rate_limit_abort_defers():
    print("\nTesting rate-limit abort defers to next scheduled run...")
    lf = _import_lambda()
    cont, processed = _run_handler(lf, 10, [120_000] * 20, rate_limit_at=3)
    assert processed == [0, 1, 2], processed
    cont.assert_not_called()
    print("  ✓ stopped at the rate limit without self-invoking")


def test_time_abort_without_progress_defers():
    """No self-invoke loop: a time abort before any user is processed defers."""
    print("\nTesting time abort with no progress does not loop...")
    lf = _import_lambda()
    cont, processed = _run_handler(lf, 5, [10_000] * 10)
    assert processed == [], processed
    cont.assert_not_called()
    print("  ✓ no users processed -> no self-continue")


if __name__ == "__main__":
    print("Running scheduled_activity_update tests...")
    print("=" * 60)
    try:
        test_selection_is_sweep_only()
        test_selection_falls_back_before_migration_016()
        test_stamp_only_on_clean_pass()
        test_time_budget_abort_self_continues()
        test_rate_limit_abort_defers()
        test_time_abort_without_progress_defers()
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
