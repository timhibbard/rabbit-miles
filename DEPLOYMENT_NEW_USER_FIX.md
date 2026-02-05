# New User Connection Fix - Deployment Guide

## Summary

This fix addresses the issue where new users cannot connect to Strava. The root cause is that cookies set during cross-origin 302 redirects are not reliably stored by modern browsers.

## Changes Made

### 1. Core Fix: HTML Response Instead of 302 Redirect

**Files Modified:**
- `backend/auth_callback/lambda_function.py`
- `backend/auth_disconnect/lambda_function.py`

**Change:** Instead of returning a 302 redirect response that sets cookies, we now return a 200 OK HTML page with:
- Meta refresh tag (`<meta http-equiv="refresh">`)
- JavaScript fallback redirect
- User-friendly loading message
- Cookies set in the response headers

This approach gives the browser time to process and store the cookies before the redirect occurs.

### 2. Extensive Logging for Debugging

**Files Modified:**
- `backend/auth_start/lambda_function.py`
- `backend/auth_callback/lambda_function.py`
- `backend/me/lambda_function.py`
- `backend/auth_disconnect/lambda_function.py`

**Additions:**
- Detailed request/response logging with clear markers (`LOG`, `ERROR`, `WARNING`)
- Cookie analysis (presence, length, attributes)
- Browser context detection (User-Agent, Sec-Fetch headers)
- Step-by-step flow tracking with visual separators
- Troubleshooting hints in error messages

## Deployment Instructions

### Option 1: Automatic Deployment (Recommended)

1. **Merge this PR to `main` branch**
   - The GitHub Actions workflow will automatically deploy all changed Lambda functions
   - Workflow file: `.github/workflows/deploy-lambdas.yml`
   - Deploys when changes are detected in `backend/**` paths

2. **Monitor Deployment**
   - Go to GitHub Actions tab
   - Check "Deploy Lambda Functions" workflow
   - Verify all 4 Lambdas deploy successfully:
     - `auth_start`
     - `auth_callback`
     - `auth_disconnect`
     - `me`

### Option 2: Manual Deployment

If you need to deploy immediately without merging:

```bash
# Set your AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_REGION="us-east-1"

# Deploy auth_start
cd backend/auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://function.zip
cd ../..

# Deploy auth_callback
cd backend/auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-callback \
  --zip-file fileb://function.zip
cd ../..

# Deploy auth_disconnect
cd backend/auth_disconnect
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-disconnect \
  --zip-file fileb://function.zip
cd ../..

# Deploy me
cd backend/me
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-me \
  --zip-file fileb://function.zip
cd ../..
```

## Testing the Fix

### Test Case 1: New User Connection

1. **Open an incognito/private browser window** (to simulate new user with no cookies)
2. Navigate to: `https://timhibbard.github.io/rabbit-miles/connect`
3. Click "Connect with Strava"
4. Authorize the app on Strava
5. **Expected:** You should see a "Successfully connected to Strava!" page for 1 second, then be redirected to the connect page showing "You're Connected!"
6. **Verify:** The `/me` endpoint returns your user data (check browser console or Network tab)

### Test Case 2: Existing User Reconnection

1. If already connected, click "Disconnect Strava"
2. **Expected:** You should see a "Successfully disconnected" page for 1 second
3. Click "Connect with Strava" again
4. **Expected:** Should work the same as Test Case 1

### Test Case 3: Check Logs

After testing, check CloudWatch logs for the Lambdas:

```bash
# View auth_callback logs
aws logs tail /aws/lambda/rabbitmiles-auth-callback --follow

# View me logs
aws logs tail /aws/lambda/rabbitmiles-me --follow
```

Look for:
- `AUTH CALLBACK LAMBDA - START` and `AUTH CALLBACK LAMBDA - SUCCESS`
- `LOG - Cookie configuration:` with all cookie attributes
- `/ME LAMBDA - START` and `/ME LAMBDA - SUCCESS`
- `LOG - Session token found!` in /me Lambda

## Debugging New Issues

If the issue persists after deployment, check these logs in order:

### 1. Check auth_start logs
```
AUTH START LAMBDA - START
LOG - State token generated
LOG - Setting rm_state cookie
```

### 2. Check auth_callback logs
```
AUTH CALLBACK LAMBDA - START
LOG - State validation SUCCESS
LOG - Strava response status: 200
LOG - Database upsert SUCCESS
LOG - Session token created successfully
LOG - Cookie configuration: [details]
```

### 3. Check me logs
```
/ME LAMBDA - START
LOG - Cookie analysis:
LOG -   Cookies array present: [true/false]
LOG -   Cookie header present: [true/false]
LOG - Session token found! [or ERROR - No session cookie found]
```

### Common Issues

**Issue:** Cookies not being sent to /me endpoint
- Check: `LOG - Cookie header present: False` in /me logs
- Solution: Cookie was not stored by browser
- Check browser DevTools > Application > Cookies
- Verify cookie domain matches API Gateway domain
- Check if third-party cookies are blocked

**Issue:** Session token verification failed
- Check: `ERROR - Session token verification FAILED` in /me logs
- Possible cause: APP_SECRET mismatch between Lambdas
- Verify: All Lambdas use the same APP_SECRET environment variable

## Rollback Plan

If this fix causes issues, you can rollback by:

1. Revert the PR on GitHub
2. Re-deploy Lambdas from the previous commit
3. Or manually restore previous Lambda code

The HTML redirect approach is backward compatible, so existing users should not be affected.

## Architecture Notes

### Why HTML Instead of 302 Redirect?

Modern browsers have stricter policies for third-party cookies. When a cookie is set during a cross-origin 302 redirect, some browsers (especially Chrome 115+) may not store the cookie properly, even with `SameSite=None; Secure; Partitioned` attributes.

By returning an HTML page that displays for 1 second before redirecting, we ensure:
1. The browser processes the response fully
2. Cookies are stored before the next navigation
3. The user sees a friendly "connecting" message instead of a blank redirect
4. JavaScript and meta refresh provide redundant redirect mechanisms

### Cookie Attributes Explained

- **HttpOnly**: Prevents JavaScript access (security)
- **Secure**: Only sent over HTTPS (required for SameSite=None)
- **SameSite=None**: Allows cross-site requests (required for cross-origin auth)
- **Partitioned**: Enables CHIPS (Cookies Having Independent Partitioned State) for Chrome 115+
- **Path=/**: Cookie available for all paths
- **Max-Age=2592000**: 30 days expiration

## Success Criteria

After deployment, new users should be able to:
1. Click "Connect with Strava"
2. Authorize on Strava
3. Be redirected back with a working session
4. See their dashboard with activities

The logs should show:
- Clear step-by-step flow through each Lambda
- Cookie being set in auth_callback
- Cookie being received in /me
- User data being returned successfully
