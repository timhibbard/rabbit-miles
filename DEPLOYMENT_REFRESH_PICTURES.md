# Deployment: Admin "Refresh Profile Pictures"

Adds an admin button that re-fetches every connected user's Strava profile
picture, plus a throttled auto-refresh in the hourly scheduled poll. Fixes
avatars that break when an athlete changes their Strava photo (Strava versions
its avatar URLs, so a stored URL 404s after the photo changes).

## What changed

**Frontend**
- `src/components/Avatar.jsx` — new; falls back to the 👤 placeholder when an
  image fails to load (`onError`). Used in the leaderboard.
- `src/pages/Leaderboard.jsx` — uses `<Avatar>` for both the top-3 and the table.
- `src/pages/Admin.jsx` — "Refresh Profile Pictures" button (Global Admin Actions).
- `src/utils/api.js` — `refreshProfilePictures()` → `POST /admin/refresh-pictures`.

**Backend**
- `backend/migrations/015_add_profile_picture_updated_at.sql` — tracks last refresh.
- `backend/scheduled_activity_update/lambda_function.py` — refreshes each user's
  picture at most once per 7 days while it's already processing that user.
- `backend/admin_refresh_pictures/lambda_function.py` — new admin endpoint.

## Deploy steps

1. **Run the migration** `015_add_profile_picture_updated_at.sql` against the DB.

2. **Create the Lambda** `rabbitmiles-admin-refresh-pictures`
   (handler `lambda_function.handler`, Python runtime matching the other admin
   Lambdas). Deploy code via the `deploy-lambdas.yml` workflow — it's already
   registered there with `needs_utils: true`, and needs the
   `LAMBDA_ADMIN_REFRESH_PICTURES` GitHub secret set to the function name.

3. **Set env vars** on the new Lambda (same as other admin Lambdas):
   `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME`, `APP_SECRET`, `FRONTEND_URL`,
   `ADMIN_ATHLETE_IDS`, and Strava creds (`STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET`
   or `STRAVA_SECRET_ARN`).

4. **IAM**: the execution role needs `rds-data:ExecuteStatement`,
   `secretsmanager:GetSecretValue`, and **`lambda:InvokeFunction` on itself**
   (it self-invokes asynchronously to run past API Gateway's 30s timeout).
   Not in a VPC (RDS Data API requirement).

5. **Configure timeout/memory**: `scripts/configure-admin-refresh-pictures-lambda.sh`
   (600s timeout so it can wait out a Strava rate-limit window if hit).

6. **Add the API route**: `scripts/setup-admin-refresh-pictures-route.sh`
   (creates `POST` + `OPTIONS /admin/refresh-pictures`).

7. **Deploy the frontend** build.

## Notes
- The endpoint returns `202` immediately and does the work in the background;
  progress is in CloudWatch logs for the Lambda.
- Rate-limit aware: makes one Strava read per user. If it approaches the read
  limit (300/15 min) it waits or stops cleanly — remaining users keep their
  current picture and get caught up by the next run or another click.
