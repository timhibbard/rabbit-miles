# CORS Fix Deployment Guide

## Overview

This fix resolves the "Unable to Connect" network error that occurs after connecting with Strava. The issue was caused by missing CORS (Cross-Origin Resource Sharing) headers in the `/me` endpoint response.

## Root Cause

The frontend (hosted on GitHub Pages at `https://timhibbard.github.io/rabbit-miles`) makes a cross-origin request to the API Gateway endpoint. Without proper CORS headers, the browser blocks the response, resulting in a "Network Error".

## Changes Made

### backend/me/lambda_function.py

1. **Added FRONTEND_URL environment variable support**
   - Reads `FRONTEND_URL` from environment variables
   
2. **Added get_cors_headers() function**
   - Returns proper CORS headers including:
     - `Access-Control-Allow-Origin`: Set to the frontend URL
     - `Access-Control-Allow-Credentials`: "true" (required for cookie-based auth)
     - `Content-Type`: "application/json"

3. **Updated all response paths to include CORS headers**
   - 401 Unauthorized responses
   - 404 Not Found responses
   - 200 Success responses

4. **Improved error responses**
   - Changed from plain text to JSON format
   - All errors now return `{"error": "message"}` structure

## Prerequisites

- AWS CLI configured with appropriate credentials
- Access to Lambda function configuration
- `FRONTEND_URL` environment variable (e.g., `https://timhibbard.github.io/rabbit-miles`)

## Deployment Steps

### 1. Ensure FRONTEND_URL Environment Variable is Set

The `/me` Lambda function needs the `FRONTEND_URL` environment variable:

```bash
# Check if the variable exists
aws lambda get-function-configuration \
  --function-name YOUR_ME_FUNCTION_NAME \
  --query 'Environment.Variables.FRONTEND_URL'

# If it doesn't exist or is incorrect, update it
# Replace YOUR_ME_FUNCTION_NAME and other values with your actual values
aws lambda update-function-configuration \
  --function-name YOUR_ME_FUNCTION_NAME \
  --environment Variables={DB_CLUSTER_ARN=<existing-value>,DB_SECRET_ARN=<existing-value>,DB_NAME=<existing-value>,APP_SECRET=<existing-value>,FRONTEND_URL=https://timhibbard.github.io/rabbit-miles}
```

**Important**: Make sure to include all existing environment variables when updating, as the update command replaces all variables. Get the existing values first with:

```bash
aws lambda get-function-configuration \
  --function-name YOUR_ME_FUNCTION_NAME \
  --query 'Environment.Variables'
```

### 2. Deploy the Updated Lambda Function

```bash
cd backend/me
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_ME_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ../..
```

### 3. Verify the Deployment

After deployment, test the fix:

1. Open your browser's Developer Tools (F12)
2. Go to the Network tab
3. Visit your application: `https://timhibbard.github.io/rabbit-miles`
4. Look for the request to `/me` endpoint
5. Check the response headers - you should see:
   - `Access-Control-Allow-Origin: https://timhibbard.github.io/rabbit-miles`
   - `Access-Control-Allow-Credentials: true`

### 4. Test the OAuth Flow

1. Navigate to your frontend application
2. Click "Connect with Strava"
3. Authorize the application on Strava
4. Verify you are successfully redirected back and see the Dashboard
5. Verify you don't see the "Unable to Connect" error

## Troubleshooting

### Still seeing "Network Error"

1. **Check FRONTEND_URL matches exactly**
   - No trailing slash
   - Correct protocol (https)
   - Correct subdomain and path

2. **Verify Lambda was deployed**
   ```bash
   aws lambda get-function \
     --function-name YOUR_ME_FUNCTION_NAME \
     --query 'Configuration.LastModified'
   ```

3. **Check CloudWatch Logs**
   ```bash
   aws logs tail /aws/lambda/YOUR_ME_FUNCTION_NAME --follow
   ```

### CORS headers not appearing

1. **Ensure FRONTEND_URL environment variable is set**
   - If FRONTEND_URL is empty or not set, CORS headers won't be added

2. **Check API Gateway configuration**
   - API Gateway HTTP API should be configured to pass through Lambda response headers
   - Verify no CORS configuration conflicts in API Gateway

### Different error message

- If you see a different error, check the browser console for details
- Check the Network tab to see the actual response from the server
- Review CloudWatch Logs for backend errors

## Security Considerations

- CORS headers are only added when `FRONTEND_URL` is configured
- `Access-Control-Allow-Credentials: true` is required for cookie-based authentication
- The origin is explicitly set (not using wildcard `*`) for security
- Error responses now return JSON instead of plain text for consistency

## Rollback Plan

If you need to rollback:

1. Deploy the previous version of the Lambda function
2. The change is backwards compatible - if FRONTEND_URL is not set, CORS headers won't be added (but the function will still work for same-origin requests)

## Testing Checklist

- [ ] `FRONTEND_URL` environment variable is set correctly
- [ ] Lambda function deployed successfully
- [ ] `/me` endpoint returns CORS headers in response
- [ ] OAuth flow completes successfully
- [ ] Dashboard loads after authentication
- [ ] No "Unable to Connect" error appears
- [ ] User profile information displays correctly
