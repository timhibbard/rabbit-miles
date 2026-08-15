#!/usr/bin/env python3
"""Guard the activity upsert contract across every ingest Lambda.

Seven Lambdas write to the activities table with near-identical ON CONFLICT
upserts. That duplication is where things quietly drift: webhook_processor --
the primary real-time path -- omitted athlete_count entirely, so group
activities ingested via webhook were pinned to the column default of 1 and the
group badge never rendered. Nothing failed; the field was simply never written.

These tests read the SQL out of each Lambda and assert the shared contract, so
the next divergence fails here instead of silently producing wrong data.

Pure text analysis: no boto3, no AWS, no database. Run directly:
    python3 backend/test_activity_upsert_consistency.py
"""

import io
import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Lambdas that read Strava's *list* endpoint (/athlete/activities). Its
# SummaryActivity carries map.summary_polyline only -- never the full polyline.
SUMMARY_SOURCE_LAMBDAS = [
    "fetch_activities",
    "scheduled_activity_update",
    "update_activities",
    "user_update_activities",
    "admin_update_activities",
    "admin_backfill_activities",
]

# Lambdas that read Strava's *detail* endpoint (/activities/{id}), which does
# carry the full polyline.
DETAIL_SOURCE_LAMBDAS = [
    "webhook_processor",
]

ALL_UPSERT_LAMBDAS = SUMMARY_SOURCE_LAMBDAS + DETAIL_SOURCE_LAMBDAS

# Fields Strava can change after upload, so every path must write them on
# conflict or stale values survive forever.
MUTABLE_FIELDS = [
    "name",             # renames
    "type",             # re-typing a Run as a Walk, etc.
    "athlete_count",    # grows as other participants upload a group activity
    "distance",
    "moving_time",
    "elapsed_time",
    "total_elevation_gain",
]

# Values computed by our own trail-matching, never sourced from Strava. These
# must be preserved on conflict, not clobbered by the incoming NULL.
COMPUTED_FIELDS = ["time_on_trail", "distance_on_trail"]


def _read_lambda(name):
    path = os.path.join(BACKEND_DIR, name, "lambda_function.py")
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_sql_comments(sql):
    """Drop -- line comments so they can't satisfy an assertion by accident."""
    return re.sub(r"--[^\n]*", "", sql)


def _extract_do_update_block(source, lambda_name):
    """Return the DO UPDATE SET body of the activities upsert, comments stripped."""
    match = re.search(
        r"INSERT INTO activities.*?DO UPDATE SET(.*?)(?:RETURNING|\"\"\")",
        source,
        re.DOTALL,
    )
    assert match, f"{lambda_name}: could not locate an activities DO UPDATE SET block"
    return _strip_sql_comments(match.group(1))


def _assignment_for(block, column):
    """Return the right-hand side assigned to `column`, or None if unassigned."""
    match = re.search(rf"(?<![\w.]){re.escape(column)}\s*=\s*([^,\n]+)", block)
    return match.group(1).strip() if match else None


def test_mutable_fields_are_written_by_every_path():
    """Every ingest path must refresh all Strava-mutable fields."""
    print("Testing that all mutable fields are written on conflict...")
    for name in ALL_UPSERT_LAMBDAS:
        block = _extract_do_update_block(_read_lambda(name), name)
        for column in MUTABLE_FIELDS:
            assigned = _assignment_for(block, column)
            assert assigned is not None, (
                f"{name}: '{column}' is never written in DO UPDATE SET. Strava can "
                f"change it after upload, so omitting it strands stale data."
            )
            assert "EXCLUDED" in assigned, (
                f"{name}: '{column}' is assigned '{assigned}', which does not take "
                f"the incoming Strava value."
            )
        print(f"  ✓ {name}: all {len(MUTABLE_FIELDS)} mutable fields written")


