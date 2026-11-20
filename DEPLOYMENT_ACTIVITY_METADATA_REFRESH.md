# Deployment: Activity Metadata Refresh

Covers the fix for stale `athlete_count` (group badges never appearing) and for
activity renames/re-types that were never reconciled after a missed webhook.

**Deploy order:** run step 1 (the migration) before step 2 (the Lambda deploy) so the
refresh sweep is live the first time the hourly schedule fires. Getting it backwards
is safe, not just survivable — `get_users_needing_poll()` detects the missing column,
logs `has migration 016 run?`, and degrades to exactly the previous
webhook-freshness-only behaviour (*not* to "poll everyone", which would have
multiplied Strava read usage). The sweep simply does not start until the column
exists.

---

## Step 1 — Run migration 016 (do this first)

Adds `users.last_metadata_refresh_at`. Idempotent (`ADD COLUMN IF NOT EXISTS`), so
re-running is harmless.

The RDS Data API runs **one statement per call** (`Multistatements aren't
supported`), and this migration has three (`ALTER TABLE`, `CREATE INDEX`,
`COMMENT`). Strip the comment lines and run each statement separately:

```bash
grep -v '^[[:space:]]*--' backend/migrations/016_add_last_metadata_refresh.sql \
  | tr '\n' ' ' | tr ';' '\n' \
  | while read -r stmt; do
      [ -n "$stmt" ] || continue
      echo "Running: ${stmt:0:60}..."
      aws rds-data execute-statement \
        --resource-arn "$DB_CLUSTER_ARN" \
        --secret-arn "$DB_SECRET_ARN" \
        --database postgres \
        --sql "$stmt" < /dev/null || break
    done
```

(The `;` split is safe here because none of 016's string literals contain a
semicolon. Alternatively, run the file with `psql -f`, which handles multiple
statements natively.)

Verify the column exists:

```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database postgres \
  --sql "SELECT column_name FROM information_schema.columns
         WHERE table_name='users' AND column_name='last_metadata_refresh_at'"
```

Expect one row back. An empty result means the migration did not apply — stop and
fix that before merging, otherwise step 3's verification will show no sweep activity.

---

## Step 2 — Deploy the Lambdas

Merging this PR to `main` triggers `.github/workflows/deploy-lambdas.yml`
(it fires on any push touching `backend/**`) and deploys all seven changed functions.
No new GitHub secrets, IAM changes, env vars, or EventBridge changes are needed —
the existing `scheduled-activity-update-hourly` rule is reused as-is.

Functions changed by this PR:

| Lambda | Change |
| --- | --- |
| `webhook_processor` | Now writes `athlete_count` (was silently omitted) |
| `scheduled_activity_update` | 7-day window; sweeps all users; stamps `last_metadata_refresh_at` |
| `user_update_activities` | Paginates all pages instead of page 1 only |
| `fetch_activities` | Polyline downgrade fix |
| `update_activities` | Polyline downgrade fix for list refreshes; single-activity (detail) refreshes now replace the stored polyline |
| `admin_update_activities` | Polyline downgrade fix; paginates all pages instead of page 1 only |
| `admin_backfill_activities` | Polyline downgrade fix |

Confirm all seven matrix jobs went green in the Actions run before moving on.

---

## Step 3 — Verify the sweep is running

Wait for the next hourly EventBridge fire (or invoke manually):

```bash
aws lambda invoke \
  --function-name "$LAMBDA_SCHEDULED_ACTIVITY_UPDATE" \
  --payload '{}' response.json && cat response.json
```

In CloudWatch Logs for that function, look for:

- `Found N users due for a refresh sweep`. On the first run after the migration,
  `N` should equal your **total** connected user count, since no one has been
  swept yet. After that each user comes due once every 6 hours, so expect about
  `total / 6` per hourly run.
