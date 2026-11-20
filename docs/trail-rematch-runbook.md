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
| `lambda:GetFunctionConfiguration`, `lambda:UpdateFunctionConfiguration` on `fetch_activities` | Removing and restoring its batch-matching trigger (step 4, clean-up) |
| `lambda:PutFunctionEventInvokeConfig`, `lambda:DeleteFunctionEventInvokeConfig` on the matcher | Optional: bounding async event age for the run (step 5) |
| `cloudwatch:GetMetricStatistics` | Checking the matcher's async queue and throttles before step 6 |

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
restored. There are two producers:

- **EventBridge schedules** targeting it. Find them with
  `aws events list-rule-names-by-target --target-arn <function ARN>`, then
  `aws events disable-rule --name <rule>`.
- **`fetch_activities`**, which invokes it (limit 75) after any user's activity
  fetch whenever its `MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN` env var is set.
  Remove that variable for the duration of the run. Note that
  `update-function-configuration --environment` **replaces the whole variable
  set**, so save the current one first:
  The saved environment holds secrets (`APP_SECRET`, Strava client secret), so
  write it **outside the repo**, never to the working directory of this
  public repo:
  ```bash
  FETCH_ENV=$(mktemp)   # outside the repo; delete in clean-up
  aws lambda get-function-configuration --function-name <fetch_activities name> \
    --query Environment > "$FETCH_ENV"
  # then re-apply it without MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN
  ```
  New activities still sync, but they arrive with `last_matched` NULL, so the
  batch matcher picks them up with whichever chunk is queued next (see
  step 5.2).

Both are restored in clean-up.

**Paths that match directly**, without going through the batch matcher, keep
running. `webhook_processor` invokes the matcher on every activity
create/update webhook, and the user-facing `reset_last_matched` endpoint can
reset and re-match a user's activities. Either can re-match a restored
activity between steps 6 and 8, for example when an athlete renames an old
activity. They're rare enough that the plan is to **accept them and catch them**:
the step 6 re-check and the step 9 per-athlete check both detect a value below
baseline. To rule them out, also remove `MATCH_ACTIVITY_LAMBDA_ARN` from
`webhook_processor` for the run, using the same save-outside-the-repo and
re-apply approach.

**Pre-flight:** before step 5, `SELECT COUNT(*) FROM activities WHERE
last_matched IS NULL` should be 0. Any pre-existing NULL rows are stuck for
some other reason (see step 5.3). Deal with them first, or they'll stall every
chunk's drain check.

## 5. Re-match in chunks

The batch matcher re-matches activities whose `last_matched IS NULL`. It
queues one async `rabbitmiles-match-activity-trail` invocation per activity.
Loop over chunks of about 400 activity IDs that have a polyline:

1. **Reset the chunk:**
   ```sql
   UPDATE activities SET last_matched = NULL
    WHERE id BETWEEN :lo AND :hi AND polyline IS NOT NULL AND polyline <> ''
   ```
2. **Queue it** with an **async** invoke. Set `limit` to the **table-wide**
   unmatched count (`SELECT COUNT(*) FROM activities WHERE last_matched IS NULL`),
   not the chunk size. The batch matcher picks rows across the whole table
   (`WHERE last_matched IS NULL ORDER BY start_date DESC LIMIT :limit`), so
   newer NULL rows outside the chunk (activities fetched mid-run, a user's
   reset, stuck rows) take slots first and the chunk's oldest rows would never
   be queued:
   ```bash
   aws lambda invoke --function-name rabbitmiles-match-unmatched-activities \
     --invocation-type Event --cli-binary-format raw-in-base64-out \
     --payload '{"limit": 400}' out.json
   ```
   Don't use a synchronous invoke. The CLI's 60 s read timeout fails silently
   on large batches.
