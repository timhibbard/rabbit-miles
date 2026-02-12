# Deployment and Verification Guide

## Summary
This fix resolves the 500 error that users encounter when clicking "Refresh Activities from Strava" in the Settings page. The issue was caused by missing OPTIONS preflight handling and APP_SECRET validation in the `user_update_activities` Lambda function.

## Pre-Deployment Checklist

### 1. Code Quality ✅
- [x] Python syntax check passed
- [x] Code review completed
- [x] Security scan (CodeQL) completed - 0 vulnerabilities found
- [x] Pattern matches existing Lambda functions

### 2. Testing ✅
- [x] Local tests pass
  - OPTIONS preflight handling works correctly
  - APP_SECRET validation returns clear error
  - POST requests with invalid sessions return 401
  - CORS headers are properly set

### 3. Documentation ✅
- [x] Created `FIX_500_ERROR_ACTIVITIES_UPDATE.md` with detailed explanation
- [x] Deployment instructions provided
- [x] Verification steps documented

## Deployment Steps

### Automatic Deployment (Recommended)
1. **Merge PR** to `main` branch
2. **GitHub Actions** will automatically deploy via `.github/workflows/deploy-lambdas.yml`
3. **Monitor** the GitHub Actions workflow for successful deployment

### Manual Deployment (If Needed)
```bash
cd backend/user_update_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name <LAMBDA_USER_UPDATE_ACTIVITIES> \
  --zip-file fileb://function.zip
```

## Post-Deployment Verification

### 1. Lambda Configuration Check
Verify the Lambda has all required environment variables:

```bash
aws lambda get-function-configuration \
  --function-name <LAMBDA_USER_UPDATE_ACTIVITIES> \
  --query 'Environment.Variables' \
  --output json
```

Expected variables:
- ✅ `DB_CLUSTER_ARN`
- ✅ `DB_SECRET_ARN`
- ✅ `DB_NAME`
- ✅ `APP_SECRET` ⚠️ **Critical: Must be set!**
- ✅ `FRONTEND_URL`
- ✅ `STRAVA_CLIENT_ID`
- ✅ `STRAVA_CLIENT_SECRET`

### 2. CloudWatch Logs Check
After deployment, monitor the logs for the first few requests:

```bash
aws logs tail /aws/lambda/<LAMBDA_USER_UPDATE_ACTIVITIES> --follow
```

Look for:
- ✅ "OPTIONS preflight request - returning CORS headers" for OPTIONS requests
- ✅ "user_update_activities handler invoked" for POST requests
- ❌ "ERROR: Missing APP_SECRET" (should NOT appear if configured correctly)

### 3. Functional Testing

#### Test 1: OPTIONS Preflight
```bash
curl -X OPTIONS https://api.rabbitmiles.com/activities/update \
  -H "Origin: https://rabbitmiles.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type, Cookie" \
  -v
```

Expected:
- Status: 200 OK
- Headers include:
  - `Access-Control-Allow-Origin: https://rabbitmiles.com`
  - `Access-Control-Allow-Methods: POST, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, Cookie`
  - `Access-Control-Allow-Credentials: true`

#### Test 2: POST Without Session (Should Return 401)
```bash
curl -X POST https://api.rabbitmiles.com/activities/update \
  -H "Content-Type: application/json" \
  -H "Origin: https://rabbitmiles.com" \
  -v
```

Expected:
- Status: 401 Unauthorized
- Body: `{"error": "authentication required"}`
- Headers include CORS headers

#### Test 3: Full User Flow
1. Open https://rabbitmiles.com in a browser
2. Log in with Strava credentials
3. Navigate to Settings page
4. Click "Refresh Activities from Strava" button
5. Verify:
   - ✅ No 500 error appears
   - ✅ Success message shows (e.g., "Updated 25 activities")
   - ✅ Activities list refreshes with latest data

### 4. Browser DevTools Check
Open browser DevTools (F12) → Network tab during the test:

1. **Preflight Request** (OPTIONS):
   - Method: OPTIONS
   - Status: 200
   - Response headers show CORS configuration

2. **Actual Request** (POST):
   - Method: POST
   - Status: 200 (or 401 if not logged in)
   - Request includes: Cookie header with `rm_session`
   - Response includes: CORS headers

## Rollback Plan

If issues occur after deployment:

### Quick Rollback
```bash
# Get previous version
aws lambda get-function \
  --function-name <LAMBDA_USER_UPDATE_ACTIVITIES> \
  --query 'Configuration.Version'

# Rollback to previous version (replace N with version number)
aws lambda update-alias \
  --function-name <LAMBDA_USER_UPDATE_ACTIVITIES> \
  --name PROD \
  --function-version N
```

### Full Rollback via GitHub
1. Revert the PR merge commit
2. Push to `main` branch
3. GitHub Actions will redeploy the previous version

## Troubleshooting

### Issue: Still Getting 500 Error
**Check:**
1. Is APP_SECRET environment variable set on the Lambda?
2. Are CloudWatch logs showing "ERROR: Missing APP_SECRET"?
3. Is the correct Lambda function deployed (user_update_activities, not update_activities)?

**Fix:**
Set APP_SECRET environment variable:
```bash
aws lambda update-function-configuration \
  --function-name <LAMBDA_USER_UPDATE_ACTIVITIES> \
  --environment Variables={APP_SECRET=<your-secret-key>,...}
```

### Issue: CORS Error in Browser
**Check:**
1. Is FRONTEND_URL environment variable correct?
2. Are OPTIONS requests returning 200?
3. Is API Gateway configured to pass through OPTIONS requests to Lambda?

**Fix:**
Verify FRONTEND_URL:
```bash
aws lambda get-function-configuration \
  --function-name <LAMBDA_USER_UPDATE_ACTIVITIES> \
  --query 'Environment.Variables.FRONTEND_URL'
```

### Issue: Authentication Failed (401)
**Check:**
1. Is rm_session cookie being sent?
2. Is APP_SECRET the same value used by auth_callback Lambda?
3. Has the session expired?

**Fix:**
1. Log out and log back in
2. Verify APP_SECRET matches across all Lambdas
3. Check session cookie expiry time

## Success Criteria

The deployment is successful when:
- ✅ OPTIONS requests return 200 with proper CORS headers
- ✅ POST requests without authentication return 401 (not 500)
- ✅ POST requests with valid authentication return 200 with activity data
- ✅ Users can successfully refresh activities from Settings page
- ✅ No 500 errors in CloudWatch logs
- ✅ No CORS errors in browser console

## Monitoring

After deployment, monitor for 24-48 hours:

1. **CloudWatch Metrics**:
   - Invocation count (should increase after deployment)
   - Error rate (should decrease to ~0%)
   - Duration (should remain similar)

2. **CloudWatch Logs**:
   - OPTIONS requests are handled correctly
   - No "ERROR: Missing APP_SECRET" messages
   - No unhandled exceptions

3. **User Feedback**:
   - No reports of 500 errors
   - Successful activity refreshes reported

## Contact

If issues persist after following this guide:
1. Check CloudWatch Logs for detailed error messages
2. Review the `FIX_500_ERROR_ACTIVITIES_UPDATE.md` for technical details
3. Verify API Gateway configuration points to `user_update_activities` Lambda

---

**Last Updated:** February 12, 2026
**Version:** 1.0
**Related PR:** Fix 500 error when refreshing activities from Strava
