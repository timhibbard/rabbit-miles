# Troubleshooting Guide: 500 Error on Activity Refresh

## Issue Summary

Users report 500 errors when clicking "Refresh Activities from Strava" button in Settings page, even after PR #217 was merged.

**Error Message:** `Failed to update activities: Request failed with status code 500`

**Endpoint:** `POST /activities/update`

**Lambda:** `user_update_activities`

---

## Root Cause Analysis

The `user_update_activities` Lambda code is **functionally correct** (all tests pass ✅), which means the 500 error is caused by:

1. **Deployment Issue** - Latest code not deployed to AWS Lambda
2. **Configuration Issue** - Missing required environment variables
3. **Runtime Issue** - Problem only manifesting in AWS environment

---

## Verification Steps

### Step 1: Check Lambda Deployment Status

```bash
# Check when Lambda was last updated
aws lambda get-function \
  --function-name rabbitmiles-user-update-activities \
  --query 'Configuration.[LastModified,CodeSize,Handler]' \
  --output table

# Compare with latest commit date in GitHub
```

**Expected:**
- LastModified should be AFTER PR #217 merge date
- Handler should be `lambda_function.handler`
- CodeSize should be > 5000 bytes

### Step 2: Check Environment Variables

```bash
# List all environment variables
aws lambda get-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --query 'Environment.Variables' \
  --output json
```

