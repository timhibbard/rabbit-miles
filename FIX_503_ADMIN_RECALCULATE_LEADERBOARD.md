# Fix for 503 Error on Admin Leaderboard Recalculate

## Problem

The `/admin/leaderboard/recalculate` endpoint returns a 503 error when called from the admin panel. The error is **intermittent** - it works sometimes but fails other times.

## Root Causes

### 1. Lambda Timeout (Primary Cause)

The Lambda function `rabbitmiles-admin-recalculate-leaderboard` is **timing out** during execution. When the Lambda processes many activities and takes longer than its configured timeout, AWS Lambda terminates the function and API Gateway returns a 503 Service Unavailable error.

**Default Lambda timeout:** 3 seconds (AWS default)  
**Needed timeout:** 10 minutes (600 seconds) for processing large datasets

The timeout is especially likely when:
- There are many activities to process (hundreds or thousands)
- The database queries take longer than usual
- Lambda cold start adds additional latency

### 2. Lack of Error Handling (Secondary Cause)

When a user revokes Strava permissions or has corrupted data, processing their activities could throw an exception, causing the entire recalculation to fail. The original code didn't have per-activity error handling, so one bad user's data would break the calculation for everyone.

## Solution

This PR implements two fixes:

### A. Increase Lambda Timeout and Memory

Configure the Lambda with sufficient resources to process all activities.

### Quick Fix (2 minutes)

1. **Run the configuration script:**
   ```bash
   ./scripts/configure-admin-recalculate-leaderboard-lambda.sh
   ```

   This will:
   - Set timeout to 600 seconds (10 minutes)
   - Set memory to 1024 MB
   - Verify the configuration

2. **Verify the configuration:**
   ```bash
   aws lambda get-function-configuration \
     --function-name rabbitmiles-admin-recalculate-leaderboard \
     --query '[Timeout,MemorySize]' \
     --output table
   ```

3. **Test the endpoint:**
   Go to the admin panel and click "Recalculate Leaderboard". It should now complete successfully, even if some users have revoked permissions or have corrupted data.

### B. Per-Activity Error Handling (Code Changes)

The Lambda code has been updated to handle errors gracefully:

- **Per-activity error handling:** If processing one activity fails, it's skipped and logged, but recalculation continues
- **Per-insert error handling:** If inserting one aggregate fails, it's skipped and logged, but recalculation continues
- **Detailed logging:** All skipped activities and affected athletes are logged to CloudWatch
- **Warning response:** If any items were skipped, the response includes warning details

This ensures that one user's bad data (e.g., from revoking permissions, corrupted timestamps, invalid timezones) doesn't prevent the leaderboard from being recalculated for everyone else.

## Quick Fix

### Step 1: Configure Lambda Timeout (Required)

Run the configuration script:
```bash
./scripts/configure-admin-recalculate-leaderboard-lambda.sh
```

This will:
- Set timeout to 600 seconds (10 minutes)
- Set memory to 1024 MB
- Verify the configuration

### Step 2: Deploy Updated Lambda Code (Required for Error Handling)

The Lambda code has been updated to handle errors gracefully. Deploy it:

```bash
cd backend/admin_recalculate_leaderboard
zip -r function.zip lambda_function.py
zip -j function.zip ../admin_utils.py
zip -j function.zip ../timezone_utils.py

aws lambda update-function-code \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --zip-file fileb://function.zip
```

Or merge this PR and let GitHub Actions deploy automatically.

### Step 3: Test the Endpoint

Go to the admin panel and click "Recalculate Leaderboard". It should now:
- Complete successfully even if some users have bad data
- Show a warning message if any activities were skipped
- Log details to CloudWatch about skipped items

### Alternative: Manual Lambda Configuration

**For timeout/memory (via AWS Console):**

1. **Open AWS Lambda Console**
2. **Find the function:** `rabbitmiles-admin-recalculate-leaderboard`
3. **Go to Configuration → General configuration**
4. **Click Edit**
5. **Set:**
   - Timeout: 600 seconds (10 minutes)
   - Memory: 1024 MB
