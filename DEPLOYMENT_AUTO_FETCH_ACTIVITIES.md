# Automatic Activity Fetch for New Users - Deployment Guide

## Overview
This update enables automatic activity fetching when a new user logs in via Strava OAuth. Previously, new users had to manually click "Fetch Activities" after logging in. Now, activities are automatically fetched in the background for new users.

## Changes Summary
- **auth_callback**: Detects new users and triggers activity fetch asynchronously
- **fetch_activities**: Supports both API Gateway (existing) and direct Lambda invocation (new)
- No changes to existing user experience (returning users are unaffected)

## Deployment Steps

### 1. Deploy Updated Lambda Functions

Deploy the updated Lambda code using GitHub Actions or manually:

#### Option A: GitHub Actions (Recommended)
1. Push changes to the `main` branch
2. GitHub Actions will automatically deploy both lambdas:
   - `auth_callback`
   - `fetch_activities`

#### Option B: Manual Deployment
```bash
# Deploy auth_callback
cd backend/auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_LAMBDA_NAME \
  --zip-file fileb://function.zip

# Deploy fetch_activities
cd ../fetch_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_FETCH_ACTIVITIES_LAMBDA_NAME \
  --zip-file fileb://function.zip
```

### 2. Configure Environment Variables

Add the following environment variable to the `auth_callback` Lambda function:

```bash
FETCH_ACTIVITIES_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT_ID:function:YOUR_FETCH_ACTIVITIES_LAMBDA_NAME
```

Or use the AWS CLI:

```bash
aws lambda update-function-configuration \
  --function-name YOUR_AUTH_CALLBACK_LAMBDA_NAME \
  --environment "Variables={
    DB_CLUSTER_ARN=YOUR_DB_CLUSTER_ARN,
    DB_SECRET_ARN=YOUR_DB_SECRET_ARN,
    DB_NAME=postgres,
    API_BASE_URL=YOUR_API_BASE_URL,
    FRONTEND_URL=YOUR_FRONTEND_URL,
    APP_SECRET=YOUR_APP_SECRET,
    STRAVA_CLIENT_ID=YOUR_STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET=YOUR_STRAVA_CLIENT_SECRET,
    FETCH_ACTIVITIES_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT_ID:function:YOUR_FETCH_ACTIVITIES_LAMBDA_NAME
  }"
```

### 3. Grant Lambda Invocation Permissions

The `auth_callback` Lambda needs permission to invoke the `fetch_activities` Lambda:

```bash
aws lambda add-permission \
  --function-name YOUR_FETCH_ACTIVITIES_LAMBDA_NAME \
  --statement-id AllowInvokeFromAuthCallback \
  --action lambda:InvokeFunction \
  --principal lambda.amazonaws.com \
  --source-arn arn:aws:lambda:REGION:ACCOUNT_ID:function:YOUR_AUTH_CALLBACK_LAMBDA_NAME
```

Or add this IAM policy to the `auth_callback` Lambda's execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:YOUR_FETCH_ACTIVITIES_LAMBDA_NAME"
    }
  ]
}
```

## Verification

### Test New User Flow
1. Create a test Strava account (or use one that hasn't connected to RabbitMiles)
2. Navigate to your RabbitMiles frontend
3. Click "Connect to Strava"
4. Complete the OAuth flow
5. Check CloudWatch logs for `auth_callback`:
   ```
   LOG - New user detected: ATHLETE_ID (Name)
   LOG - Triggering automatic activity fetch for new user ATHLETE_ID
   LOG - Successfully triggered activity fetch lambda: status 202
   ```
6. Check CloudWatch logs for `fetch_activities`:
   ```
   Direct lambda invocation detected
   Direct invocation for athlete_id: ATHLETE_ID
   Direct invocation completed: N activities stored
   ```
7. Verify activities appear in the frontend dashboard

### Test Existing User Flow
1. Disconnect from Strava (if already connected)
2. Reconnect to Strava
3. Check CloudWatch logs for `auth_callback`:
   ```
   LOG - Existing user returning: ATHLETE_ID (Name)
   ```
4. Verify no duplicate activity fetch is triggered (user must manually click "Fetch Activities")

## Rollback Plan

If issues arise, you can disable automatic fetching by removing the environment variable:

```bash
# Remove the FETCH_ACTIVITIES_LAMBDA_ARN environment variable
aws lambda update-function-configuration \
  --function-name YOUR_AUTH_CALLBACK_LAMBDA_NAME \
  --environment "Variables={
    DB_CLUSTER_ARN=YOUR_DB_CLUSTER_ARN,
    DB_SECRET_ARN=YOUR_DB_SECRET_ARN,
    DB_NAME=postgres,
    API_BASE_URL=YOUR_API_BASE_URL,
    FRONTEND_URL=YOUR_FRONTEND_URL,
    APP_SECRET=YOUR_APP_SECRET,
    STRAVA_CLIENT_ID=YOUR_STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET=YOUR_STRAVA_CLIENT_SECRET
  }"
```

The system will log a warning but continue to work normally:
```
WARNING - FETCH_ACTIVITIES_LAMBDA_ARN not configured, skipping automatic activity fetch
```

## Troubleshooting

### Activities not fetching for new users

1. Check `auth_callback` CloudWatch logs for:
   - "New user detected" message
   - "Successfully triggered activity fetch lambda" message
   - Any errors or warnings

2. Check `fetch_activities` CloudWatch logs for:
   - "Direct lambda invocation detected" message
   - Activity fetch progress
   - Any errors

3. Verify environment variable is set:
   ```bash
   aws lambda get-function-configuration \
     --function-name YOUR_AUTH_CALLBACK_LAMBDA_NAME \
     --query 'Environment.Variables.FETCH_ACTIVITIES_LAMBDA_ARN'
   ```

4. Verify IAM permissions:
   ```bash
   aws lambda get-policy \
     --function-name YOUR_FETCH_ACTIVITIES_LAMBDA_NAME
   ```

### Auth callback failing

If the auth callback fails, it will NOT block the login flow. The user will still be logged in successfully, but activities won't be automatically fetched. Check CloudWatch logs for warnings.

## Notes

- Activity fetch is asynchronous and non-blocking (uses `InvocationType='Event'`)
- If activity fetch fails, the login still succeeds (graceful degradation)
- Existing users (returning users) are not affected by this change
- The `fetch_activities` Lambda maintains backward compatibility with API Gateway invocations
