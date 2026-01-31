# Cookie Authentication Fix - Deployment Guide

## Problem Summary

After authentication, users were still prompted to connect with Strava because the `/me` endpoint was returning 401 (not authenticated). 

**Root Cause**: API Gateway HTTP API v2 provides cookies in `event['cookies']` array, not in `event['headers']['cookie']`. The Lambda functions were only checking headers, causing authentication to fail.

## Solution

Updated all Lambda functions to read cookies from the correct location in the API Gateway HTTP API v2 event format.

## Affected Lambda Functions

1. **me** - Session validation endpoint
2. **auth_callback** - OAuth callback handler (state validation)
3. **auth_disconnect** - Disconnect/logout handler

## Deployment Steps

### Prerequisites

- AWS CLI configured with appropriate credentials
- Access to update Lambda functions in your AWS account
- Lambda function names (find these in AWS Console or your infrastructure config)

### Step 1: Deploy Updated Lambda Functions

#### Option A: Using AWS CLI (Recommended)

```bash
# Navigate to the backend directory
cd backend

# Deploy the /me Lambda
cd me
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_ME_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ..

# Deploy the auth_callback Lambda
cd auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ..

# Deploy the auth_disconnect Lambda
cd auth_disconnect
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_DISCONNECT_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ..
```

**Note**: Replace `YOUR_*_FUNCTION_NAME` with your actual Lambda function names. You can find these in:
- AWS Console → Lambda → Functions
- Your infrastructure as code (Terraform, CloudFormation, SAM, etc.)

#### Option B: Using Infrastructure as Code

If you're using Terraform, CloudFormation, or SAM:

1. Copy the updated Lambda code to your infrastructure repository
2. Run your deployment command:
   - Terraform: `terraform apply`
   - CloudFormation: `aws cloudformation update-stack ...`
   - SAM: `sam deploy`

#### Option C: Using AWS Console

1. Navigate to AWS Lambda in the console
2. For each function (me, auth_callback, auth_disconnect):
   - Click the function name
   - Go to "Code" tab
   - Click "Upload from" → ".zip file"
   - Upload the corresponding function.zip file
   - Click "Save"

### Step 2: Verify Deployment

After deploying, verify the Lambda code has been updated:

```bash
# Check the last modified time - should be recent
aws lambda get-function --function-name YOUR_ME_FUNCTION_NAME \
  --query 'Configuration.LastModified'

aws lambda get-function --function-name YOUR_AUTH_CALLBACK_FUNCTION_NAME \
  --query 'Configuration.LastModified'

aws lambda get-function --function-name YOUR_AUTH_DISCONNECT_FUNCTION_NAME \
  --query 'Configuration.LastModified'
```

### Step 3: Test the Fix

#### 3.1 Clear Browser State

1. Open browser DevTools (F12)
2. Go to Application → Cookies
3. Delete all cookies for your domain
4. Close and reopen browser to ensure clean state

#### 3.2 Test Authentication Flow

1. Navigate to your app: `https://timhibbard.github.io/rabbit-miles/`
2. Click "Connect with Strava"
3. Authorize on Strava
4. You should be redirected back and see your profile

#### 3.3 Check CloudWatch Logs

After attempting authentication, check CloudWatch logs for the `/me` Lambda:

**Expected logs (SUCCESS):**
```
Cookies array: ['rm_session=eyJhaWQi...']
Cookie header: None
Found rm_session cookie: eyJhaWQi...
Verified session for athlete_id: 3519964
Successfully retrieved user from database
```

**Old logs (FAILURE - before fix):**
```
Cookie header received: False
No rm_session cookie found. Cookie header: None
```

To view logs:
```bash
# Get recent log events for /me Lambda
aws logs tail /aws/lambda/YOUR_ME_FUNCTION_NAME --follow

# Or in AWS Console:
# CloudWatch → Log groups → /aws/lambda/YOUR_ME_FUNCTION_NAME
```

#### 3.4 Check Network Tab

In browser DevTools → Network tab:

**Request to `/me`:**
- Status: 200 ✓
- Request Cookie header: `rm_session=eyJhaWQi...` ✓
- Response: `{"athlete_id": ..., "display_name": "...", ...}` ✓

