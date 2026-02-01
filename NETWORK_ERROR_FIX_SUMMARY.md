# Network Error Fix - Summary

## Issue
Users experienced a "Network Error" when clicking the "Refresh Activities" button on the Dashboard. The browser console showed:
- **Status code**: 500 Internal Server Error
- **CORS errors**: "Origin https://timhibbard.github.io is not allowed by Access-Control-Allow-Origin"
- **Error message**: "XMLHttpRequest cannot load https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/activities/fetch due to access control checks"

## Root Cause
The Lambda functions were accessing environment variables using `os.environ["KEY"]` syntax, which throws a `KeyError` during module initialization if the variable is missing. When a Lambda function fails to initialize (before the handler even runs), API Gateway returns a 500 error **without** the CORS headers that the handler would have set. This causes:

1. **Lambda initialization failure**: Missing environment variables cause Python module load to fail
2. **No CORS headers**: The handler's CORS headers never get set because the handler never runs
3. **Browser CORS error**: Browser blocks the 500 response due to missing CORS headers
4. **Generic error message**: User sees "Network Error" instead of a helpful error message

## Solution
Changed all Lambda functions to safely access environment variables and validate them in the handler:

### Before (Unsafe - Causes Initialization Failure)
```python
# This will throw KeyError if APP_SECRET is not set
APP_SECRET = os.environ["APP_SECRET"].encode()
```

### After (Safe - Allows Initialization to Complete)
```python
# Safe environment variable access with default values
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""

# Validate in handler and return proper error with CORS headers
def handler(event, context):
    cors_headers = get_cors_headers()
    
    if not APP_SECRET:
        print("ERROR: Missing APP_SECRET environment variable")
        return {
            "statusCode": 500,
            "headers": cors_headers,  # CORS headers are included!
            "body": json.dumps({"error": "server configuration error"})
        }
```

## Files Changed

### Backend Lambda Functions (All Fixed)
1. **backend/fetch_activities/lambda_function.py**
   - Safe env var access for: DB_CLUSTER_ARN, DB_SECRET_ARN, APP_SECRET, FRONTEND_URL
   - Handler validation for required env vars
   - Returns 500 with CORS headers if env vars missing

2. **backend/get_activities/lambda_function.py**
   - Safe env var access for: DB_CLUSTER_ARN, DB_SECRET_ARN, APP_SECRET, FRONTEND_URL
   - Handler validation for required env vars
   - Returns 500 with CORS headers if env vars missing

3. **backend/me/lambda_function.py**
   - Safe env var access for: DB_CLUSTER_ARN, DB_SECRET_ARN, APP_SECRET, FRONTEND_URL
   - Handler validation for required env vars
   - Returns 500 with CORS headers if env vars missing

4. **backend/auth_callback/lambda_function.py**
   - Safe env var access for: DB_CLUSTER_ARN, DB_SECRET_ARN, APP_SECRET, API_BASE_URL, FRONTEND_URL
   - Safe cookie path extraction

5. **backend/auth_disconnect/lambda_function.py**
   - Safe env var access for: DB_CLUSTER_ARN, DB_SECRET_ARN, APP_SECRET, API_BASE_URL, FRONTEND_URL
   - Safe cookie path extraction

6. **backend/auth_start/lambda_function.py**
   - Safe env var access for: DB_CLUSTER_ARN, DB_SECRET_ARN, API_BASE_URL
   - Safe cookie path extraction

## Benefits

### Before Fix
❌ Lambda fails to initialize if env vars missing  
❌ API Gateway returns 500 without CORS headers  
❌ Browser shows CORS error  
❌ User sees generic "Network Error"  
❌ No helpful error messages in browser console  
❌ Difficult to debug configuration issues  

### After Fix
✅ Lambda always initializes successfully  
✅ Handler validates env vars and returns proper errors  
✅ All error responses include CORS headers  
✅ Browser receives proper error messages  
✅ Clear error messages in CloudWatch logs  
✅ Easy to identify configuration issues  

## Deployment Instructions

### Step 1: Update Lambda Code

Deploy the updated code to **all 6 Lambda functions**:

```bash
# For each Lambda function:
cd backend/<lambda-name>
zip -r lambda.zip lambda_function.py

aws lambda update-function-code \
  --function-name rabbitmiles-<lambda-name> \
  --zip-file fileb://lambda.zip

cd ../..
```

Replace `<lambda-name>` with:
- `fetch_activities`
- `get_activities`
- `me`
- `auth_callback`
- `auth_disconnect`
- `auth_start`

### Step 2: Verify Environment Variables

**IMPORTANT**: Ensure all required environment variables are set in AWS Lambda console:

