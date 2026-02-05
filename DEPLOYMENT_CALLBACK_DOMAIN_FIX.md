# Deployment Guide: OAuth Callback Domain Fix

## Issue Summary

New users cannot authenticate because the OAuth callback flow is configured to use the GitHub Pages frontend domain (`timhibbard.github.io`) as the callback URL. However, Strava's Authorization Callback Domain must be configured to match the domain that receives the OAuth redirect.

## Root Cause

The OAuth flow was previously updated to use `{FRONTEND_URL}/callback` as the redirect_uri, which requires:
1. Configuring `timhibbard.github.io` as the Authorization Callback Domain in Strava
2. The frontend to forward OAuth parameters to the backend

This added unnecessary complexity and an extra redirect hop. More importantly, if the Strava Authorization Callback Domain was never updated to include `timhibbard.github.io`, the OAuth flow would fail.

## Solution

Revert the OAuth callback flow to directly use the API Gateway domain:
- Change `redirect_uri` from `{FRONTEND_URL}/callback` to `{API_BASE_URL}/auth/callback`
- This allows Strava's Authorization Callback Domain to be set to `9zke9jame0.execute-api.us-east-1.amazonaws.com`
- Eliminates the extra frontend callback hop

## Changes Made

### 1. backend/auth_start/lambda_function.py
**Line 113:**
```python
# Before:
redirect_uri = f"{FRONTEND}/callback"

# After:
redirect_uri = f"{API_BASE}/auth/callback"
```

### 2. backend/auth_callback/lambda_function.py
**Lines 224-227:**
```python
# Before:
# CRITICAL: redirect_uri must EXACTLY match the one used in auth_start
# auth_start uses {FRONTEND_URL}/callback, so we must use the same here
redirect_uri = f"{FRONTEND}/callback"

# After:
# CRITICAL: redirect_uri must EXACTLY match the one used in auth_start
# auth_start uses {API_BASE_URL}/auth/callback, so we must use the same here
redirect_uri = f"{API_BASE}/auth/callback"
```

## Deployment Instructions

### Prerequisites
- AWS CLI configured with proper credentials
- Access to Lambda functions: `rabbitmiles-auth-start`, `rabbitmiles-auth-callback`
- Access to Strava API application settings

### Step 1: Update Strava Authorization Callback Domain

**CRITICAL: Do this step FIRST, before deploying Lambda changes**

1. Go to https://www.strava.com/settings/api
2. Find your RabbitMiles application
3. Set **Authorization Callback Domain** to:
   ```
   9zke9jame0.execute-api.us-east-1.amazonaws.com
   ```
4. **Save** the changes

### Step 2: Deploy auth_start Lambda

```bash
cd backend/auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://function.zip
cd ../..
```

### Step 3: Deploy auth_callback Lambda

```bash
cd backend/auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-callback \
  --zip-file fileb://function.zip
cd ../..
```

### Step 4: Verify Deployment

Check CloudWatch logs to ensure Lambdas are using the new redirect_uri:

```bash
# Check auth_start logs
aws logs tail /aws/lambda/rabbitmiles-auth-start --follow

# Look for:
# "LOG - OAuth redirect_uri: https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback"
```

## Updated OAuth Flow

### After Fix (Simplified)
```
User clicks "Connect with Strava"
  ↓
Frontend redirects to: API Gateway /auth/start
  ↓
auth_start redirects to: Strava OAuth
  (with redirect_uri=https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback)
  ↓
User authorizes on Strava
  ↓
Strava redirects to: API Gateway /auth/callback ✨
  (directly to backend, no frontend hop)
  ↓
auth_callback validates & sets cookie
  ↓
Redirects to: Frontend /connect?connected=1
```

### Benefits of This Approach
1. **Simpler flow**: Eliminates extra frontend callback hop
2. **More reliable**: Direct backend-to-backend communication
3. **Easier to configure**: Only one domain in Strava settings
4. **Standard OAuth**: Follows typical OAuth 2.0 pattern
5. **Faster**: One less redirect

## Testing Instructions

After deployment:

