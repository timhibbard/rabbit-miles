# Scheduled Activity Update Lambda

This Lambda runs every hour and sweeps *every* connected user once every 6 hours, re-reading a 7-day window with a single Strava list request per user. That one sweep serves two purposes:

1. **Webhook backstop** — anything a missed webhook dropped is picked up within one sweep interval (≤ 6 hours).
2. **Metadata reconciliation** — refreshes fields Strava changes after upload.

The hourly schedule only spreads users across runs and retries failures. No user is polled more than once per sweep interval.

## Purpose

Strava keeps mutating activities after upload, and not all of it generates a webhook we can rely on:

- `athlete_count` grows as the *other* participants upload their copy of a group activity — minutes to days after the fact. This is why a value written once at ingest is wrong so often.
- Athletes rename activities and change their type long after uploading.

Webhooks cover most of this, but a webhook that is missed (subscription lapse, DLQ, rate-limit deferral) previously left the row stale forever: the hourly poll only looked back 24 hours *and* skipped any user whose webhooks were flowing. That excluded the most active users from all reconciliation. The refresh sweep closes that gap.

## Functionality

1. Selects connected users that are **due**: `last_metadata_refresh_at` older than 6h, or never set. Webhook freshness is ignored. (Previously, "webhook-stale" users, meaning anyone who hadn't uploaded in 6h, were polled every hour, which was most users 24x/day.) Ordered oldest-sweep-first so a backlog drains fairly instead of always serving the lowest athlete IDs.
2. For each user:
   - Refreshes the Strava access token if needed
   - Fetches activities from the last 7 days (one list request)
   - Updates or inserts activities, refreshing `name`, `type`, `athlete_count`, distance and time fields
   - Preserves trail matching data (`time_on_trail`, `distance_on_trail`) via COALESCE
   - Preserves any full `polyline` already stored by `webhook_processor` — the list endpoint only returns `summary_polyline`, so assigning it directly would downgrade the stored route
   - Refreshes the profile picture if it is older than 7 days
   - Stamps `last_metadata_refresh_at` only when every activity write succeeded, so a failure (including a single failed row) is retried on the next hourly run instead of waiting out a full sweep interval
3. Returns a summary of updates performed

## Rate limit budget

Strava allows 300 read requests per 15 minutes and 3,000 per day. The sweep costs **1 read request per user per 6 hours**, which is 4 per user per day. That's the whole scheduled cost, because no user is polled more often than that. It stays inside the daily read quota up to roughly 700 connected users, minus whatever webhook detail fetches use. Profile-picture refreshes add at most 1 read per user per 7 days, and a user whose writes are failing is retried hourly until a clean pass. Widening the lookback window from 24 hours to 7 days costs nothing extra: it is the same single list request either way.

For comparison, the previous hourly backstop polled every webhook-stale user each hour. In Nov 2026 that was 57 of 84 users, about 1,370 reads/day.

If you outgrow that, raise `METADATA_REFRESH_SECONDS` (sweep less often) rather than shrinking the window.

## Batching and continuation

Each invocation processes at most `USERS_PER_INVOCATION` (25) users and stops
early when less than `LAMBDA_TIME_REMAINING_SAFETY_MS` (90 s) of Lambda time
remains. What happens to the rest depends on why it stopped:

- **Batch full, or out of Lambda time:** self-invoke immediately with the
  remaining athlete IDs. A fresh invocation has its full time budget.
- **Deferred to the next scheduled run** instead in these cases:
  - Strava rate limit reached (`RateLimitExhaustedError`)
  - **app-wide** Strava read usage in the current 15-minute window has reached
    `SWEEP_RATE_LIMIT_SHARE` (50%). Strava's headers count every read the app
    makes, webhooks included, so the sweep yields to busy webhook traffic
  - a time-budget stop before any user was processed, so it can't self-invoke
    in a loop
  - a time-budget stop while running a pre-migration-016 fallback selection.
    Those don't stamp users, so chaining would poll every fallback user hourly
  - self-invocation failed. This is logged at ERROR and returned as
    `continuation_failed: true`.

**Requirements and guards:**
- **IAM:** the execution role needs `lambda:InvokeFunction` on the function's
  own ARN. Without it every continuation fails and the sweep falls back to one
  batch per hourly run.
- **Recommended:** set reserved concurrency to 1
  (`aws lambda put-function-concurrency --reserved-concurrent-executions 1`). A
  continuation chain then can't overlap the next scheduled run or a manual
  invoke and fetch the same users twice. Async self-invokes that arrive while
  one is running are queued and retried, not lost.
- The Strava usage counter is tied to its 15-minute window and resets when the
  window changes, so a warm container doesn't inherit stale usage.

With the 123 s timeout, about 33 s per invocation are usable, which is about
18 users. Before continuation applied to time-budget stops, that capped each
*hourly run* at about 18 users. That was barely enough to sweep 84 users every
6 hours, and the first sweep after deploying took several hours.

## Environment Variables Required

- `DB_CLUSTER_ARN`: ARN of the Aurora Serverless cluster
- `DB_SECRET_ARN`: ARN of the RDS credentials secret
- `DB_NAME`: Database name (default: postgres)
- `STRAVA_CLIENT_ID`: Strava OAuth client ID
- `STRAVA_CLIENT_SECRET`: Strava OAuth client secret (or use STRAVA_SECRET_ARN)
- `STRAVA_SECRET_ARN`: Optional - ARN of secret containing Strava credentials

## Deployment

Both the Lambda function and EventBridge schedule are automatically deployed via GitHub Actions when code is pushed to the `main` branch.

### Required GitHub Secrets

```bash
LAMBDA_SCHEDULED_ACTIVITY_UPDATE=<lambda-function-name>
AWS_ACCESS_KEY_ID=<your-aws-access-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret-key>
AWS_REGION=<your-aws-region>
```

### What Gets Deployed

1. **Lambda Function** - Deployed by `.github/workflows/deploy-lambdas.yml`
2. **EventBridge Schedule** - Configured by `.github/workflows/deploy-eventbridge-schedule.yml`
   - Rule name: `scheduled-activity-update-hourly`
   - Schedule: `rate(1 hour)`
   - Target: The Lambda function specified in `LAMBDA_SCHEDULED_ACTIVITY_UPDATE`
   - Permissions: Automatically grants EventBridge permission to invoke the Lambda

### Manual Deployment (Optional)

If you need to manually configure the EventBridge schedule, you can use the AWS Console or CLI:

**Using AWS Console:**

1. Navigate to Amazon EventBridge → Rules
2. Click "Create rule"
3. Rule details:
   - Name: `scheduled-activity-update-hourly`
   - Description: "Updates activities from Strava every hour"
   - Event bus: `default`
4. Rule type: Schedule
5. Schedule pattern: Rate-based schedule
   - Rate expression: `rate(1 hour)`
6. Select targets:
   - Target types: AWS service
   - Select a target: Lambda function
   - Function: Select your `scheduled_activity_update` Lambda
7. Create rule

**Using AWS CLI:**

```bash
# Create EventBridge rule
aws events put-rule \
  --name scheduled-activity-update-hourly \
  --description "Updates activities from Strava every hour" \
  --schedule-expression "rate(1 hour)" \
  --region us-east-1

# Add Lambda as target
aws events put-targets \
  --rule scheduled-activity-update-hourly \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:LAMBDA_NAME" \
  --region us-east-1

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name LAMBDA_NAME \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/scheduled-activity-update-hourly \
  --region us-east-1
```

Replace `ACCOUNT_ID` and `LAMBDA_NAME` with your values.

## Testing

You can manually invoke the Lambda to test it:

```bash
aws lambda invoke \
  --function-name LAMBDA_NAME \
  --payload '{}' \
  response.json

cat response.json
```

## Response Format

```json
{
  "statusCode": 200,
  "body": {
    "message": "Scheduled activity update completed",
    "total_users": 5,
    "successful_updates": 5,
    "failed_updates": 0,
    "total_activities_stored": 23,
    "results": [
      {
        "athlete_id": 123456,
        "success": true,
        "total_activities": 5,
        "stored": 5,
        "failed": 0
      }
    ]
  }
}
```

## Monitoring

Monitor Lambda execution in:
- CloudWatch Logs: `/aws/lambda/LAMBDA_NAME`
- CloudWatch Metrics: Invocations, Errors, Duration
- EventBridge Metrics: Failed invocations

## Notes

- The Lambda fetches activities after timestamp: `max(ACTIVITIES_START_DATE, current_time - 7d)`
- ACTIVITIES_START_DATE is Jan 1, 2026 (timestamp: 1767225600)
- Updates preserve existing trail matching data using COALESCE
- Access tokens are automatically refreshed if within 5 minutes of expiry
- The Lambda processes users sequentially (not in parallel) to avoid rate limits
- Requires migration `016_add_last_metadata_refresh.sql`. Before it runs, `get_users_needing_poll()` logs `has migration 016 run?` and falls back to the previous webhook-freshness selection (users with no webhook in 6h, polled hourly). It does *not* poll everyone, which would multiply Strava read usage. Only if that query also fails (pre-011/015) does it select all connected users. The sweep doesn't start, and `last_metadata_refresh_at` isn't stamped, until the column exists.
- A single page (200 activities) is the cap per user per run. If a user somehow exceeds that inside the window, a `WARNING` is logged naming the unrefreshed tail rather than silently truncating
- Only reconciles the **last 7 days**. Repairing older rows is a one-time job — see `DEPLOYMENT_ACTIVITY_METADATA_REFRESH.md`
