# Trail Re-match Runbook

How to refresh trail data and re-score existing activities against it. Use this
after the trail network changes (new segments, reroutes) or after a change to
the matching logic in `backend/match_activity_trail/`.

This runbook was written after the November 2026 re-match (tracked in
[#338](https://github.com/timhibbard/rabbit-miles/issues/338)). Every step
below has a reason that came from that run.

## Before you start

**Names.** Deployed Lambda names are not the folder names:

| Code | Deployed function |
|---|---|
| `backend/update_trail_data/` | `rabbitmiles-update-trail-data` |
| `backend/match_activity_trail/` | `rabbitmiles-match-activity-trail` |
| `backend/match_unmatched_activities/` | `rabbitmiles-match-unmatched-activities` |
| `backend/admin_recalculate_leaderboard/` | `rabbitmiles-admin-recalculate-leaderboard` |

**Permissions.** Check you have all of these **before step 4**. The earlier
steps only read, so a missing permission discovered mid-run leaves you stuck
with production half-changed.

| Permission | Used for |
|---|---|
| `lambda:InvokeFunction` on the four functions above | Publishing, matching, rebuilding |
| `lambda:GetFunctionConfiguration` | Reading `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME` from any of them |
| `rds-data:ExecuteStatement`, `secretsmanager:GetSecretValue` | All SQL |
| `events:ListRuleNamesByTarget`, `events:DisableRule`, `events:EnableRule` | Suspending and restoring scheduled batch matching (step 4, clean-up) |

A quick check is a read-only call to each: `get-function-configuration`,
`list-rule-names-by-target`, a `SELECT 1` through `rds-data`, and
`lambda invoke --invocation-type DryRun` on each function.

**Data API constraints** that shape the steps below:
- Responses over **1 MB** fail. Page every read (`WHERE id > :last ORDER BY id LIMIT n`).
- **One statement per call.** Multi-statement SQL is rejected.

**Pick a quiet time.** The matcher updates leaderboard rows as it goes, and
the leaderboard recalculation is best run when nothing else is matching.

Nothing in production changes until step 4. Steps 1–3 only read.

## 1. Fetch the candidate trail data locally

The update Lambda copies whatever greenvilleopenmap.info currently publishes
(`SwampRabbitWays.geojson`, `SwampRabbitConnectors.geojson`). Download both to
a scratch directory and check `Last-Modified`, feature counts and sizes. Keep
the **current** data alongside: the repo's `trail/` copies, or `aws s3 cp` from
`s3://rabbitmiles-trail-data/trails/` if you have read access. Don't refresh
`trail/` yet, because step 2 compares against it.

## 2. Estimate impact locally

Re-matching rewrites `distance_on_trail` for every activity, so measure first.
Download polylines (paged), run `calculate_trail_intersection` from
`backend/match_activity_trail/lambda_function.py` locally against the current
and candidate GeoJSON, and compare per athlete. With 8 worker processes this
takes a few minutes for about 23k activities. If the result looks wrong, stop
here. Nothing has been published.

Do this even for "small" trail changes. In November 2026 the trail refresh
itself changed totals by about 0 mi, but the local run exposed a matcher bug
worth about 1,700 mi
([#335](https://github.com/timhibbard/rabbit-miles/pull/335)).

## 3. Snapshot the baseline

Save `id, athlete_id, distance_on_trail, time_on_trail` for every activity to a
local CSV, paged by `id`. You need it for step 6 and for any rollback. Keep it
out of the repo, because it contains athlete data.

## 4. Publish the trail data and stop other matchers

From here on, production changes.

```bash
aws lambda invoke --function-name rabbitmiles-update-trail-data \
  --cli-binary-format raw-in-base64-out --payload '{}' response.json && cat response.json
```

The matcher reads S3 on every invocation, so new matches use the new data
immediately. Confirm the reported sizes match the candidate files from step 1.

**Suspend other producers of batch matching for the duration of the run.**
Anything else that invokes `rabbitmiles-match-unmatched-activities` can queue the
same rows you just reset. A late duplicate then overwrites a value step 6
restored. Producers include any EventBridge schedule targeting it (find them
with `aws events list-rule-names-by-target --target-arn <function ARN>`, then
`aws events disable-rule`) and `fetch_activities`, which triggers it after a
user's activity fetch. Re-enable the rules when the run is done.

## 5. Re-match in chunks

The batch matcher re-matches activities whose `last_matched IS NULL`. It
queues one async `rabbitmiles-match-activity-trail` invocation per activity.
Loop over chunks of about 400 activity IDs that have a polyline:

1. **Reset the chunk:**
   ```sql
   UPDATE activities SET last_matched = NULL
    WHERE id BETWEEN :lo AND :hi AND polyline IS NOT NULL AND polyline <> ''
   ```
2. **Queue it** with an **async** invoke, sized to the number unmatched:
   ```bash
   aws lambda invoke --function-name rabbitmiles-match-unmatched-activities \
     --invocation-type Event --cli-binary-format raw-in-base64-out \
     --payload '{"limit": 400}' out.json
   ```
   Don't use a synchronous invoke. The CLI's 60 s read timeout fails silently
   on large batches.
3. **Wait for the chunk to drain** (`SELECT COUNT(*) FROM activities WHERE last_matched IS NULL`
   reaches 0) before resetting the next chunk.

   **Bound the wait.** The batch matcher catches per-activity queueing errors
   and still returns normally, reporting them as `failed_to_queue`. Those rows
   are **never retried automatically**, and with other producers suspended
   they'd stay unmatched. If the unmatched count hasn't dropped for about 5
   minutes, queue again with `limit` set to the remaining count. For these
   small retry batches you can drop `--invocation-type Event` so `out.json`
   shows `queued` and `failed_to_queue` (keep batches under about 150 so the
   synchronous call finishes within the CLI's 60 s read timeout). Repeat up to
   about 5 times. If rows are still stuck after that, match one
   directly to see the error:
   ```bash
   aws lambda invoke --function-name rabbitmiles-match-activity-trail \
     --cli-binary-format raw-in-base64-out --payload '{"activity_id": <id>}' one.json && cat one.json
   ```
   Then fix the cause, or set `last_matched = NOW()` on those rows and note
   their IDs, so the run can continue. Their values are unchanged.

Expect about 90–250 s per 400-activity chunk, or 1.5–4 hours for the full set.

**A count of 0 doesn't mean all matching has finished.** It only means every row
has been matched at least once. Async invocations can still be queued or retrying
(Lambda retries failed async events twice, with delays of a few minutes). So
before step 6, after the last chunk *and* before a pause, wait until matching
has been **quiet for at least 10 minutes**, with no activity's `last_matched`
changing:

```sql
SELECT MAX(last_matched) FROM activities  -- unchanged for 10+ minutes
```

**Pausing.** Stop between chunks, never mid-chunk. If a chunk was already reset
when you stopped, set `last_matched = NOW()` on its rows. Their values haven't
changed yet, and this keeps the scheduled matcher from picking them up while
you're away. It does *not* cancel async work already queued, so wait for the
quiet period above, then run steps 6–8 for what's done so far, and resume
after the last finished ID.

## 6. Keep only higher values

```sql
-- for each activity whose new distance_on_trail is lower than the baseline:
UPDATE activities a SET distance_on_trail = v.d, time_on_trail = v.t
  FROM (VALUES (:id, :d, :t), ...) AS v(id, d, t)
 WHERE a.id = v.id
```

Why: many stored polylines are Strava **summary** polylines. Before
[#334](https://github.com/timhibbard/rabbit-miles/pull/334), the hourly list
poll overwrote detailed polylines with summary ones, and those weren't
re-fetched. A summary polyline cuts corners, so re-matching it gives *fewer*
trail miles than the athlete actually rode. In November 2026, 2,799 activities
(249.8 mi) would have dropped. Restore the baseline wherever the new value is
lower, and keep every increase.

Keep the list of restored IDs. Their leaderboard buckets were already rewritten
with the lower values by the matcher, so step 7 needs to cover them.

**Re-check right before step 7:** re-run the comparison and confirm that
**0** activities are now below baseline. If any are, a late match overwrote
them. Restore again, wait for another quiet period, and re-check.

## 7. Recompute leaderboard buckets for restored activities

Run this **before** the full rebuild. The matcher rewrote leaderboard buckets
with the lower values before step 6 restored the activities. The rebuild in
step 8 only covers in-season windows (from the week containing Jan 1, 2026),
so restored **pre-season** activities (2025 and earlier) would keep wrong
buckets.

For each restored activity, recompute its buckets with
`leaderboard_agg.recompute_for_activity(exec_sql, athlete_id, start_date_local,
user_timezone, activity_timezone)` from `backend/leaderboard_agg.py`. This only
re-sums from `activities`; it doesn't re-match, so restored values are safe.
Deduplicate first by (athlete, window), since many restored activities share
buckets. In November 2026, about 3,200 buckets took a few minutes with 12
threads. Retry transient Data API errors.

## 8. Rebuild the leaderboard

```bash
aws lambda invoke --function-name rabbitmiles-admin-recalculate-leaderboard \
  --cli-read-timeout 300 --cli-binary-format raw-in-base64-out \
  --payload '{"async_invocation": true}' out.json && cat out.json
```

This is a set-based rebuild of all in-season buckets, taking about 8 s, and it
never empties the table (see [`leaderboard-runbook.md`](leaderboard-runbook.md)).
Run it after step 7 and while matching is quiet.

## 9. Verify

- No activity left unmatched: `SELECT COUNT(*) FROM activities WHERE last_matched IS NULL` returns 0.
- Failed matches weren't masked. When matching errors, the matcher still
  stamps `last_matched` and writes **0**, so the unmatched count reaches 0, and
  step 6 then restores the baseline as if the drop were a downgraded polyline.
  The activity looks fine but was never re-scored. Among the restored
  activities, list those whose re-match came out at exactly 0 while the
  baseline was above 0. Compare them with step 2's local results: any the local
  run scored above 0 is a matching failure, not a polyline downgrade. Re-match
  those individually with a direct `rabbitmiles-match-activity-trail` invoke.
  For the restore step to know about these, record the post-match value of
  each restored activity before overwriting it.
- Pre-season buckets match activities too: for windows before the season,
  compare `leaderboard_agg` against `SUM(distance_on_trail)` grouped by
  athlete and window key. The rebuild doesn't touch these, so step 7 is what
  fixes them.
- Leaderboard matches activities: compare `leaderboard_agg` against the
  rebuild's `REBUILD_SELECT` (in
  `backend/admin_recalculate_leaderboard/lambda_function.py`) for missing and
  differing buckets. Both counts should be 0. Also check that week, month and
  year totals agree.
- Per-athlete report: baseline vs. current trail miles. Nobody should be lower.
  Share it privately, because the repo is public.

## Clean up

- Re-enable any EventBridge rules you disabled in step 4.
- Refresh the repo's reference copies in `trail/` from the published files.
  Nothing reads them, but they're the baseline for the next run's step 2.
- Delete the local snapshot, polylines and any scripts that embed the DB ARNs.
