# Deployment Checklist - Authentication Fix

Use this checklist to deploy the authentication fix step by step.

## Pre-Deployment Verification

- [ ] You have AWS CLI configured with appropriate credentials
- [ ] You have access to the RDS cluster and can run Data API commands
- [ ] You have access to Lambda functions for deployment
- [ ] You have environment variables documented (see below)

## Environment Variables Reference

### Lambdas Currently Deployed

Get function names:
```bash
aws lambda list-functions --query 'Functions[?contains(FunctionName, `rabbit`) || contains(FunctionName, `strava`)].FunctionName' --output table
```

### Required Environment Variables

For each Lambda, verify environment variables:
```bash
# Check auth_callback Lambda
aws lambda get-function-configuration --function-name YOUR_AUTH_CALLBACK_FUNCTION --query 'Environment.Variables'

# Check me Lambda  
aws lambda get-function-configuration --function-name YOUR_ME_FUNCTION --query 'Environment.Variables'
```

## Deployment Steps

### Step 1: Backup Current State (Optional but Recommended)

```bash
# Export current Lambda configurations
aws lambda get-function --function-name YOUR_AUTH_CALLBACK_FUNCTION > auth_callback_backup.json
aws lambda get-function --function-name YOUR_ME_FUNCTION > me_backup.json
```

### Step 2: Deploy Database Migration (CRITICAL - Do This First)

```bash
# Set environment variables for your RDS cluster
export DB_CLUSTER_ARN="arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:YOUR_CLUSTER"
export DB_SECRET_ARN="arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:YOUR_SECRET"
export DB_NAME="postgres"

# Run the migration
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "$DB_NAME" \
  --sql "$(cat backend/migrations/000_create_users_table.sql)"
```

**Expected Output:**
```json
{
    "numberOfRecordsUpdated": 0
}
```

**Verify Table Creation:**
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "$DB_NAME" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_name = 'users'"
```

**Expected Output:**
```json
{
    "records": [
        [
            {
                "stringValue": "users"
            }
        ]
    ]
}
```

✅ **Step 2 Complete** - Users table created

### Step 3: Deploy auth_callback Lambda

```bash
# Navigate to auth_callback directory
cd backend/auth_callback

# Create deployment package
zip -r function.zip lambda_function.py

# Deploy to Lambda
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION \
  --zip-file fileb://function.zip

# Wait for update to complete
aws lambda wait function-updated \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION

# Verify deployment
aws lambda get-function-configuration \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION \
  --query 'LastModified'
```

✅ **Step 3 Complete** - auth_callback Lambda deployed

### Step 4: Deploy me Lambda

```bash
# Navigate to me directory
cd ../me

# Create deployment package
zip -r function.zip lambda_function.py

# Deploy to Lambda
aws lambda update-function-code \
  --function-name YOUR_ME_FUNCTION \
  --zip-file fileb://function.zip

# Wait for update to complete
aws lambda wait function-updated \
  --function-name YOUR_ME_FUNCTION

# Verify deployment
aws lambda get-function-configuration \
  --function-name YOUR_ME_FUNCTION \
  --query 'LastModified'
```

✅ **Step 4 Complete** - me Lambda deployed

### Step 5: Deploy Frontend (Automatic via GitHub Actions)

The frontend changes will be automatically deployed when this PR is merged to main.

If you need to deploy manually:
```bash
# Build the frontend
npm run build

# The GitHub Actions workflow will handle deployment
# Or manually deploy dist/ to GitHub Pages
```

✅ **Step 5 Complete** - Frontend will auto-deploy

## Post-Deployment Testing

### Test 1: Verify CloudWatch Logs are Working

```bash
# Start tailing logs in one terminal
aws logs tail /aws/lambda/YOUR_ME_FUNCTION --follow

