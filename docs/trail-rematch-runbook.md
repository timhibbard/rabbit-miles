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

**Permissions.** You need `lambda:InvokeFunction` on those functions, plus
`rds-data:ExecuteStatement` and `secretsmanager:GetSecretValue` for the DB
cluster. Get `DB_CLUSTER_ARN`, `DB_SECRET_ARN` and `DB_NAME` from the
environment variables of any of these Lambdas.

**Data API constraints** that shape the steps below:
- Responses over **1 MB** fail. Page every read (`WHERE id > :last ORDER BY id LIMIT n`).
- **One statement per call.** Multi-statement SQL is rejected.

**Pick a quiet time.** The matcher updates leaderboard rows as it goes, and
the leaderboard recalculation is best run when nothing else is matching.

## 1. Refresh trail data

```bash
aws lambda invoke --function-name rabbitmiles-update-trail-data \
  --cli-binary-format raw-in-base64-out --payload '{}' response.json && cat response.json
```

Check the source first. The Lambda copies whatever greenvilleopenmap.info
currently publishes (`SwampRabbitWays.geojson`, `SwampRabbitConnectors.geojson`;
check `Last-Modified`). The matcher reads S3 on every invocation, so new matches
use the new data immediately. Afterwards, refresh the repo's reference copies in
`trail/` from the same URLs. Nothing reads them, but they're useful for local
diffs.

## 2. Estimate impact locally before touching production

Re-matching rewrites `distance_on_trail` for every activity, so measure first.
Download polylines (paged), run `calculate_trail_intersection` from
`backend/match_activity_trail/lambda_function.py` locally against the old and
new GeoJSON, and compare per athlete. With 8 worker processes this takes a
few minutes for about 23k activities.

Do this even for "small" trail changes. In November 2026 the trail refresh
itself changed totals by about 0 mi, but the local run exposed a matcher bug
worth about 1,700 mi
([#335](https://github.com/timhibbard/rabbit-miles/pull/335)).

## 3. Snapshot the baseline

Save `id, athlete_id, distance_on_trail, time_on_trail` for every activity to a
local CSV, paged by `id`. You need it for step 5 and for any rollback. Keep it
out of the repo, because it contains athlete data.

## 4. Re-match in chunks

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
   on large batches, and the only progress then comes from the scheduled
   matcher at about 75 activities per 3 minutes.
3. **Wait for the chunk to drain** (`SELECT COUNT(*) FROM activities WHERE last_matched IS NULL`
   reaches 0) before resetting the next chunk, so activities aren't queued twice.

Expect about 90–250 s per 400-activity chunk, or 1.5–4 hours for the full set.

**Pausing.** Stop between chunks, never mid-chunk. If a chunk was already reset
when you stopped, set `last_matched = NOW()` on its rows: their values haven't
changed yet, and otherwise the scheduled matcher picks them up while you're away
and step 5 never sees them. Then run step 5 and step 6 for what's done so far,
and resume after the last finished ID.

## 5. Keep only higher values

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
with the lower values by the matcher, so step 6 needs to cover them.

## 6. Rebuild the leaderboard

```bash
aws lambda invoke --function-name rabbitmiles-admin-recalculate-leaderboard \
  --cli-read-timeout 300 --cli-binary-format raw-in-base64-out \
  --payload '{"async_invocation": true}' out.json && cat out.json
```

This is a set-based rebuild of all in-season buckets, taking about 8 s, and it
never empties the table (see [`leaderboard-runbook.md`](leaderboard-runbook.md)).
Run it after step 5 and when no matching is in progress.

## 7. Verify

- No activity left unmatched: `SELECT COUNT(*) FROM activities WHERE last_matched IS NULL` returns 0.
- Leaderboard matches activities: compare `leaderboard_agg` against the
  rebuild's `REBUILD_SELECT` (in
  `backend/admin_recalculate_leaderboard/lambda_function.py`) for missing and
  differing buckets. Both counts should be 0. Also check that week, month and
  year totals agree.
- Per-athlete report: baseline vs. current trail miles. Nobody should be lower.
  Share it privately, because the repo is public.

## Clean up

Delete the local snapshot, polylines and any scripts that embed the DB ARNs.
