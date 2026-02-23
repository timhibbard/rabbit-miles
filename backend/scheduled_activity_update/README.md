# Scheduled Activity Update Lambda

This Lambda function runs on a schedule (every hour) to automatically update activities from the last 24 hours for all connected users from the Strava API.

## Purpose

Ensures that activity data (including `athlete_count` for group activities) is kept up-to-date automatically without requiring manual user intervention.

## Functionality

1. Queries database for all users with valid Strava tokens
2. For each user:
   - Refreshes Strava access token if needed
   - Fetches activities from the last 24 hours from Strava API
   - Updates or inserts activities in the database
   - Preserves existing trail matching data (time_on_trail, distance_on_trail)
3. Returns summary of updates performed

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

- The Lambda fetches activities after timestamp: `max(ACTIVITIES_START_DATE, current_time - 24h)`
- ACTIVITIES_START_DATE is Jan 1, 2026 (timestamp: 1767225600)
- Updates preserve existing trail matching data using COALESCE
- Access tokens are automatically refreshed if within 5 minutes of expiry
- The Lambda processes users sequentially (not in parallel) to avoid rate limits
