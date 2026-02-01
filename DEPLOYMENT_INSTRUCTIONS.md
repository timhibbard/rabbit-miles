# Deployment Instructions for Network Error Fix

## Overview
This fix addresses the network error that occurs when users click "Refresh Activities" on the Dashboard. The issue was caused by the `fetch_activities` Lambda function lacking authentication, which resulted in 500 errors and CORS issues.

## Changes Made
1. Modified `backend/fetch_activities/lambda_function.py` to require authentication
2. Updated to fetch activities only for the authenticated user
3. Added proper error handling with CORS headers

## Deployment Steps

### 1. Update Lambda Environment Variables

The `fetch_activities` Lambda function now requires an additional environment variable:

```bash
# Set the APP_SECRET environment variable (same value used by other auth endpoints)
aws lambda update-function-configuration \
  --function-name rabbitmiles-fetch-activities \
  --environment Variables="{
    DB_CLUSTER_ARN=$DB_CLUSTER_ARN,
    DB_SECRET_ARN=$DB_SECRET_ARN,
    DB_NAME=postgres,
    APP_SECRET=$APP_SECRET,
    STRAVA_CLIENT_ID=$STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET=$STRAVA_CLIENT_SECRET,
    FRONTEND_URL=$FRONTEND_URL
  }"
```

**Important:** The `APP_SECRET` must be the same value used by:
- `auth_callback` Lambda
- `auth_disconnect` Lambda  
- `me` Lambda
- `get_activities` Lambda

### 2. Deploy Updated Lambda Code

Package and deploy the updated Lambda function:

```bash
cd backend/fetch_activities
zip -r lambda.zip lambda_function.py

aws lambda update-function-code \
  --function-name rabbitmiles-fetch-activities \
  --zip-file fileb://lambda.zip
```

### 3. Verify Lambda Permissions

Ensure the Lambda execution role has the necessary permissions:
- `rds-data:ExecuteStatement` - Access RDS Data API
- `secretsmanager:GetSecretValue` - Read database secrets
- `secretsmanager:GetSecretValue` - Read Strava secrets (if using STRAVA_SECRET_ARN)

### 4. Test the Endpoint

After deployment, test that the endpoint works correctly:

1. **Test with valid authentication:**
   - Log in to the application at https://timhibbard.github.io
   - Click the "Refresh Activities" button on the Dashboard
   - Should see success message with number of activities synced

2. **Test without authentication (should fail gracefully):**
   ```bash
   curl -X POST https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/activities/fetch \
     -H "Content-Type: application/json"
   ```
   Expected: 401 response with `{"error": "not authenticated"}`

3. **Test with invalid session (should fail gracefully):**
   ```bash
   curl -X POST https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/activities/fetch \
     -H "Content-Type: application/json" \
     -H "Cookie: rm_session=invalid.token.here"
   ```
   Expected: 401 response with `{"error": "invalid session"}`

## Expected Behavior After Fix

### Before Fix
- Clicking "Refresh Activities" resulted in:
  - Network Error displayed on screen
  - 500 Internal Server Error
  - CORS errors in browser console
  - Lambda attempted to fetch activities for ALL users

### After Fix
- Clicking "Refresh Activities" will:
  - Verify user is authenticated via session cookie
  - Fetch activities only for the authenticated user
  - Return success message with count of activities synced
  - Show green success banner on Dashboard
  - Activities list automatically refreshes

### Error Handling
The endpoint now properly handles various error cases:
- **401 Unauthorized**: User not logged in or invalid session
- **404 Not Found**: User record not found in database
- **400 Bad Request**: User not connected to Strava
- **500 Internal Server Error**: Unexpected errors

All error responses include proper CORS headers to prevent browser CORS errors.

## Security Improvements

This fix includes important security improvements:
1. **Authentication required**: Prevents anonymous users from triggering activity syncs
2. **User-specific**: Users can only refresh their own activities, not other users'
3. **Proper error handling**: Returns appropriate HTTP status codes with CORS headers
4. **Session verification**: Uses HMAC signature to verify session tokens

## Rollback Plan

If issues occur after deployment, you can rollback by:

1. **Revert Lambda code to previous version:**
   ```bash
   aws lambda update-function-code \
     --function-name rabbitmiles-fetch-activities \
     --s3-bucket your-backup-bucket \
     --s3-key lambda-backups/fetch_activities-previous.zip
   ```

2. **Or revert to previous Git commit:**
   ```bash
   git revert HEAD
   git push
   # Then redeploy Lambda from reverted code
   ```

## Monitoring

After deployment, monitor:
1. CloudWatch Logs for the `fetch_activities` Lambda
2. API Gateway metrics for `/activities/fetch` endpoint
3. User feedback on Dashboard functionality

Look for:
- Successful 200 responses when users click "Refresh Activities"
- Proper 401 responses for unauthenticated requests
- No 500 errors or CORS-related errors
- Activities appearing on Dashboard after refresh

## Support

If issues persist after deployment:
1. Check CloudWatch Logs for the Lambda function
2. Verify environment variables are set correctly
3. Confirm APP_SECRET matches across all Lambda functions
4. Test authentication flow with `/me` endpoint
5. Check API Gateway route configuration for `/activities/fetch`
