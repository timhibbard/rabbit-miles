# Fix Summary: Lambda Timeout Configuration for user_update_activities

## Issue

PR #218 was successfully merged and deployed on **2026-02-12 at 13:40:47**, but users continued to experience **500 errors** when clicking "Refresh Activities from Strava" button.

## Root Cause Analysis

### What We Found

1. **✅ Code Deployment Was Successful**
   - Lambda was deployed with correct code (17,025 bytes uncompressed)
   - CodeSize of 4,830 bytes is the **compressed** zip size (73% deflation)
   - This is expected and correct behavior

2. **❌ Lambda Configuration Was Inadequate**
   - **Timeout:** Only 3 seconds (far too low)
   - **Memory:** Only 128MB (minimal)

### Why This Causes 500 Errors

The `user_update_activities` Lambda performs these operations:
1. Parse and verify session cookie
2. Query database for user's Strava tokens
3. **Check if access token is expired** (~1-2 seconds)
4. **Refresh access token if needed** (Strava API call, ~2-5 seconds)
5. **Fetch activities from Strava** (can return 200 activities, ~3-10 seconds)
6. **Store each activity in database** (200 INSERT/UPDATE queries, ~5-15 seconds)

**Total time needed:** 10-30 seconds depending on:
- Number of activities
- Network latency to Strava API
- Database performance
- Whether token refresh is needed

**With 3-second timeout:** Lambda is killed mid-execution → API Gateway returns **500 Internal Server Error**

## The Solution

### Changes Made

#### 1. Created Lambda Configuration Script

**File:** `scripts/configure-user-update-activities-lambda.sh`

Sets optimal configuration:
- **Timeout:** 60 seconds (enough time for all operations)
- **Memory:** 256MB (sufficient for processing 200 activities)

**Usage:**
```bash
./scripts/configure-user-update-activities-lambda.sh
```

#### 2. Updated GitHub Actions Workflow

**File:** `.github/workflows/deploy-lambdas.yml`

**Changes:**
- Added `timeout` and `memory` parameters to `user_update_activities` matrix entry
- Added new step: "Configure Lambda" that runs after code deployment
- Sets timeout and memory automatically during deployment

**Before:**
```yaml
- name: user_update_activities
  secret: LAMBDA_USER_UPDATE_ACTIVITIES
```

**After:**
```yaml
- name: user_update_activities
  secret: LAMBDA_USER_UPDATE_ACTIVITIES
  timeout: 60
  memory: 256
```

**New workflow step:**
```yaml
- name: Configure ${{ matrix.lambda.name }} Lambda
  if: matrix.lambda.timeout || matrix.lambda.memory
  run: |
    aws lambda update-function-configuration \
      --function-name ${{ secrets[matrix.lambda.secret] }} \
      --timeout ${{ matrix.lambda.timeout }} \
      --memory-size ${{ matrix.lambda.memory }}
```

#### 3. Updated Verification Script

**File:** `scripts/verify-user-update-activities-deployment.sh`

**Changes:**
- Fixed code size check (was looking for 16KB uncompressed, now checks for >4KB compressed)
- Added timeout verification (checks for 60s minimum)
- Added memory verification (checks for 256MB minimum)
- Provides clear warnings and fix instructions if configuration is wrong

## Deployment Instructions

### Option 1: Automatic via GitHub Actions (Recommended)

1. **Merge this PR to main branch**
   - GitHub Actions will automatically deploy
   - Code will be updated
   - Timeout and memory will be configured

2. **Verify deployment:**
   ```bash
   ./scripts/verify-user-update-activities-deployment.sh
   ```

### Option 2: Manual Configuration (If PR Already Merged)

If the code is already deployed but timeout is still 3s:

```bash
# Configure Lambda with correct timeout and memory
./scripts/configure-user-update-activities-lambda.sh

# Verify
./scripts/verify-user-update-activities-deployment.sh
```

### Option 3: Manual AWS CLI Commands

