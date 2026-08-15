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

```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database postgres \
  --sql "$(cat backend/migrations/016_add_last_metadata_refresh.sql)"
```

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
| `update_activities` | Polyline downgrade fix |
| `admin_update_activities` | Polyline downgrade fix |
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

- `Found N users to poll (webhook-stale or refresh-sweep due)` — on the first run
  after the migration, `N` should equal your **total** connected user count, since
  no one has been swept yet. On later runs it settles to whoever is due.
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

`swept` should climb toward `total` over the first few hours. Users are processed
25 per invocation with self-continuation, so a large user base takes a few runs.

---

## Step 4 — One-time repair of rows older than 7 days

The sweep only reconciles the last 7 days. Activities older than that keep whatever
`athlete_count` they were first written with, so they need one backfill pass.

**Use `admin_update_activities` (or the user-facing "Update activities" button), not
`backfill_athlete_count`.** The admin/user paths read Strava's *list* endpoint — one
request covers 200 activities. `backfill_athlete_count` reads the *detail* endpoint
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

Because `user_update_activities` now paginates, a user pressing "Update activities"
repairs their whole season rather than only their most recent 200 activities. If a
user has more than 2,000 activities in range it stops at the `MAX_PAGES` limit and
says so in the response `message`, with `truncated: true` — press it again to continue.

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
