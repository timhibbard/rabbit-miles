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


if __name__ == "__main__":
    print("Running scheduled_activity_update tests...")
    print("=" * 60)
    try:
        test_selection_is_sweep_only()
        test_selection_falls_back_before_migration_016()
        test_stamp_only_on_clean_pass()
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
