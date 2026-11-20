#!/usr/bin/env python3
"""
Tests for admin_recalculate_leaderboard's set-based rebuild.

Run: python3 backend/admin_recalculate_leaderboard/test_lambda.py
"""

import os
import sys
from unittest.mock import patch, MagicMock

LAMBDA_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(LAMBDA_DIR)
for d in (LAMBDA_DIR, BACKEND_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)


def _import_lambda():
    with patch("boto3.client", return_value=MagicMock()):
        if "lambda_function" in sys.modules:
            del sys.modules["lambda_function"]
        import lambda_function
        return lambda_function


def _fake_db(fail_on=None):
    """Return (exec_sql stub, list of executed SQL kinds)."""
    calls = []

    def kind(sql):
        s = " ".join(sql.split())
        if "information_schema.tables" in s:
            return "check"
        if s.startswith("SELECT COUNT(*)"):
            return "count"
        if "clock_timestamp()" in s:
            return "clock"
        if s.startswith("INSERT INTO leaderboard_agg"):
            return "upsert"
        if s.startswith("DELETE FROM leaderboard_agg"):
            return "delete"
        return "other"

    def exec_sql(sql, parameters=None):
        k = kind(sql)
        calls.append((k, sql, parameters))
        if k == fail_on:
            raise Exception(f"simulated {k} failure")
        if k == "check":
            return {"records": [[{"booleanValue": True}]]}
        if k == "count":
            return {"records": [[{"longValue": 120}, {"longValue": 7}]]}
        if k == "clock":
            return {"records": [[{"stringValue": "2026-11-20 15:00:00.000001"}]]}
        if k == "upsert":
            return {"numberOfRecordsUpdated": 300}
        if k == "delete":
            return {"numberOfRecordsUpdated": 4}
        return {}

    return exec_sql, calls


def test_never_reads_activities_into_lambda():
    """No statement may return per-activity rows (that hit the 1 MB limit)."""
    print("\nTesting rebuild is set-based...")
    lf = _import_lambda()
    exec_sql, calls = _fake_db()
    with patch.object(lf, "exec_sql", side_effect=exec_sql):
        result = lf.recalculate_leaderboard()
    assert result == (120, 7, None, 0, 0, []), result
    kinds = [k for k, _, _ in calls]
    assert "other" not in kinds, f"unexpected statement executed: {kinds}"
    assert "GROUP BY" in lf.REBUILD_SQL and "ON CONFLICT" in lf.REBUILD_SQL
    print("  ✓ only check/count/clock/upsert/delete statements run")


def test_upsert_runs_before_delete():
    """The table must never be emptied before the rebuild has written rows."""
    print("\nTesting upsert precedes stale delete...")
    lf = _import_lambda()
    exec_sql, calls = _fake_db()
    with patch.object(lf, "exec_sql", side_effect=exec_sql):
        lf.recalculate_leaderboard()
    kinds = [k for k, _, _ in calls]
    assert kinds.index("clock") < kinds.index("upsert") < kinds.index("delete"), kinds
    delete_sql = [sql for k, sql, _ in calls if k == "delete"][0]
    assert "last_updated <" in delete_sql, "delete must only remove rows older than this run"
    delete_params = {p["name"] for p in [c for c in calls if c[0] == "delete"][0][2]}
    assert delete_params == {"run_started", "start_date"}, delete_params
    print("  ✓ clock -> upsert -> scoped delete of older rows")


def test_upsert_failure_leaves_table_untouched():
    print("\nTesting upsert failure does not delete anything...")
    lf = _import_lambda()
    exec_sql, calls = _fake_db(fail_on="upsert")
    with patch.object(lf, "exec_sql", side_effect=exec_sql):
        result = lf.recalculate_leaderboard()
    assert result[2] and "simulated upsert failure" in result[2], result
    assert "delete" not in [k for k, _, _ in calls], "must not delete after a failed upsert"
    print("  ✓ error returned, no delete issued")


def test_delete_is_scoped_to_rebuilt_windows():
    """Pre-season buckets are maintained per match and must survive a rebuild."""
    print("\nTesting stale delete is scoped to in-season windows...")
    lf = _import_lambda()
    sql = " ".join(lf.DELETE_STALE_SQL.split())
    for win in ("week", "month", "year"):
        assert f"\"window\" = '{win}' AND window_key >=" in sql, f"missing {win} scope"
    print("  ✓ delete limited to windows on/after the season start")


if __name__ == "__main__":
    print("Running admin_recalculate_leaderboard tests...")
    print("=" * 60)
    try:
        test_never_reads_activities_into_lambda()
        test_upsert_runs_before_delete()
        test_upsert_failure_leaves_table_untouched()
        test_delete_is_scoped_to_rebuilt_windows()
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
