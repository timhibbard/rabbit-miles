# CORS Error Fix - Domain Migration

## ⚠️ ACTION REQUIRED

This fix requires updating AWS Lambda environment variables. Please run the provided script with AWS credentials configured.

## Problem

The frontend has migrated to `https://rabbitmiles.com` (custom domain) but the backend Lambda functions still have `FRONTEND_URL` environment variable set to the old GitHub Pages URL (`https://timhibbard.github.io/rabbit-miles`).

This causes CORS errors:
```
Access to XMLHttpRequest at 'https://api.rabbitmiles.com/activities/363' from origin 'https://rabbitmiles.com' 
has been blocked by CORS policy: The 'Access-Control-Allow-Origin' header has a value 
'https://timhibbard.github.io' that is not equal to the supplied origin.
```

## Root Cause

Lambda functions use the `FRONTEND_URL` environment variable to set the `Access-Control-Allow-Origin` header. The code extracts the origin (scheme + host) from this URL using the `get_cors_origin()` function.

Currently:
- Frontend sends: `Origin: https://rabbitmiles.com`
- Backend returns: `Access-Control-Allow-Origin: https://timhibbard.github.io`
- Result: ❌ Browser blocks the request

## Solution

Update the `FRONTEND_URL` environment variable in AWS Lambda from the old domain to the new custom domain.

### Affected Lambda Functions

These Lambda functions use `FRONTEND_URL` for CORS headers or OAuth redirects:
- `rabbitmiles-auth-start` (OAuth flow)
- `rabbitmiles-auth-callback` (OAuth flow)
- `rabbitmiles-auth-disconnect` (OAuth flow)
- `rabbitmiles-me` (API with CORS)
- `rabbitmiles-get-activities` (API with CORS)
- `rabbitmiles-get-activity-detail` (API with CORS)
- `rabbitmiles-fetch-activities` (API with CORS)
- `rabbitmiles-reset-last-matched` (API with CORS)

### Fix Steps

#### Option 1: Using the provided script (recommended)

```bash
cd scripts
./update-lambda-frontend-url.sh
```

This script will:
1. Check current `FRONTEND_URL` value for each function
2. Update it to `https://rabbitmiles.com`
3. Preserve all other environment variables

#### Option 2: Manual update via AWS Console

For each Lambda function listed above:
1. Go to AWS Lambda Console
2. Select the function
3. Navigate to **Configuration** → **Environment variables**
4. Click **Edit**
5. Change `FRONTEND_URL` from `https://timhibbard.github.io/rabbit-miles` to `https://rabbitmiles.com`
6. Click **Save**

#### Option 3: Using AWS CLI directly

```bash
# For each function, update the FRONTEND_URL variable
aws lambda update-function-configuration \
  --function-name rabbitmiles-get-activity-detail \
  --environment Variables="{
    FRONTEND_URL=https://rabbitmiles.com,
    DB_CLUSTER_ARN=$(existing value),
    DB_SECRET_ARN=$(existing value),
    DB_NAME=$(existing value),
    APP_SECRET=$(existing value)
  }"
```

**Note:** You must include all existing environment variables or they will be removed.

### Verification

After updating, verify the fix:

```bash
# Test CORS headers
curl -i -H "Origin: https://rabbitmiles.com" https://api.rabbitmiles.com/me

# Expected response headers should include:
# Access-Control-Allow-Origin: https://rabbitmiles.com
# Access-Control-Allow-Credentials: true
```

Or visit https://rabbitmiles.com/activity/363 and check browser console - the CORS error should be gone.

## Technical Details

The Lambda functions use this pattern to handle CORS:

```python
def get_cors_origin():
    """Extract origin (scheme + host) from FRONTEND_URL"""
    if not FRONTEND_URL:
        return None
    parsed = urlparse(FRONTEND_URL)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
```

This correctly extracts `https://rabbitmiles.com` from `FRONTEND_URL` and uses it in the `Access-Control-Allow-Origin` header, which matches what the browser sends in the `Origin` header.
