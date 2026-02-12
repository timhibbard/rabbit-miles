# Activity Update Features - Deployment Guide

This guide covers the deployment and configuration of the new activity update features.

## Overview

Three new features have been added to automatically keep activity data up-to-date from Strava:

1. **Scheduled Updates** - Automatically updates activities every 12 hours
2. **User Manual Update** - Allows users to refresh their own activities via Settings
3. **Admin Update** - Allows admins to refresh any user's activities

## Components

### Backend Lambda Functions

1. **scheduled_activity_update**
   - Purpose: Runs on schedule to update recent activities for all users
   - Trigger: EventBridge schedule (every 12 hours)
   - Endpoint: N/A (event-driven)

2. **user_update_activities**
   - Purpose: Allows authenticated users to update their own activities
   - Trigger: API Gateway
   - Endpoint: `POST /activities/update`

3. **admin_update_activities**
   - Purpose: Allows admins to update any user's activities
   - Trigger: API Gateway
   - Endpoint: `POST /admin/users/{athlete_id}/update-activities`

### Frontend Changes

- **Settings Page**: New "Refresh Activities" button
- **Admin Page**: New "Update" button for selected user

## Deployment Steps

### Step 1: Add GitHub Secrets

Add these secrets to your GitHub repository settings:

```
LAMBDA_SCHEDULED_ACTIVITY_UPDATE=<your-lambda-function-name>
LAMBDA_USER_UPDATE_ACTIVITIES=<your-lambda-function-name>
LAMBDA_ADMIN_UPDATE_ACTIVITIES=<your-lambda-function-name>
```

### Step 2: Create Lambda Functions in AWS

Either:
- **Option A**: Let GitHub Actions create them automatically on next push to `main`
- **Option B**: Create them manually using AWS Console or CLI

**Manual Creation (if needed):**

```bash
# Create scheduled_activity_update
aws lambda create-function \
  --function-name scheduled-activity-update \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip \
  --timeout 300 \
  --memory-size 256

# Create user_update_activities
aws lambda create-function \
  --function-name user-update-activities \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip \
  --timeout 60 \
  --memory-size 256

# Create admin_update_activities
aws lambda create-function \
  --function-name admin-update-activities \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip \
  --timeout 60 \
  --memory-size 256
```

### Step 3: Configure Lambda Environment Variables

All three Lambdas require these environment variables:

```bash
DB_CLUSTER_ARN=arn:aws:rds:region:account:cluster:cluster-name
DB_SECRET_ARN=arn:aws:secretsmanager:region:account:secret:secret-name
DB_NAME=postgres
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
# OR use:
# STRAVA_SECRET_ARN=arn:aws:secretsmanager:region:account:secret:secret-name
```

Additional for user and admin endpoints:
```bash
APP_SECRET=your_app_secret
FRONTEND_URL=https://rabbitmiles.com
```

Additional for admin endpoint:
```bash
ADMIN_ATHLETE_IDS=123456,789012
```

### Step 4: Configure API Gateway Routes

Add these routes to your API Gateway:

**User Endpoint:**
- Path: `POST /activities/update`
- Integration: Lambda proxy integration
- Target: `user_update_activities` Lambda
- CORS: Enabled with credentials

**Admin Endpoint:**
- Path: `POST /admin/users/{id}/update-activities`
- Integration: Lambda proxy integration
- Target: `admin_update_activities` Lambda
- CORS: Enabled with credentials

### Step 5: Create EventBridge Schedule

Create a schedule to trigger `scheduled_activity_update` Lambda every 12 hours:

**Using AWS Console:**

1. Go to Amazon EventBridge → Rules
2. Create rule:
   - Name: `scheduled-activity-update-every-12h`
   - Rule type: Schedule
   - Schedule pattern: Rate expression = `rate(12 hours)`
3. Add target:
   - Target type: Lambda function
   - Function: Select `scheduled_activity_update`
4. Create rule

**Using AWS CLI:**

```bash
# 1. Create the rule
aws events put-rule \
  --name scheduled-activity-update-every-12h \
  --description "Updates activities from Strava every 12 hours" \
  --schedule-expression "rate(12 hours)" \
  --region us-east-1

# 2. Add Lambda as target
aws events put-targets \
  --rule scheduled-activity-update-every-12h \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:scheduled-activity-update" \
  --region us-east-1

# 3. Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name scheduled-activity-update \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/scheduled-activity-update-every-12h \
  --region us-east-1
```

Replace `ACCOUNT_ID` with your AWS account ID.

### Step 6: Deploy Frontend

The frontend changes are automatically deployed via GitHub Pages on push to `main`.

## Testing

### Test Scheduled Lambda

Manually invoke the Lambda to test it:

```bash
aws lambda invoke \
  --function-name scheduled-activity-update \
  --payload '{}' \
  response.json

cat response.json
```

Expected output:
```json
{
  "statusCode": 200,
  "body": "{\"message\":\"Scheduled activity update completed\",\"total_users\":5,\"successful_updates\":5,...}"
}
```

### Test User Endpoint

1. Log in to the application
2. Go to Settings page
3. Click "Refresh Activities" button
4. Verify success message shows updated count

### Test Admin Endpoint

1. Log in as an admin user
2. Go to Admin page
3. Select a user
4. Click "Update" button (blue, next to orange "Backfill" button)
5. Verify success message shows updated count

## Monitoring

### CloudWatch Logs

Monitor Lambda execution logs:
- `/aws/lambda/scheduled-activity-update`
- `/aws/lambda/user-update-activities`
- `/aws/lambda/admin-update-activities`

### CloudWatch Metrics

Key metrics to monitor:
- **Invocations**: Number of times Lambda is invoked
- **Errors**: Number of failed invocations
- **Duration**: Execution time
- **Throttles**: Number of throttled invocations

### EventBridge Metrics

Monitor scheduled rule:
- **Invocations**: Number of times rule triggered
- **FailedInvocations**: Failed triggers

## Troubleshooting

### Scheduled Lambda Not Running

1. Check EventBridge rule is enabled
2. Verify Lambda permission for EventBridge
3. Check CloudWatch Logs for errors

### User/Admin Update Fails

1. Verify API Gateway routes are configured
2. Check Lambda environment variables
3. Verify session cookie authentication
4. Check CloudWatch Logs for errors

### Activities Not Updating

1. Verify Strava tokens are valid (check `users` table)
2. Check if activities exist after Jan 1, 2026
3. Verify `athlete_count` field is in Strava API response
4. Check database for updated `updated_at` timestamps

## Rollback

If issues occur, you can rollback by:

1. Disable EventBridge rule
2. Remove API Gateway routes
3. Revert frontend deployment
4. Delete Lambda functions (optional)

## Notes

- The scheduled Lambda processes users sequentially to avoid Strava API rate limits
- All updates preserve existing trail matching data (time_on_trail, distance_on_trail)
- Access tokens are automatically refreshed if within 5 minutes of expiry
- Admin updates use the TARGET user's Strava tokens, not the admin's tokens