#### For fetch_activities, get_activities, me:
- `DB_CLUSTER_ARN` ✅ Required
- `DB_SECRET_ARN` ✅ Required
- `DB_NAME` (optional, defaults to "postgres")
- `APP_SECRET` ✅ Required (must be same across all functions)
- `FRONTEND_URL` ✅ Required (e.g., "https://timhibbard.github.io/rabbit-miles")

#### For auth_callback, auth_disconnect:
- `DB_CLUSTER_ARN` ✅ Required
- `DB_SECRET_ARN` ✅ Required
- `DB_NAME` (optional, defaults to "postgres")
- `APP_SECRET` ✅ Required (must be same across all functions)
- `API_BASE_URL` ✅ Required (e.g., "https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod")
- `FRONTEND_URL` ✅ Required (e.g., "https://timhibbard.github.io/rabbit-miles")
- `STRAVA_CLIENT_ID` ✅ Required
- `STRAVA_CLIENT_SECRET` ✅ Required (or STRAVA_SECRET_ARN)

#### For auth_start:
- `DB_CLUSTER_ARN` ✅ Required
- `DB_SECRET_ARN` ✅ Required
- `DB_NAME` (optional, defaults to "postgres")
- `API_BASE_URL` ✅ Required (e.g., "https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod")
- `STRAVA_CLIENT_ID` ✅ Required

### Step 3: Test the Fix

After deployment, test the endpoint:

1. **Open the application**: Navigate to https://timhibbard.github.io/rabbit-miles
2. **Open browser DevTools**: Press F12
3. **Go to Network tab**: Monitor API requests
4. **Click "Refresh Activities"**: Button on the Dashboard
5. **Verify response**:
   - Status should be 200 (if authenticated) or 401 (if not authenticated)
   - Should NOT see CORS errors
   - Should see proper error messages if any issues

### Step 4: Monitor CloudWatch Logs

If issues persist, check CloudWatch Logs for each Lambda:

```bash
aws logs tail /aws/lambda/rabbitmiles-fetch-activities --follow
```

Look for:
- ✅ "fetch_activities handler called"
- ❌ "ERROR: Missing APP_SECRET environment variable"
- ❌ "ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN environment variable"

## Expected Behavior After Fix

### Scenario 1: All Environment Variables Set Correctly
- ✅ Lambda initializes successfully
- ✅ User can refresh activities
- ✅ Proper success/error messages with CORS headers
- ✅ No browser CORS errors

### Scenario 2: Missing Environment Variables
- ✅ Lambda initializes successfully (no crash)
- ✅ Handler returns 500 error with CORS headers
- ✅ Browser receives error: `{"error": "server configuration error"}`
- ✅ CloudWatch logs show: "ERROR: Missing X environment variable"
- ✅ Easy to identify and fix configuration issue

### Scenario 3: User Not Authenticated
- ✅ Lambda returns 401 with CORS headers
- ✅ Browser receives error: `{"error": "not authenticated"}`
- ✅ User is redirected to Connect Strava page

## Security Review

✅ **CodeQL Security Scan**: Passed with 0 vulnerabilities  
✅ **No secrets exposed**: Error messages are generic  
✅ **Proper CORS handling**: Only allows configured frontend origin  
✅ **Authentication required**: fetch_activities, get_activities, me require valid session  

## Code Review Notes

The code review identified minor code duplication opportunities:
1. Cookie path extraction logic is duplicated across auth Lambda functions
2. Environment variable validation is duplicated across data Lambda functions

These are noted for future refactoring but don't affect the fix's correctness. Lambda functions are intentionally kept self-contained to avoid shared dependencies and reduce cold start times.

## Rollback Plan

If issues occur after deployment, rollback is simple:

```bash
# List previous versions
aws lambda list-versions-by-function --function-name rabbitmiles-fetch-activities

# Rollback to previous version (replace $PREVIOUS_VERSION)
aws lambda update-alias \
  --function-name rabbitmiles-fetch-activities \
  --name prod \
  --function-version $PREVIOUS_VERSION
```

## Monitoring Recommendations

After deployment, monitor for:
- 500 errors (should decrease significantly)
- CloudWatch Logs for "ERROR: Missing" messages
- API Gateway metrics for /activities/fetch endpoint
- User feedback on Dashboard functionality

---

**PR Status**: Ready to merge  
**Security Scan**: ✅ Passed (0 vulnerabilities)  
**Code Review**: ✅ Completed (2 minor non-blocking suggestions)  
**Testing**: Manual testing recommended after deployment  
**Deployment**: Manual AWS Lambda deployment required