3. **Wait for the chunk to drain** before resetting the next one, counting
   **only this chunk**:
   ```sql
   SELECT COUNT(*) FROM activities
    WHERE last_matched IS NULL AND id BETWEEN :lo AND :hi
   ```
   A table-wide count also picks up rows inserted mid-run, and rows the matcher
   never stamps. If matching fails before the DB write (activity missing, no
   `athlete_id`), the handler returns a 404 or 500 without touching
   `last_matched`.

   **Bound the wait.** The batch matcher catches per-activity queueing errors
   and still returns normally, reporting them as `failed_to_queue`. Those rows
   are **never retried automatically**, and with other producers suspended
   they'd stay unmatched. If the unmatched count hasn't dropped for about 5
   minutes, queue again with `limit` set to the **table-wide** unmatched count
   (for the same reason as step 5.2). For these
   small retry batches you can drop `--invocation-type Event` so `out.json`
   shows `queued` and `failed_to_queue` (keep batches under about 150 so the
   synchronous call finishes within the CLI's 60 s read timeout). Repeat up to
   about 5 times. If rows are still stuck after that, match one
   directly to see the error:
   ```bash
   aws lambda invoke --function-name rabbitmiles-match-activity-trail \
     --cli-binary-format raw-in-base64-out --payload '{"activity_id": <id>}' one.json && cat one.json
   ```
   Read the body's `message`, **not** `statusCode`. A matching failure still
   returns `statusCode: 200`, with `"Matching failed: …"` or
   `"Processing failed: …"`, after writing 0 and stamping the row. Only
   `"Successfully matched"` is a success. A 404 or 500 means it failed before
   the DB write.

   Then fix the cause, or set `last_matched = NOW()` on those rows and note
   their IDs as **not re-scored**, so the run can continue. Their values are
   unchanged.

Expect about 90–250 s per 400-activity chunk, or 1.5–4 hours for the full set.

**A count of 0 doesn't mean all matching has finished.** It only means every row
has been matched at least once. Duplicate invocations can still be in Lambda's
async queue:

- **Throttled** events, when 400 async invokes exceed concurrency, are retried
  for up to the function's `MaximumEventAgeInSeconds`, which **defaults to 6
  hours**.
- **Errors** are *not* retried. `match_activity` catches matching errors
  itself (it writes 0, stamps the row and returns 200 with a failure
  `message`), and the handler turns anything else into a 404 or 500 response.
  Since no exception escapes, Lambda only retries timeouts and out-of-memory
  crashes, and those at most twice.

A quiet period on its own isn't proof. Before step 6, after the last chunk
*and* before a pause, check both of these:

1. Matching has been **quiet for at least 10 minutes**:
   ```sql
   SELECT MAX(last_matched) FROM activities  -- unchanged for 10+ minutes
   ```
2. The async queue is empty. In CloudWatch, `AWS/Lambda` `AsyncEventsReceived`
   vs. processed and `AsyncEventAge` for `rabbitmiles-match-activity-trail`
   should be flat, with no recent `Throttles`. To bound the risk up front,
   give the matcher a short event age for the run. Events older than that are
   dropped rather than applied late, and any rows they leave unmatched show up
   in the drain check. Save the existing async config first, because
   `put-function-event-invoke-config` **replaces** it, resetting retry attempts
   and dropping any on-failure or on-success destinations:
   ```bash
   EVENT_CFG=$(mktemp)
   aws lambda get-function-event-invoke-config \
     --function-name rabbitmiles-match-activity-trail > "$EVENT_CFG"   # errors if none exists yet
   aws lambda update-function-event-invoke-config \
     --function-name rabbitmiles-match-activity-trail --maximum-event-age-in-seconds 900
   # if none existed, use put-function-event-invoke-config instead
   ```

**Pausing.** Stop between chunks, never mid-chunk. If the next chunk was
already reset when you stopped, it depends on whether it was queued:

- **Reset but not queued:** its rows still have their old values. Set
  `last_matched = NOW()` **only on rows `WHERE last_matched IS NULL AND id
  BETWEEN :lo AND :hi`**, so nothing picks them up while you're away.
- **Already queued:** some rows are re-matched or in flight. Don't stamp them.
  Wait for the quiet checks above, then stamp any rows still NULL in that
  range, as in the first case.

Either way, treat that chunk as **unfinished**: record its range, run steps 6–8
for the chunks that did finish, and resume by **re-running that chunk from the
reset** rather than starting after it.

## 6. Keep only higher values

**First, record the post-match value** (`id`, new `distance_on_trail`,
`time_on_trail`) of every activity you're about to restore. The restore
overwrites it, and step 9's check for masked match failures needs it.

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
(249.8 mi) would have dropped.

**Don't blanket-restore every drop.** Some drops are real: trail segments
removed or rerouted, or a matcher fix that stops over-counting. Restoring those
would keep miles for trail that no longer exists. Classify each drop using
step 2's local results, which score the *same stored polyline* with the
*current* code against both the current and the candidate trail data:

| Local current-data result | Local candidate-data result | Cause | Action |
|---|---|---|---|
| below baseline | about the same as current | Polyline downgrade or an older baseline, not this change | **Restore** the baseline |
| at or near baseline | below current | This trail change (segment removed or rerouted) | **Keep** the new value |

If the run is for a **matcher change** that's *meant* to lower values (for
example, a tighter tolerance), the first row is expected too. Decide
explicitly whether to restore, and say so in the run notes.

