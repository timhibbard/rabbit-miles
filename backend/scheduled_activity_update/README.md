# Scheduled Activity Update Lambda

This Lambda runs every hour and serves two purposes with a single Strava request per user:

1. **Webhook backstop** — picks up activities for users whose webhooks have not delivered in over 6 hours.
2. **Metadata refresh sweep** — re-reads a 7-day window for *every* connected user at least once every 6 hours.

## Purpose

Strava keeps mutating activities after upload, and not all of it generates a webhook we can rely on:

- `athlete_count` grows as the *other* participants upload their copy of a group activity — minutes to days after the fact. This is why a value written once at ingest is wrong so often.
- Athletes rename activities and change their type long after uploading.

Webhooks cover most of this, but a webhook that is missed (subscription lapse, DLQ, rate-limit deferral) previously left the row stale forever: the hourly poll only looked back 24 hours *and* skipped any user whose webhooks were flowing. That excluded the most active users from all reconciliation. The refresh sweep closes that gap.

## Functionality

1. Selects connected users that are **due** — either webhook-stale (>6h) or sweep-due (`last_metadata_refresh_at` older than 6h, or never). Ordered oldest-sweep-first so a backlog drains fairly instead of always serving the lowest athlete IDs.
2. For each user:
   - Refreshes the Strava access token if needed
   - Fetches activities from the last 7 days (one list request)
   - Updates or inserts activities, refreshing `name`, `type`, `athlete_count`, distance and time fields
   - Preserves trail matching data (`time_on_trail`, `distance_on_trail`) via COALESCE
   - Preserves any full `polyline` already stored by `webhook_processor` — the list endpoint only returns `summary_polyline`, so assigning it directly would downgrade the stored route
   - Refreshes the profile picture if it is older than 7 days
   - Stamps `last_metadata_refresh_at` on success only, so a failure is retried on the next run instead of waiting out a full sweep interval
3. Returns a summary of updates performed

## Rate limit budget

Strava allows 300 read requests per 15 minutes and 3,000 per day. The sweep costs **1 read request per user per 6 hours** — 4 per user per day — which stays inside the daily read quota up to roughly 700 connected users. Widening the lookback window from 24 hours to 7 days costs nothing extra: it is the same single list request either way.

If you outgrow that, raise `METADATA_REFRESH_SECONDS` (sweep less often) rather than shrinking the window.

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
- Requires migration `016_add_last_metadata_refresh.sql`. Before it runs, `get_users_needing_poll()` falls back to selecting all connected users and the sweep clause is inert — the Lambda still works, it just behaves as it did before this change
- A single page (200 activities) is the cap per user per run. If a user somehow exceeds that inside the window, a `WARNING` is logged naming the unrefreshed tail rather than silently truncating
- Only reconciles the **last 7 days**. Repairing older rows is a one-time job — see `DEPLOYMENT_ACTIVITY_METADATA_REFRESH.md`