- `Rate limit usage: X/300` — confirm this stays well under 300.
- Absence of `page full (...) were NOT refreshed` warnings. If you see one, a user
  has more than 200 activities inside the 7-day window and the tail was skipped.

Then confirm the stamps are landing:

```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database postgres \
  --sql "SELECT count(*) AS total,
                count(last_metadata_refresh_at) AS swept
         FROM users WHERE access_token IS NOT NULL"
```

`swept` should reach `total` within a few minutes of the first scheduled run.
Each invocation processes users until it hits 25 users or its time budget
(timeout minus a 90 s safety margin; about 18 users with the 123 s timeout),
then self-invokes for the rest. The remainder is deferred to the next hourly
run instead on a Strava rate limit, when the sweep has used half of the
current 15-minute read window, on a time stop before any user was processed,
or if self-invocation fails. That last case is logged at ERROR and is usually
a missing `lambda:InvokeFunction` grant on the function's own ARN; see
`backend/scheduled_activity_update/README.md`.

---

## Step 4 — One-time repair of rows older than 7 days

The sweep only reconciles the last 7 days. Activities older than that keep whatever
`athlete_count` they were first written with, so they need one backfill pass.

**Use `admin_update_activities` (or the user-facing "Update activities" button), not
`backfill_athlete_count`.** Both paths read Strava's *list* endpoint, and both now
paginate through the whole season: one request covers 200 activities, up to 10 pages
(2,000 activities) per call. `backfill_athlete_count` reads the *detail* endpoint
once per activity: 100 requests to fix 100 activities, which burns a third of the
daily read quota per user and has no rate-limit handling. It remains in the repo for
targeted single-activity investigation only.

Check what actually needs repair first:

```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database postgres \
  --sql "SELECT count(*) FROM activities
         WHERE start_date < now() - interval '7 days'
           AND (athlete_count IS NULL OR athlete_count = 1)"
```

That count is an upper bound, not a to-do list — most of those really are solo
activities. Then trigger the repair per athlete via the admin endpoint, and re-run
the query to see the count drop.

Because both endpoints now paginate, one call repairs an athlete's whole season
rather than only their most recent 200 activities. If an athlete has more than 2,000
activities in range, the call stops at the `MAX_PAGES` limit and returns
`truncated: true` with an explanatory `message`. The Settings and Admin pages show
this as a partial-update warning. Calling again does **not** continue from where it
stopped: it re-reads the newest 2,000. No athlete is near that limit today (the
season maximum is about 1,100), so there is no resume cursor. Add one if that changes.

Paginating makes the admin endpoint slower for high-activity athletes (up to 10 list
requests plus one DB write per activity). Before running the repair, check that
`admin_update_activities` has at least the same Lambda timeout as
`user_update_activities`.

---

## Rollback

Revert the merge commit and let `deploy-lambdas.yml` redeploy. **Leave the column in
place** — it is additive, nothing outside `scheduled_activity_update` reads it, and
dropping it is pure risk. The reverted code simply stops writing to it.

There is no data to undo: every change either writes a previously-unwritten field or
makes an existing write more conservative.

---

## What this does not fix

Called out so it does not read as covered:

- **Changing an activity's `type` can change leaderboard eligibility, and no
  leaderboard recompute is triggered.** The refresh updates `activities.type`, but
  `leaderboard_agg` is only recomputed by trail matching and the webhook delete path.
  A Run re-typed as a Ride keeps its leaderboard contribution until something else
  forces a recompute. Pre-existing, and worth a follow-up.
- **Strava athlete deauthorization is still ignored.** `webhook/lambda_function.py`
  drops any event where `object_type != "activity"`, so an `athlete` event carrying
  `updates: {authorized: "false"}` is discarded and the user stays marked connected
  until a token refresh fails. Pre-existing, unrelated to this PR.
- **Activities before Jan 1 2026** are out of range everywhere via
  `ACTIVITIES_START_DATE`. Unchanged by this PR.
