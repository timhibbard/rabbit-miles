# match_unmatched_activities Lambda Function

This Lambda function finds activities in the database where `last_matched IS NULL` and triggers trail matching for them. It's used for backfilling existing activities and catching any activities that were missed during webhook processing.

## Purpose

- Identifies activities that haven't been matched against trail data
- Triggers the `match_activity_trail` Lambda for each unmatched activity
- Processes activities in batches to avoid overwhelming the system
- **Defaults to processing 75 activities per invocation** (configurable via event payload)

## Use Cases

1. **Initial Backfill**: After deploying trail matching, process all existing activities
2. **Scheduled Cleanup**: Run daily/weekly to catch any activities missed by webhooks
3. **Manual Trigger**: Admin can invoke manually if needed

## Invocation

### Manual Invocation (Default: 75 activities)
```bash
aws lambda invoke \
  --function-name match_unmatched_activities \
  --invocation-type Event \
  output.json
```

### Manual Invocation with Custom Limit
```bash
# Process 150 activities
aws lambda invoke \
  --function-name match_unmatched_activities \
  --invocation-type Event \
  --payload '{"limit": 150}' \
  output.json

# Process 25 activities
aws lambda invoke \
  --function-name match_unmatched_activities \
  --invocation-type Event \
  --payload '{"limit": 25}' \
  output.json
```

### Scheduled via EventBridge
```json
{
  "schedule": "rate(1 day)",
  "rule": "daily-match-unmatched-activities"
}
```

## Environment Variables

Required:
- `DB_CLUSTER_ARN`: Aurora PostgreSQL cluster ARN
- `DB_SECRET_ARN`: Database credentials secret ARN
- `DB_NAME`: Database name (default: postgres)
- `MATCH_ACTIVITY_LAMBDA_ARN`: ARN of match_activity_trail Lambda function

## Batch Processing

- Processes **75 activities per invocation** by default
- Can be customized by passing a `limit` parameter in the event payload
- Uses async Lambda invocation to trigger matching
- Each activity is matched independently
- Can be invoked multiple times for large backlogs

## Response Format

```json
{
  "message": "Queued matching for 8 activities (async - check database for actual results)",
  "total_found": 10,
  "queued": 8,
  "failed_to_queue": 2
}
```

**Important**: The response indicates that invocations were successfully **queued**, not that matching has completed. Because this Lambda uses async invocation (`InvocationType='Event'`), the actual matching happens in the background. To verify actual results, query the database for activities where `last_matched` has been updated.

## Algorithm

1. Query database for activities where `last_matched IS NULL`
2. Order by `start_date DESC` (newest first)
3. Limit to specified batch size (default: 75, configurable via event payload)
4. For each activity:
   - Invoke `match_activity_trail` Lambda asynchronously
   - Track success/failure count
5. Return summary

## Deployment

```bash
# Create deployment package
cd backend/match_unmatched_activities
zip -r function.zip lambda_function.py

# Deploy to AWS Lambda
aws lambda update-function-code \
  --function-name match_unmatched_activities \
  --zip-file fileb://function.zip

# Set environment variables
aws lambda update-function-configuration \
  --function-name match_unmatched_activities \
  --environment Variables={
    DB_CLUSTER_ARN=arn:aws:rds:us-east-1:...,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:...,
    DB_NAME=postgres,
    MATCH_ACTIVITY_LAMBDA_ARN=arn:aws:lambda:us-east-1:...:function:match_activity_trail
  }
```

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:us-east-1:ACCOUNT:cluster:CLUSTER_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:SECRET_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:match_activity_trail"
    }
  ]
}
```

## Monitoring

Check CloudWatch Logs for:
- Number of unmatched activities found
- Success/failure rates for Lambda invocations being **queued** (not completion)
- Any errors during processing

**To verify actual matching results:**
- Query the database: `SELECT COUNT(*) FROM activities WHERE last_matched IS NOT NULL`
- Check CloudWatch Logs for `match_activity_trail` Lambda to see actual matching results
- Look for activities where `last_matched` timestamp was recently updated

## Batch Size Tuning

The default batch size is 75 activities per invocation. You can customize this in two ways:

### Option 1: Event Payload (Recommended)
Pass a `limit` parameter when invoking the Lambda:

```bash
# Process 200 activities
aws lambda invoke \
  --function-name match_unmatched_activities \
  --invocation-type Event \
  --payload '{"limit": 200}' \
  output.json
```

### Option 2: Code Modification
To permanently change the default, modify `DEFAULT_BATCH_SIZE` in the code:

```python
# Increase default batch size for faster backfilling
DEFAULT_BATCH_SIZE = 100  # Default is 75
```

Consider Lambda timeout and concurrent execution limits when increasing batch size.

## For Large Backlogs

If you have thousands of unmatched activities:

1. Increase Lambda timeout (max 15 minutes)
2. Pass a custom limit to process more activities per invocation:
   ```bash
   aws lambda invoke \
     --function-name match_unmatched_activities \
     --invocation-type Event \
     --payload '{"limit": 200}' \
     output.json
   ```
3. Invoke multiple times in parallel
4. Use Step Functions for orchestration

Example Step Functions workflow:
```json
{
  "Comment": "Process all unmatched activities",
  "StartAt": "ProcessBatch",
  "States": {
    "ProcessBatch": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:match_unmatched_activities",
      "Next": "CheckIfMore",
      "Retry": [{
        "ErrorEquals": ["States.ALL"],
        "MaxAttempts": 3
      }]
    },
    "CheckIfMore": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.total_found",
        "NumericGreaterThan": 0,
        "Next": "Wait"
      }],
      "Default": "Done"
    },
    "Wait": {
      "Type": "Wait",
      "Seconds": 2,
      "Next": "ProcessBatch"
    },
    "Done": {
      "Type": "Succeed"
    }
  }
}
```

## Scheduling Recommendations

- **Initial deployment**: Invoke manually with high limit (e.g., 200+) for backfilling
  - Note: Test with incrementally larger limits (100, 200, 300) to ensure Lambda doesn't timeout
  - Consider Lambda timeout (default: 3 seconds, max: 15 minutes) when choosing limit
- **Ongoing**: Schedule once daily with default limit (75) to catch missed activities
- **After webhook issues**: Invoke manually with custom limit to recover

## Error Handling

- Individual Lambda invocation failures are logged but don't stop processing
- Database query errors return 500 status
- Missing environment variables return 500 status
- Continues processing even if some invocations fail
