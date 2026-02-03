# Trail Matching Deployment Guide

This guide walks through deploying the new trail matching Lambda functions to AWS.

## Prerequisites

- AWS CLI configured with appropriate credentials
- S3 bucket `rabbitmiles-trail-data` with trail GeoJSON files
- Existing Lambda functions and database already deployed
- Database migrations 004 and 005 applied (for trail columns)

## Deployment Steps

### 1. Deploy match_activity_trail Lambda

```bash
cd backend/match_activity_trail

# Create deployment package
zip -r function.zip lambda_function.py

# Create Lambda function (first time only)
aws lambda create-function \
  --function-name match_activity_trail \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables={
    DB_CLUSTER_ARN=arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:CLUSTER_NAME,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:SECRET_NAME,
    DB_NAME=postgres,
    TRAIL_DATA_BUCKET=rabbitmiles-trail-data
  }

# OR update existing function
aws lambda update-function-code \
  --function-name match_activity_trail \
  --zip-file fileb://function.zip
```

### 2. Deploy match_unmatched_activities Lambda

```bash
cd backend/match_unmatched_activities

# Create deployment package
zip -r function.zip lambda_function.py

# Get the ARN of match_activity_trail Lambda
MATCH_LAMBDA_ARN=$(aws lambda get-function \
  --function-name match_activity_trail \
  --query 'Configuration.FunctionArn' \
  --output text)

# Create Lambda function (first time only)
aws lambda create-function \
  --function-name match_unmatched_activities \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip \
  --timeout 300 \
  --memory-size 256 \
  --environment Variables={
    DB_CLUSTER_ARN=arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:CLUSTER_NAME,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:SECRET_NAME,
    DB_NAME=postgres,
    MATCH_ACTIVITY_LAMBDA_ARN=$MATCH_LAMBDA_ARN
  }

# OR update existing function
aws lambda update-function-code \
  --function-name match_unmatched_activities \
  --zip-file fileb://function.zip
```

### 3. Update webhook_processor Lambda

The webhook_processor has been modified to trigger trail matching. Update it:

```bash
cd backend/webhook_processor

# Create deployment package
zip -r function.zip lambda_function.py

# Get the ARN of match_activity_trail Lambda
MATCH_LAMBDA_ARN=$(aws lambda get-function \
  --function-name match_activity_trail \
  --query 'Configuration.FunctionArn' \
  --output text)

# Update function code
aws lambda update-function-code \
  --function-name webhook_processor \
  --zip-file fileb://function.zip

# Update environment variables to include MATCH_ACTIVITY_LAMBDA_ARN
aws lambda update-function-configuration \
  --function-name webhook_processor \
  --environment Variables={
    DB_CLUSTER_ARN=arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:CLUSTER_NAME,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:SECRET_NAME,
    DB_NAME=postgres,
    STRAVA_CLIENT_ID=YOUR_CLIENT_ID,
    STRAVA_CLIENT_SECRET=YOUR_CLIENT_SECRET,
    MATCH_ACTIVITY_LAMBDA_ARN=$MATCH_LAMBDA_ARN
  }
```

### 4. Update IAM Permissions

Add necessary permissions for the Lambda functions:

#### match_activity_trail Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:CLUSTER_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:SECRET_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::rabbitmiles-trail-data/trails/*"
    }
  ]
}
```

#### match_unmatched_activities Permissions

Add Lambda invoke permission:

```json
{
  "Effect": "Allow",
  "Action": [
    "lambda:InvokeFunction"
  ],
  "Resource": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:match_activity_trail"
}
```

#### webhook_processor Permissions

Add Lambda invoke permission:

```json
{
  "Effect": "Allow",
  "Action": [
    "lambda:InvokeFunction"
  ],
  "Resource": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:match_activity_trail"
}
```

### 5. Deploy Frontend Changes

The Dashboard component has been updated to display trail metrics. Deploy the frontend:

```bash
# Build frontend
npm run build

# Deploy to GitHub Pages
npm run deploy

# OR manually
git push origin main
```

## Initial Backfill

After deployment, backfill existing activities:

```bash
# Test with a single activity first
aws lambda invoke \
  --function-name match_activity_trail \
  --payload '{"activity_id": 123}' \
  output.json

cat output.json

# If successful, backfill all unmatched activities
# This may need to be run multiple times if you have > 10 unmatched activities
aws lambda invoke \
  --function-name match_unmatched_activities \
  --invocation-type Event \
  output.json
```

## Verification

### 1. Check Lambda Logs

```bash
# Check match_activity_trail logs
aws logs tail /aws/lambda/match_activity_trail --follow

# Check match_unmatched_activities logs
aws logs tail /aws/lambda/match_unmatched_activities --follow

# Check webhook_processor logs
aws logs tail /aws/lambda/webhook_processor --follow
```

### 2. Query Database

```sql
-- Check activities with trail metrics
SELECT 
  id, 
  name, 
  distance, 
  distance_on_trail,
  time_on_trail,
  last_matched
FROM activities 
WHERE last_matched IS NOT NULL
LIMIT 10;

-- Count unmatched activities
SELECT COUNT(*) FROM activities WHERE last_matched IS NULL;
```

### 3. Test Frontend

1. Open the dashboard in your browser
2. Verify activities show trail metrics (green text below distance/duration)
3. Add a new Strava activity and verify it gets matched automatically
4. Check that the trail metrics appear after ~30 seconds (auto-refresh interval)

## Schedule Cleanup (Optional)

Set up a daily schedule to catch any missed activities:

```bash
# Create EventBridge rule
aws events put-rule \
  --name daily-match-unmatched-activities \
  --schedule-expression "rate(1 day)"

# Add Lambda as target
aws events put-targets \
  --rule daily-match-unmatched-activities \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:match_unmatched_activities"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name match_unmatched_activities \
  --statement-id daily-match-unmatched-activities \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/daily-match-unmatched-activities
```

## Troubleshooting

### Activities not getting matched

1. Check webhook_processor logs for trail matching invocation
2. Verify MATCH_ACTIVITY_LAMBDA_ARN is set correctly
3. Check IAM permissions for Lambda invoke
4. Manually invoke match_activity_trail with a specific activity_id

### Incorrect trail metrics

1. Verify trail data is up-to-date in S3
2. Check tolerance value (50m) is appropriate
3. Review polyline data quality from Strava
4. Check CloudWatch logs for calculation details

### High Lambda costs

1. Consider caching trail data in /tmp
2. Reduce batch size in match_unmatched_activities
3. Adjust scheduled cleanup frequency
4. Use reserved concurrency to limit costs

## Rollback

If issues occur, rollback changes:

```bash
# Revert webhook_processor to previous version
aws lambda update-function-code \
  --function-name webhook_processor \
  --s3-bucket your-backup-bucket \
  --s3-key webhook_processor-previous.zip

# Or remove MATCH_ACTIVITY_LAMBDA_ARN to disable trail matching
aws lambda update-function-configuration \
  --function-name webhook_processor \
  --environment Variables={...without MATCH_ACTIVITY_LAMBDA_ARN...}

# Delete new Lambda functions (if needed)
aws lambda delete-function --function-name match_activity_trail
aws lambda delete-function --function-name match_unmatched_activities
```

## Monitoring

Key metrics to monitor:

- Lambda invocation count
- Lambda error rate
- Lambda duration
- Database query performance
- S3 GET requests
- Activities with `last_matched` vs without

Set up CloudWatch alarms for:
- Lambda errors > 5% 
- Lambda duration > 200s
- Lambda throttles > 0