6. **Click Save**

**For timeout/memory (via AWS CLI):**

```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --timeout 600 \
  --memory-size 1024
```

### If API Gateway Route is Also Missing

If you also get consistent 503 errors (not intermittent), the API Gateway route might be missing too:

1. **Run the route setup script:**
   ```bash
   ./scripts/setup-admin-recalculate-leaderboard-route.sh
   ```

2. **Follow the prompts:**
   - Enter your API Gateway ID when prompted
   - The script will auto-detect your Lambda function name

3. **Verify the route was created:**
   ```bash
   ./scripts/verify-api-gateway-routes.sh
   ```

### Manual Route Setup (if script fails)

If you prefer to set up the route manually via AWS Console:

1. **Open API Gateway** in AWS Console
2. **Navigate to your HTTP API** (rabbitmiles-api)
3. **Create a new route:**
   - Method: `POST`
   - Path: `/admin/leaderboard/recalculate`
   - Integration: Lambda function `rabbitmiles-admin-recalculate-leaderboard`
   - Payload format version: `2.0`
4. **Create OPTIONS route** (for CORS):
   - Method: `OPTIONS`
   - Path: `/admin/leaderboard/recalculate`
   - Integration: Same Lambda function
5. **Add Lambda permissions:**
   ```bash
   aws lambda add-permission \
     --function-name rabbitmiles-admin-recalculate-leaderboard \
     --statement-id apigateway-admin-recalculate-leaderboard \
     --action lambda:InvokeFunction \
     --principal apigateway.amazonaws.com \
     --source-arn "arn:aws:execute-api:REGION:ACCOUNT_ID:API_ID/*/*/admin/leaderboard/recalculate"
   ```

### Testing

After setting up the route, test it works:

```bash
# Get your admin session cookie from browser DevTools
curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
  -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -v
```

Expected response (success with no warnings):
```json
{
  "message": "Leaderboard recalculation completed successfully",
  "activities_processed": 123,
  "athletes_processed": 45,
  "duration_ms": 1234.56
}
```

Expected response (success with warnings):
```json
{
  "message": "Leaderboard recalculation completed with 5 items skipped due to errors",
  "activities_processed": 118,
  "athletes_processed": 45,
  "duration_ms": 1234.56,
  "warnings": {
    "activities_skipped": 3,
    "insert_failed": 2,
    "athletes_with_errors": [456, 789]
  }
}
```

## What Was Fixed

### 1. Lambda Configuration
- Added configuration script to set proper timeout (600s) and memory (1024MB)
- Prevents Lambda from being killed mid-execution

### 2. Error Handling in Lambda Code
- **Per-activity error handling:** Bad activity data no longer breaks the entire recalculation
- **Per-insert error handling:** Database insert failures are logged but don't stop processing
- **Detailed logging:** CloudWatch logs show which activities/athletes had errors
- **Warning response:** Frontend displays count of skipped items

### 3. Frontend Warning Display
- Admin panel now shows warning when items are skipped
- Directs admin to check CloudWatch logs for details

## Prevention

1. **The configuration script** has been added to ensure proper timeout/memory settings
2. **The verification script** has been updated to include the route in expected routes

Run these after any Lambda redeployment:
```bash
./scripts/configure-admin-recalculate-leaderboard-lambda.sh
./scripts/verify-api-gateway-routes.sh
```

## Technical Details

### Why Intermittent?

- **Cold starts:** First invocation after idle period may be slower
- **Variable activity count:** More activities = longer processing time
- **Database latency:** RDS Data API response times can vary

### Why 503 Specifically?

When a Lambda times out, API Gateway doesn't get a response and returns:
- **503 Service Unavailable** - Lambda timed out or throttled
- **504 Gateway Timeout** - API Gateway timed out (30 seconds default)

### Configuration Requirements

- **Minimum:** 300 seconds timeout, 512 MB memory
- **Recommended:** 600 seconds timeout, 1024 MB memory
- **Current Lambda code:** ✅ Working correctly
- **Missing:** ❌ Proper timeout/memory configuration