**Required Variables:**
- ✅ `DB_CLUSTER_ARN` - Database cluster ARN
- ✅ `DB_SECRET_ARN` - Database secret ARN  
- ✅ `DB_NAME` - Database name (default: postgres)
- ✅ `APP_SECRET` - **CRITICAL** - Session signing secret
- ✅ `FRONTEND_URL` - Frontend origin (https://rabbitmiles.com)
- ✅ `STRAVA_CLIENT_ID` - Strava OAuth client ID
- ✅ `STRAVA_CLIENT_SECRET` - Strava OAuth client secret

**Check for Missing Variables:**
```bash
# Check each variable individually
for var in DB_CLUSTER_ARN DB_SECRET_ARN DB_NAME APP_SECRET FRONTEND_URL STRAVA_CLIENT_ID STRAVA_CLIENT_SECRET; do
  value=$(aws lambda get-function-configuration \
    --function-name rabbitmiles-user-update-activities \
    --query "Environment.Variables.$var" \
    --output text 2>/dev/null)
  
  if [ "$value" = "None" ] || [ -z "$value" ]; then
    echo "❌ $var: NOT SET"
  else
    echo "✅ $var: SET"
  fi
done
```

### Step 3: Check CloudWatch Logs

The Lambda now includes enhanced logging. Check the most recent invocation:

```bash
# Tail CloudWatch logs
aws logs tail /aws/lambda/rabbitmiles-user-update-activities --follow

# Or get recent logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-user-update-activities \
  --start-time $(date -d '10 minutes ago' +%s)000 \
  --query 'events[].message' \
  --output text
```

**Look for:**
1. **Environment check line:**
   ```
   Environment check: DB_CLUSTER_ARN=set, DB_SECRET_ARN=set, APP_SECRET=set, FRONTEND_URL=https://rabbitmiles.com
   ```
   - If any show "NOT SET", that's the problem

2. **Error messages:**
   ```
   ERROR: Missing APP_SECRET
   ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN
   ```

3. **Authentication issues:**
   ```
   No session cookie found
   Invalid session token
   ```

4. **Strava API errors:**
   ```
   Failed to fetch activities from Strava
   ```

5. **Database errors:**
   ```
   ERROR: Failed to store activity
   ```

---

## Fix Instructions

### If Lambda Not Deployed

```bash
# Manual deployment
cd backend/user_update_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-user-update-activities \
  --zip-file fileb://function.zip

# Or trigger GitHub Actions
# Push to main branch or manually trigger the workflow
```

### If Environment Variables Missing

```bash
# Update environment variables
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --environment Variables="{
    DB_CLUSTER_ARN=arn:aws:rds:...,
    DB_SECRET_ARN=arn:aws:secretsmanager:...,
    DB_NAME=postgres,
    APP_SECRET=your-secret-key-here,
    FRONTEND_URL=https://rabbitmiles.com,
    STRAVA_CLIENT_ID=your-client-id,
    STRAVA_CLIENT_SECRET=your-client-secret
  }"
```

**Note:** Make sure `APP_SECRET` matches the value used by other auth Lambdas (`me`, `auth_callback`, `auth_disconnect`).

### If APP_SECRET Missing or Wrong

This is the most common issue. The `APP_SECRET` must be:
1. **Set** in the Lambda environment variables
2. **Consistent** across all Lambdas that use session cookies:
   - `auth_callback` - Creates session cookies
   - `auth_disconnect` - Clears session cookies
   - `me` - Verifies session cookies
   - `user_update_activities` - Verifies session cookies
   - All `admin_*` Lambdas that require authentication

```bash
# Get APP_SECRET from one of the working Lambdas
APP_SECRET=$(aws lambda get-function-configuration \
  --function-name rabbitmiles-me \
  --query 'Environment.Variables.APP_SECRET' \
  --output text)

# Set it on user_update_activities
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --environment Variables="{APP_SECRET=$APP_SECRET,...other vars...}"
```

---

## Testing After Fix

### Test 1: Check CloudWatch Logs

After making changes, trigger the endpoint and immediately check logs:

```bash
# In one terminal, tail logs
aws logs tail /aws/lambda/rabbitmiles-user-update-activities --follow

# In browser, click "Refresh Activities" button
```

**Expected log output:**
```
user_update_activities handler invoked
Event: {...}
Environment check: DB_CLUSTER_ARN=set, DB_SECRET_ARN=set, APP_SECRET=set, FRONTEND_URL=https://rabbitmiles.com
Authenticated user: athlete_id=123456
Updating activities for user 123456
Fetched X activities from Strava
Successfully stored activity ...
Update completed: {...}
```

### Test 2: Functional Test

1. Log in to https://rabbitmiles.com
2. Go to Settings page
3. Click "Refresh Activities from Strava"
4. **Expected:** Success alert with count: "Success! Updated X activities out of Y fetched from Strava."
5. **Not:** "Failed to update activities: Request failed with status code 500"

### Test 3: API Test

```bash
# Get session cookie from browser (Developer Tools -> Application -> Cookies)
SESSION_COOKIE="your-rm_session-cookie-value"

curl -X POST https://api.rabbitmiles.com/activities/update \
  -H "Cookie: rm_session=$SESSION_COOKIE" \
  -v

# Expected: 200 OK with JSON response
# {
#   "message": "Activities updated successfully",
#   "athlete_id": 123456,
#   "total_activities": 50,
#   "stored": 50,
#   "failed": 0
# }
```

---

## Common Issues and Solutions

### Issue 1: "ERROR: Missing APP_SECRET"

**Cause:** APP_SECRET environment variable not set

**Solution:**
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --environment Variables="{APP_SECRET=your-secret-here,...}"
```

### Issue 2: "No session cookie found"

**Cause:** 
- User not logged in
- Cookie not being sent with request (CORS issue)
- Cookie expired

**Solution:**
- Check CORS headers include `Access-Control-Allow-Credentials: true`
- Check frontend sets `withCredentials: true`
- User should re-login

### Issue 3: "Invalid session token"

**Cause:**
- APP_SECRET mismatch between Lambdas
- Session expired
- Session corrupted

**Solution:**
```bash
# Ensure APP_SECRET is same across all auth Lambdas
# Get from working Lambda
APP_SECRET=$(aws lambda get-function-configuration \
  --function-name rabbitmiles-me \
  --query 'Environment.Variables.APP_SECRET' \
  --output text)

# Set on all auth Lambdas
for lambda in rabbitmiles-user-update-activities rabbitmiles-me rabbitmiles-auth-callback rabbitmiles-auth-disconnect; do
  echo "Updating $lambda..."
  # Update with your full environment variables
done
```

### Issue 4: "Failed to fetch activities from Strava"

**Cause:**
- Invalid Strava access token
- Token expired
- Strava API error

**Solution:**
- Check CloudWatch for detailed error
- Verify STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET
- User should disconnect and reconnect Strava

### Issue 5: Lambda times out

**Cause:**
- Too many activities to process
- Database slow
- Network issues

**Solution:**
```bash
# Increase Lambda timeout
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --timeout 60  # seconds
```

---

## GitHub Actions Deployment

If using GitHub Actions for deployment:

### Check Workflow Status

1. Go to https://github.com/timhibbard/rabbit-miles/actions
2. Find "Deploy Lambda Functions" workflow
3. Check if latest run succeeded
4. Verify `user_update_activities` job succeeded

### Check GitHub Secrets

The workflow needs this secret:
- `LAMBDA_USER_UPDATE_ACTIVITIES` - Lambda function name in AWS

```bash
# Verify secret exists (requires GitHub CLI or web UI)
gh secret list --repo timhibbard/rabbit-miles | grep LAMBDA_USER_UPDATE_ACTIVITIES
```

### Manual Trigger

If needed, manually trigger deployment:

1. Go to Actions tab
2. Select "Deploy Lambda Functions" workflow
3. Click "Run workflow"
4. Select `main` branch
5. Click "Run workflow" button

---

## Prevention

To prevent this issue in the future:

1. **Always test Lambdas after deployment**
   - Run functional test
   - Check CloudWatch logs
   - Verify environment variables

2. **Use CloudFormation/Terraform for infrastructure**
   - Environment variables in code
   - Consistent across deployments
   - Version controlled

3. **Add integration tests**
   - Test actual Lambda invocation
   - Test with real AWS credentials
   - Run in CI/CD pipeline

4. **Monitor CloudWatch alarms**
   - Alert on Lambda errors
   - Alert on high error rate
   - Alert on missing environment variables

---

## Contact

If issue persists after following this guide:

1. Share CloudWatch logs from a failed request
2. Share Lambda configuration (with secrets redacted)
3. Share exact error message from browser console
4. Share timestamp of failed request

---

**Last Updated:** February 12, 2026  
**Status:** Enhanced logging deployed in commit 183d958  
**Next Steps:** Deploy and verify