def test_computed_trail_fields_are_preserved():
    """Trail metrics are ours, not Strava's -- an upsert must not clear them."""
    print("Testing that computed trail metrics survive an upsert...")
    for name in ALL_UPSERT_LAMBDAS:
        block = _extract_do_update_block(_read_lambda(name), name)
        for column in COMPUTED_FIELDS:
            assigned = _assignment_for(block, column)
            if assigned is None:
                continue  # Not touching the column at all also preserves it.
            assert assigned.startswith("COALESCE(activities."), (
                f"{name}: '{column}' is assigned '{assigned}'. It must be "
                f"COALESCE(activities.{column}, ...) or omitted, otherwise a "
                f"refresh wipes trail matching results."
            )
        print(f"  ✓ {name}: trail metrics preserved")


def test_summary_polyline_never_overwrites_full_polyline():
    """The list endpoint's summary polyline must not downgrade a stored full one."""
    print("Testing polyline downgrade protection...")
    for name in SUMMARY_SOURCE_LAMBDAS:
        block = _extract_do_update_block(_read_lambda(name), name)
        assigned = _assignment_for(block, "polyline")
        assert assigned is not None, f"{name}: 'polyline' unexpectedly unassigned"
        assert assigned.startswith("COALESCE(activities.polyline"), (
            f"{name}: reads the Strava list endpoint (summary_polyline only) but "
            f"assigns polyline = '{assigned}'. That overwrites the full polyline "
            f"stored from the detail endpoint. Use "
            f"COALESCE(activities.polyline, EXCLUDED.polyline)."
        )
        print(f"  ✓ {name}: summary polyline cannot downgrade a full one")

    for name in DETAIL_SOURCE_LAMBDAS:
        block = _extract_do_update_block(_read_lambda(name), name)
        assigned = _assignment_for(block, "polyline")
        assert assigned == "EXCLUDED.polyline", (
            f"{name}: reads the Strava detail endpoint, so it should assign "
            f"polyline = EXCLUDED.polyline to upgrade a stored summary polyline, "
            f"but assigns '{assigned}'."
        )
        print(f"  ✓ {name}: detail polyline upgrades the stored value")


def test_athlete_count_bind_parameter_is_supplied():
    """A column in the SQL is useless if no parameter is bound to it."""
    print("Testing that athlete_count is extracted and bound...")
    for name in ALL_UPSERT_LAMBDAS:
        source = _read_lambda(name)
        assert 'activity.get("athlete_count"' in source, (
            f"{name}: never reads athlete_count off the Strava payload."
        )
        assert re.search(r'"name":\s*"ac"', source), (
            f"{name}: no ':ac' bind parameter supplied for athlete_count."
        )
        print(f"  ✓ {name}: athlete_count extracted and bound")


def test_athlete_count_defaults_to_one():
    """Strava omits athlete_count on some payloads; a solo activity means 1."""
    print("Testing athlete_count default...")
    for name in ALL_UPSERT_LAMBDAS:
        source = _read_lambda(name)
        assert re.search(r'activity\.get\("athlete_count",\s*1\)', source), (
            f"{name}: athlete_count must default to 1 when Strava omits it, "
            f"otherwise the bind parameter receives None and the insert fails."
        )
        print(f"  ✓ {name}: defaults to 1")


def main():
    tests = [
        test_mutable_fields_are_written_by_every_path,
        test_computed_trail_fields_are_preserved,
        test_summary_polyline_never_overwrites_full_polyline,
        test_athlete_count_bind_parameter_is_supplied,
        test_athlete_count_defaults_to_one,
    ]

    print("=" * 72)
    print("Activity upsert consistency tests")
    print("=" * 72)

    failures = []
    for test in tests:
        try:
            test()
        except AssertionError as e:
            failures.append(f"{test.__name__}: {e}")
            print(f"  ✗ FAILED: {e}")
        print()

    print("=" * 72)
    if failures:
        print(f"❌ {len(failures)} test(s) failed:")
        for failure in failures:
            print(f"  - {failure}")
        print("=" * 72)
        return 1

    print("✅ All activity upsert consistency tests passed!")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