1. **Clear cookies**: Clear browser cookies for both domains
2. **Go to Connect page**: Visit `https://timhibbard.github.io/rabbit-miles/connect`
3. **Click "Connect with Strava"**: Initiates OAuth flow
4. **Authorize on Strava**: Should redirect to Strava authorization page
5. **After authorization**: Should redirect directly to API Gateway callback endpoint
6. **Final redirect**: Should land on `/connect?connected=1` with user info

### Expected URLs During Flow
1. `https://timhibbard.github.io/rabbit-miles/connect` - Start
2. `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/start` - Initiates OAuth
3. `https://www.strava.com/oauth/authorize?...` - Strava authorization
4. `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback?code=XXX&state=YYY` - Backend validation
5. `https://timhibbard.github.io/rabbit-miles/connect?connected=1` - Success!

### CloudWatch Logs - Expected Output

**auth_start:**
```
LOG - OAuth redirect_uri: https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback
LOG - Strava OAuth URL length: 300+ chars
LOG - Redirecting to Strava OAuth page (302)
AUTH START LAMBDA - SUCCESS
```

**auth_callback:**
```
LOG - OAuth redirect_uri: https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback
LOG - Exchanging OAuth code for tokens with Strava
LOG - Strava response status: 200
LOG - Database upsert SUCCESS for user XXXXX
LOG - Creating session token for athlete_id: XXXXX
AUTH CALLBACK LAMBDA - SUCCESS
```

## Troubleshooting

### Error: "redirect_uri mismatch"
- **Cause**: Strava Authorization Callback Domain not updated
- **Fix**: Ensure Strava settings show `9zke9jame0.execute-api.us-east-1.amazonaws.com`

### Lambda still using old redirect_uri
- **Cause**: Lambda not redeployed or cached version
- **Fix**: 
  1. Check function last modified time in AWS Console
  2. Redeploy if necessary
  3. Try invoking function to clear any API Gateway cache

### Strava shows "Invalid redirect_uri"
- **Cause**: Mismatch between Strava settings and Lambda configuration
- **Fix**: Verify both locations use exactly: `9zke9jame0.execute-api.us-east-1.amazonaws.com`

## Rollback Plan

If issues occur, you can rollback Lambda functions to previous versions:

```bash
# List previous versions
aws lambda list-versions-by-function --function-name rabbitmiles-auth-start

# Rollback to specific version
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-start \
  --publish
```

**Note**: No database changes are involved, so rollback is safe and simple.

## Environment Variables

### Required for auth_start:
- `API_BASE_URL` - e.g., `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod`
- `FRONTEND_URL` - e.g., `https://timhibbard.github.io/rabbit-miles`
- `STRAVA_CLIENT_ID`
- `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME`

### Required for auth_callback:
- `API_BASE_URL` - e.g., `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod`
- `FRONTEND_URL` - e.g., `https://timhibbard.github.io/rabbit-miles`
- `APP_SECRET`
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`
- `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME`

**Note**: `FRONTEND_URL` is still needed for the final redirect after authentication succeeds.

## Success Criteria

After deployment, verify:
- [ ] Strava Authorization Callback Domain is `9zke9jame0.execute-api.us-east-1.amazonaws.com`
- [ ] New users can complete OAuth flow successfully
- [ ] CloudWatch logs show correct redirect_uri
- [ ] `/me` endpoint returns 200 (not 401)
- [ ] Cookies are set and stored correctly
- [ ] Users stay authenticated across page refreshes
- [ ] Disconnect functionality works correctly

## Security Notes

- ✅ No changes to authentication mechanism
- ✅ No changes to cookie security attributes
- ✅ No changes to token signing/validation
- ✅ State validation still happens in backend
- ✅ All security checks remain in place

## Summary

This fix restores the OAuth callback flow to use the API Gateway domain directly, which is:
- **Simpler**: Fewer redirects, easier to understand
- **More reliable**: Direct backend OAuth flow
- **Easier to configure**: Single domain in Strava settings
- **Standard practice**: Follows typical OAuth 2.0 patterns

The key change is that Strava now redirects directly to the backend `/auth/callback` endpoint instead of going through a frontend callback page first.

**Expected Impact**: New users will be able to complete Strava authentication successfully once the Strava Authorization Callback Domain is set correctly.
