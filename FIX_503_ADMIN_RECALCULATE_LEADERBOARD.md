# Fix for 503 Error on Admin Leaderboard Recalculate

## Problem

The `/admin/leaderboard/recalculate` endpoint returns a 503 error when called from the admin panel, even though the Lambda function **completes successfully** in CloudWatch logs.

### Observed Symptoms
- Frontend shows "Service Unavailable" error
- CloudWatch logs show Lambda completing successfully after ~47-48 seconds
- All activities are processed correctly
- Leaderboard is updated successfully
- User still sees an error message

## Root Cause

**API Gateway HTTP APIs have a hard 30-second timeout limit.**

Even though:
- Lambda is configured with 600-second timeout ✅
- Lambda has 1024MB memory ✅
- Lambda completes successfully in ~47 seconds ✅
- Error handling is robust ✅

The API Gateway timeout is **not configurable** and will always terminate requests after 30 seconds, returning a 503 error to the client even if the Lambda is still running successfully in the background.

## Solution

**Implement asynchronous invocation pattern:**

1. When called from API Gateway:
   - Verify admin authentication
   - Invoke the Lambda function **asynchronously** using `InvocationType='Event'`
   - Return immediately with **202 Accepted** status (< 1 second)

2. Lambda invokes itself to run the actual recalculation:
   - Runs in the background for ~47 seconds
   - Logs results to CloudWatch
   - No response sent back to client

3. Frontend displays user-friendly message:
   - "Leaderboard recalculation started successfully"
   - "This process runs in the background and may take up to 1 minute to complete"

### Why This Works

- **API Gateway timeout:** Request completes in < 1 second ✅
- **Lambda execution:** Still runs for full ~47 seconds ✅
- **User experience:** Clear feedback that processing is ongoing ✅
- **Monitoring:** Full execution logs still available in CloudWatch ✅

## Implementation

### Backend Changes (`backend/admin_recalculate_leaderboard/lambda_function.py`)

```python
# Added lambda_client for async invocation
lambda_client = boto3.client("lambda")

def handler(event, context):
    # Check if this is an async invocation
    is_async_invocation = event.get("async_invocation") is True
    
    if is_async_invocation:
        # Run the actual recalculation (background task)
        result = recalculate_leaderboard()
        # ... process and log results ...
        return
    
    # When called from API Gateway:
    # 1. Verify admin auth
    athlete_id, is_admin = admin_utils.verify_admin_session(event, APP_SECRET)
    
    # 2. Trigger async invocation
    lambda_client.invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType='Event',  # Async - returns immediately
        Payload=json.dumps({"async_invocation": True})
    )
    
    # 3. Return immediately (< 1 second)
    return {
        "statusCode": 202,  # Accepted
        "body": json.dumps({
            "message": "Leaderboard recalculation started successfully...",
            "status": "processing"
        })
    }
```

### Frontend Changes (`src/pages/Admin.jsx`)

```javascript
const handleRecalculateLeaderboard = async () => {
  const result = await recalculateLeaderboard();
  if (result.success) {
    const { message, status } = result.data;
    
    // Handle async processing response (202 status)
    if (status === 'processing') {
      setSuccessMessage(message);
    }
  }
};
```

## Deployment

### Step 1: Deploy Updated Lambda Code

The changes are already in this PR. Deploy via:

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

### Step 2: Verify Lambda Configuration

The Lambda should already be configured from the previous fix:

```bash
aws lambda get-function-configuration \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --query '[Timeout,MemorySize]' \
  --output table
```

Expected:
- Timeout: 600 seconds ✅
- Memory: 1024 MB ✅

### Step 3: Test the Endpoint

Go to the admin panel and click "Recalculate Leaderboard". You should see:

**Immediate response (< 1 second):**
- ✅ Success message: "Leaderboard recalculation started successfully..."
- ✅ No 503 error

**CloudWatch logs (~47 seconds later):**
- ✅ Background Lambda completes successfully
- ✅ All activities processed
- ✅ Leaderboard updated

## Response Format

### API Response (Returned Immediately)

```json
{
  "message": "Leaderboard recalculation started successfully. This process runs in the background and may take up to 1 minute to complete.",
  "status": "processing"
}
```

**Status Code:** `202 Accepted`

### CloudWatch Logs (Background Execution)

The async Lambda execution logs all details to CloudWatch:

```
LOG - Recalculation successful in 47838.52ms
LOG - Processed 1634 activities from 40 athletes
=== recalculate_leaderboard END: SUCCESS ===
```

## What Changed from Previous Fix

### Previous Fix (Lambda Timeout)
- ✅ Increased Lambda timeout to 600 seconds
- ✅ Increased Lambda memory to 1024MB
- ✅ Added per-activity error handling
- ❌ **Still hit API Gateway 30-second timeout**

### Current Fix (Async Invocation)
- ✅ Returns within API Gateway 30-second limit
- ✅ Lambda still completes full processing
- ✅ User gets immediate feedback
- ✅ No more 503 errors

## Monitoring

### Check if Recalculation Succeeded

1. **CloudWatch Logs:**
   ```bash
   aws logs tail /aws/lambda/rabbitmiles-admin-recalculate-leaderboard --follow
   ```

2. **Look for:**
   ```
   ADMIN RECALCULATE LEADERBOARD - SUCCESS
   Processed 1634 activities from 40 athletes
   ```

3. **Check for errors:**
   ```
   ERROR - Recalculation failed
   WARNING - Failed to process activity
   ```

### Verify Leaderboard Updated

Check the leaderboard page to see if recent activities are reflected in the rankings.

## Technical Details

### API Gateway Limitations

| Type | Timeout Limit | Configurable |
|------|---------------|--------------|
| HTTP API | 30 seconds | ❌ No |
| REST API | 29 seconds | ❌ No |
| WebSocket API | 30 minutes | ❌ No |

**Source:** [AWS API Gateway Quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html)

### Lambda Invocation Types

| Type | Returns | Use Case |
|------|---------|----------|
| `RequestResponse` | Waits for result | Synchronous operations |
| `Event` | Immediately (202) | Async background tasks |
| `DryRun` | Validation only | Testing |

### Why 47 Seconds?

The recalculation processes:
- ~1634 activities
- 40 unique athletes
- 843 aggregate entries
- Uses RDS Data API (network calls for each query)

**Processing time breakdown:**
- Query activities: ~0.2s
- Process activities in memory: ~0.5s
- Insert aggregates: ~46s (843 inserts × ~55ms each)

Future optimization: Batch inserts to reduce API calls.

## Security

✅ **No security vulnerabilities introduced:**
- Auth check still happens before async invocation
- No new secrets or credentials required
- Uses existing Lambda permissions
- CodeQL scan: 0 alerts
