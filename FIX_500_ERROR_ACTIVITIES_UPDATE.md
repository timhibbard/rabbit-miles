# Fix for 500 Error on Activities Update

## Problem
Users were encountering a 500 error when clicking "Refresh Activities from Strava" button in the Settings page.

## Root Cause
The `user_update_activities` Lambda function was missing two critical features that are present in other user-facing API endpoints:

1. **OPTIONS preflight request handling**: When the browser makes a POST request with credentials (cookies) to a cross-origin endpoint, it first sends an OPTIONS preflight request to check CORS permissions. The Lambda was not handling these OPTIONS requests, causing them to fail.

2. **APP_SECRET validation**: The Lambda was not validating that the APP_SECRET environment variable is set before attempting to use it. If APP_SECRET was missing or empty, the session verification would fail silently, returning a confusing authentication error instead of a clear configuration error.

## Solution
Added the missing features to match the pattern used in admin Lambda functions:

### 1. OPTIONS Preflight Handler
```python
# Handle OPTIONS preflight requests for CORS
if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
    print("OPTIONS preflight request - returning CORS headers")
    return {
        "statusCode": 200,
        "headers": {
            **get_cors_headers(),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Cookie",
            "Access-Control-Max-Age": "86400"
        },
        "body": ""
    }
```

This returns proper CORS headers telling the browser that:
- POST and OPTIONS methods are allowed
- Content-Type and Cookie headers can be sent
- The preflight response can be cached for 24 hours (86400 seconds)

### 2. APP_SECRET Validation
```python
if not APP_SECRET:
    print("ERROR: Missing APP_SECRET")
    return {
        "statusCode": 500,
        "headers": get_cors_headers(),
        "body": json.dumps({"error": "server configuration error"})
    }
```

This provides a clear error message if APP_SECRET is not configured, making debugging much easier.

## Files Changed
- `backend/user_update_activities/lambda_function.py` - Added OPTIONS handling and APP_SECRET validation
- `.gitignore` - Added pattern to exclude test files

## Deployment Instructions

### Option 1: Automatic Deployment via GitHub Actions
The fix will be automatically deployed when this PR is merged to main:

1. Merge this PR to `main` branch
2. GitHub Actions will automatically deploy the updated Lambda function
3. No manual steps required

### Option 2: Manual Deployment
If you need to deploy manually before merging:

```bash
# 1. Navigate to the Lambda directory
cd backend/user_update_activities

# 2. Create deployment package
zip -r function.zip lambda_function.py

# 3. Deploy to AWS
aws lambda update-function-code \
  --function-name <YOUR_LAMBDA_FUNCTION_NAME> \
  --zip-file fileb://function.zip

# 4. Clean up
rm function.zip
```

Replace `<YOUR_LAMBDA_FUNCTION_NAME>` with the actual Lambda function name (check GitHub Secrets: `LAMBDA_USER_UPDATE_ACTIVITIES`).

## Verification

### Before Deployment
Run the test suite to verify the fix:

```bash
cd backend/user_update_activities
python3 test_lambda.py
python3 test_options.py
```

Expected output:
- ✓ Lambda returns 500 when APP_SECRET is missing (with clear error message)
- ✓ Lambda returns 401 for invalid session tokens
- ✓ OPTIONS preflight handled correctly
- ✓ POST requests work normally

### After Deployment
1. Log in to https://rabbitmiles.com
2. Go to Settings page
3. Click "Refresh Activities from Strava"
4. Verify that:
   - No 500 error appears
   - Activities are updated successfully
   - Success message shows the number of activities updated

## Environment Variables Required
Ensure these environment variables are set on the Lambda function:

- `DB_CLUSTER_ARN` - Aurora PostgreSQL cluster ARN ✅
- `DB_SECRET_ARN` - Secrets Manager ARN for database credentials ✅
- `DB_NAME` - Database name (default: postgres) ✅
- `APP_SECRET` - Secret key for signing session cookies ✅ ⚠️ **Now validated!**
- `FRONTEND_URL` - Frontend URL for CORS (https://rabbitmiles.com) ✅
- `STRAVA_CLIENT_ID` - Strava OAuth client ID ✅
- `STRAVA_CLIENT_SECRET` - Strava OAuth client secret ✅

The fix adds validation for `APP_SECRET`, which should help catch configuration issues early.

## Technical Details

### Why OPTIONS Preflight?
When a web page makes a cross-origin request with credentials (cookies) and custom content types, the browser performs a "preflight" check:

1. Browser sends OPTIONS request to check if the cross-origin request is allowed
2. Server responds with CORS headers indicating what's permitted
3. If allowed, browser proceeds with the actual POST request
4. If not allowed, browser blocks the request and shows a CORS error

Without OPTIONS handling, step 2 fails, and the browser never sends the actual POST request.

### Why Validate APP_SECRET?
The session cookie authentication relies on HMAC signatures using APP_SECRET as the key. If APP_SECRET is:
- Not set: HMAC uses empty key, creating invalid signatures
- Wrong: Session verification always fails
- Missing: Better to fail fast with clear error than confuse with auth failures

By validating APP_SECRET early, we provide a clear error message that points directly to the configuration issue.

### Pattern Consistency
This fix brings `user_update_activities` in line with other user-facing endpoints:
- `admin_all_activities` ✅ Has OPTIONS + APP_SECRET validation
- `admin_backfill_activities` ✅ Has OPTIONS + APP_SECRET validation
- `admin_delete_user` ✅ Has OPTIONS + APP_SECRET validation
- `admin_list_users` ✅ Has OPTIONS + APP_SECRET validation
- `admin_user_activities` ✅ Has OPTIONS + APP_SECRET validation
- `user_update_activities` ✅ **Now has OPTIONS + APP_SECRET validation**

## Related Documentation
- See `DEPLOYMENT_ACTIVITY_UPDATES.md` for full deployment guide
- See `backend/user_update_activities/lambda_function.py` for implementation
- See admin Lambda functions for reference implementation pattern