# In another terminal
aws logs tail /aws/lambda/YOUR_AUTH_CALLBACK_FUNCTION --follow
```

### Test 2: Test OAuth Flow

1. **Open browser with DevTools** (F12)
   - [ ] Open Console tab
   - [ ] Open Network tab
   
2. **Clear all cookies** for your app domain
   - [ ] DevTools → Application → Cookies → Delete all

3. **Navigate to** `https://timhibbard.github.io/rabbit-miles/connect`
   - [ ] Page loads
   - [ ] Console shows: "ConnectStrava: User not connected"

4. **Click "Connect with Strava"**
   - [ ] Redirected to Strava OAuth page
   - [ ] URL includes state parameter
   - [ ] Authorize the application

5. **After authorization**
   - [ ] Redirected to `/connect?connected=1`
   - [ ] Page shows "You're Connected!"
   - [ ] Profile picture displays
   - [ ] Display name shows
   - [ ] "Go to Dashboard" button appears
   - [ ] Console shows successful /me call

6. **Check Network tab**
   - [ ] `/auth/callback` returns 302
   - [ ] `Set-Cookie` header includes `rm_session`
   - [ ] `/me` request includes `Cookie` header
   - [ ] `/me` returns 200 with user data

7. **Check CloudWatch Logs**
   
   **auth_callback should show:**
   ```
   Successfully upserted user XXXXX (...) to database
   Created session token for athlete_id: XXXXX
   ```
   
   **me should show:**
   ```
   Cookie header received: True
   Verified session for athlete_id: XXXXX
   Successfully retrieved user from database
   ```

8. **Click "Go to Dashboard"**
   - [ ] Dashboard loads
   - [ ] User info displays
   - [ ] Profile picture shows
   - [ ] Welcome message with name
   - [ ] No errors in console

### Test 3: Verify Session Persistence

1. **Refresh the page**
   - [ ] Still authenticated
   - [ ] User info still shows

2. **Navigate to different pages**
   - [ ] Settings page loads
   - [ ] Can navigate back to Dashboard

3. **Close and reopen browser**
   - [ ] Cookie persists
   - [ ] Still authenticated

## Troubleshooting

If any test fails, see `TROUBLESHOOTING_AUTH.md` for detailed debugging steps.

### Quick Fixes

**"Users table does not exist" error:**
```bash
# Verify migration ran
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "$DB_NAME" \
  --sql "SELECT COUNT(*) FROM users"
```

**Lambda deployment failed:**
```bash
# Check Lambda logs for errors
aws logs tail /aws/lambda/YOUR_FUNCTION_NAME --since 5m
```

**Still getting 401 on /me:**
- Check APP_SECRET is set and same in both Lambdas
- Check cookie is being set in /auth/callback response
- Check cookie is being sent in /me request
- See TROUBLESHOOTING_AUTH.md section C

## Rollback Plan

If you need to rollback:

### Rollback Lambdas
```bash
# List versions
aws lambda list-versions-by-function --function-name YOUR_FUNCTION_NAME

# Rollback to previous version
aws lambda update-function-configuration \
  --function-name YOUR_FUNCTION_NAME \
  --publish-version PREVIOUS_VERSION
```

### Database Migration Cannot Be Rolled Back
The users table is required for the application to work. Do not drop it.

## Success Criteria

All tests pass:
- [x] Database migration completed
- [x] Lambdas deployed successfully  
- [x] OAuth flow works end-to-end
- [x] User info displays on /connect
- [x] User info displays on Dashboard
- [x] Session persists across page loads
- [x] No errors in browser console
- [x] CloudWatch logs show successful operations

## Deployment Complete! 🎉

Once all tests pass, the authentication fix is successfully deployed.

Users can now:
- ✅ Connect with Strava
- ✅ See their profile information
- ✅ Access the Dashboard
- ✅ Navigate the app with persistent authentication

## Next Steps

1. Monitor CloudWatch logs for any errors
2. Check user feedback
3. Consider adding:
   - Health check endpoint
   - Automated tests
   - Database schema versioning
   - Periodic cleanup of oauth_states table