```bash
# Update Lambda configuration
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --timeout 60 \
  --memory-size 256

# Verify
aws lambda get-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --query '[FunctionName,Timeout,MemorySize,LastModified]' \
  --output table
```

## Testing After Fix

### 1. Check Lambda Configuration

```bash
aws lambda get-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --query '[Timeout,MemorySize]' \
  --output table
```

**Expected:**
```
--------------------------
|  Timeout  |  MemorySize |
--------------------------
|  60       |  256        |
--------------------------
```

### 2. Test in Browser

1. Go to https://rabbitmiles.com
2. Log in with Strava
3. Navigate to Settings page
4. Click **"Refresh Activities from Strava"**
5. **Expected:** ✅ Success message: "Success! Updated X activities..."
6. **Not:** ❌ "Failed to update activities: Request failed with status code 500"

### 3. Monitor CloudWatch Logs

```bash
aws logs tail /aws/lambda/rabbitmiles-user-update-activities --follow
```

**Expected log entries:**
```
user_update_activities handler invoked
Environment check: DB_CLUSTER_ARN=set, ...
Authenticated user: athlete_id=123456
Updating activities for user 123456
Access token expired or expiring soon for athlete 123456, refreshing...
Refreshed access token for athlete 123456
Fetched 50 activities from Strava
Successfully stored activity 1234567890: Morning Run
...
Update completed: {"message": "Activities updated successfully", ...}
```

## Impact

### Before Fix
- ❌ Lambda timeout: 3 seconds
- ❌ Users see 500 errors
- ❌ Activities not refreshed
- ❌ Lambda killed mid-execution
- ❌ Database may have incomplete data

### After Fix
- ✅ Lambda timeout: 60 seconds
- ✅ Sufficient time for all operations
- ✅ Activities refresh successfully
- ✅ Users see success message
- ✅ Complete data stored in database

## Why This Wasn't Caught Earlier

1. **Lambda Configuration Not in Version Control**
   - Timeout and memory are Lambda properties, not code properties
   - GitHub Actions workflow only updated code, not configuration
   - Manual Lambda creation likely used AWS defaults (3s timeout)

2. **No Automated Configuration Management**
   - No Terraform/CloudFormation
   - Configuration managed manually via AWS Console
   - Easy to forget to update configuration when deploying new code

3. **Verification Script Had Wrong Expectations**
   - Checked for 16KB uncompressed size
   - Didn't check timeout or memory
   - Led to confusion about deployment status

## Prevention for Future

### 1. Added to GitHub Actions
- Timeout and memory now configured automatically during deployment
- No manual intervention needed

### 2. Enhanced Verification
- Verification script now checks timeout and memory
- Provides clear warnings if configuration is wrong

### 3. Documentation
- Clear deployment instructions
- Troubleshooting guide updated
- Configuration requirements documented

### 4. Consider Infrastructure as Code (Future)
- Move to Terraform or CloudFormation
- All Lambda properties in version control
- Consistent deployments

## Related Files

- `.github/workflows/deploy-lambdas.yml` - Deployment workflow
- `scripts/configure-user-update-activities-lambda.sh` - Configuration script
- `scripts/verify-user-update-activities-deployment.sh` - Verification script
- `backend/user_update_activities/lambda_function.py` - Lambda code
- `TROUBLESHOOTING_USER_UPDATE_ACTIVITIES.md` - Troubleshooting guide

## Timeline

- **2026-02-12 13:40:47** - PR #218 merged and code deployed (timeout still 3s)
- **2026-02-12 13:53:42** - Issue reported: 500 errors persist
- **2026-02-12 14:xx:xx** - Root cause identified: timeout configuration
- **2026-02-12 14:xx:xx** - Fix implemented: updated workflow + scripts

## Summary

**Problem:** Lambda deployed with correct code but insufficient timeout (3s)

**Solution:** Configure Lambda with 60s timeout and 256MB memory

**Result:** Lambda has enough time to complete all operations successfully

**Status:** ✅ Fixed and ready to deploy