Keep every increase.

Keep the list of restored IDs. Their leaderboard buckets were already rewritten
with the lower values by the matcher, so step 7 needs to cover them.

**Re-check right before step 7:** re-run the comparison and confirm that
**0** activities are below the value step 6 left them at (the baseline for
restored rows; the new value for drops you deliberately kept). If any are, a
late match overwrote them. Fix them again, wait for another quiet period, and
re-check.

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
`recompute_for_activity` always recomputes one activity's week, month and
year together, so deduplicate by **(athlete_id, week key, month key, year
key)**. Keep one representative activity per group, with its timezones, since
many restored activities share all three. In November 2026, about 3,200 buckets took a few minutes with 12
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
  This uses the post-match values you recorded at the start of step 6.
- Rows noted as **not re-scored** in step 5.3 are listed in the run notes,
  with their cause.
- Pre-season buckets match activities too: for windows before the season,
  compare `leaderboard_agg` per **(athlete, window key, activity_type)**
  against `SUM(distance_on_trail)`, using the same opt-in join and type
  mapping as `REBUILD_SELECT` (`all`; `foot` = Run/Walk; `bike` = Ride, with
  `show_on_leaderboards = true`). A plain per-athlete sum will report false
  mismatches. The rebuild doesn't touch these windows, so step 7 is what fixes
  them.
- Leaderboard matches activities: compare `leaderboard_agg` against the
  rebuild's `REBUILD_SELECT` (in
  `backend/admin_recalculate_leaderboard/lambda_function.py`) for missing and
  differing buckets. Both counts should be 0. Also check that week, month and
  year totals agree.
- Per-athlete report: baseline vs. current trail miles. Anyone lower should be explained by drops step 6 deliberately kept (trail removals or reroutes, or an intended matcher change). Anything else is a late overwrite or a failed match.
  Share it privately, because the repo is public.

## Clean up

- Re-enable any EventBridge rules you disabled in step 4.
- Restore `fetch_activities`' environment (and `webhook_processor`'s, if you
  changed it) from the saved file, which puts
  `MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN` back. Then queue one batch-matcher
  run so the activities fetched during the run get matched.
- If you shortened `MaximumEventAgeInSeconds` on the matcher, restore the saved
  config with `update-function-event-invoke-config` using the saved values.
  Use `delete-function-event-invoke-config` only if no config existed before
  the run.
- Refresh the **frontend** copies `public/main.geojson` and
  `public/spurs.geojson` from the published files. The activity detail page
  (`src/utils/trailMatching.js`) loads them for on-trail highlighting, so
  stale copies make the map disagree with the backend's `distance_on_trail`.
- Refresh the repo's reference copies in `trail/` from the published files.
  Nothing reads them, but they're the baseline for the next run's step 2.
- Delete the saved Lambda environments (`$FETCH_ENV`, and `webhook_processor`'s
  if saved) and `$EVENT_CFG`. The environments contain secrets.
- Delete the local snapshot, polylines and any scripts that embed the DB ARNs.