**Request to `/auth/callback`:**
- Status: 302 (redirect) ✓
- Response Set-Cookie header: `rm_session=...` ✓

## Troubleshooting

### Issue: Still getting 401 from /me

**Check:**
1. Did you deploy all three Lambda functions?
2. Are the Lambdas using the latest code? (Check LastModified time)
3. Check CloudWatch logs - do you see "Cookies array:" in the logs?
4. Is API Gateway correctly routing to the updated Lambdas?

**If logs still show "Cookie header received: False":**
- The old code is still running
- Redeploy the Lambda function
- Check you're updating the correct function name

### Issue: Logs show empty cookies array

**Possible causes:**
1. Cookie not being set properly by auth_callback
2. Cookie domain/path mismatch
3. Browser blocking third-party cookies

**Check:**
- Verify auth_callback is setting cookie with correct Path (should match API Gateway stage)
- Verify cookie has `SameSite=None` and `Secure` attributes
- Check browser console for cookie warnings

### Issue: Session token verification failed

**Possible causes:**
1. APP_SECRET mismatch between auth_callback and me Lambdas
2. Token expired (30 day max age)
3. Token corrupted in transit

**Check:**
- Verify APP_SECRET environment variable is identical in both Lambdas
- Check token expiration in CloudWatch logs
- Try authenticating again to get a fresh token

## Technical Details

### API Gateway HTTP API v2 Event Format

**Before (incorrect):**
```python
cookie_header = event.get("headers", {}).get("cookie")
# Always returns None in v2 format!
```

**After (correct):**
```python
# v2 format: cookies are in a separate array
cookies_array = event.get("cookies") or []
# Format: ['cookie1=value1', 'cookie2=value2']

# Also check headers for backwards compatibility
cookie_header = event.get("headers", {}).get("cookie")
```

### Cookie Parsing Precedence

When both formats are present (unlikely, but for robustness):
1. **Preferred**: `event['cookies']` array (v2 format)
2. **Fallback**: `event['headers']['cookie']` (v1 format or direct testing)

This ensures forward compatibility with API Gateway HTTP API v2 while maintaining backwards compatibility.

## Success Criteria

- [ ] All three Lambda functions deployed successfully
- [ ] User can complete OAuth flow
- [ ] `/me` endpoint returns 200 with user data
- [ ] CloudWatch logs show "Cookies array: [...]"
- [ ] CloudWatch logs show "Found rm_session cookie: ..."
- [ ] No 401 errors in browser console
- [ ] User stays authenticated across page refreshes

## Rollback Plan

If issues occur:

1. **Lambda Rollback**: Use AWS Lambda versioning to rollback to previous version
   ```bash
   aws lambda update-function-configuration \
     --function-name YOUR_FUNCTION_NAME \
     --revert-to-version PREVIOUS_VERSION_NUMBER
   ```

2. **No Database Changes**: This fix only changes Lambda code, no database migrations needed

3. **No Frontend Changes**: Frontend code unchanged, only backend Lambdas updated

## Security Considerations

- No changes to authentication mechanism
- No changes to token signing/verification
- No changes to cookie attributes (HttpOnly, Secure, SameSite)
- Cookie parsing is more robust and handles both formats
- No sensitive data logged (tokens are truncated in logs)

## Additional Notes

### Why did this happen?

API Gateway HTTP API v2 uses a different payload format than v1. In v2:
- Headers are lowercase and normalized
- Cookies are provided in a separate `cookies` array
- Direct cookie header access doesn't work

The Lambda functions were written assuming v1 format, causing cookies to be missed.

### Why both formats?

Supporting both formats ensures:
1. **Production**: Works with API Gateway HTTP API v2
2. **Testing**: Works with direct Lambda invocation
3. **Migration**: Smooth transition if API Gateway format changes
4. **Debugging**: Can test Lambdas with either format

### Related Documentation

- [API Gateway HTTP API v2 Payload Format](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html)
- [Lambda Function Handler in Python](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [Working with Cookies in API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-cookies.html)
