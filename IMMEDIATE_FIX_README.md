# IMMEDIATE FIX: Lambda Timeout Configuration

## Quick Summary

✅ **PR #218 deployed correctly** - Code size of 4830 bytes is the **compressed** zip size (correct)

❌ **Lambda timeout is only 3 seconds** - This causes 500 errors when the Lambda times out

## Immediate Fix (Run This Now)

```bash
# Configure the Lambda with proper timeout and memory
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --timeout 60 \
  --memory-size 256
```

**OR** run the helper script:
```bash
./scripts/configure-user-update-activities-lambda.sh
```

## Verify Fix

```bash
./scripts/verify-user-update-activities-deployment.sh
```

You should see:
```
✅ Code size looks correct!
✅ Timeout configuration looks correct!
✅ Memory configuration looks correct!
```

## Test in Browser

1. Go to https://rabbitmiles.com
2. Log in with Strava
3. Go to Settings
4. Click "Refresh Activities from Strava"
5. Should see: **"Success! Updated X activities..."** ✅
6. Not: **"Failed to update activities: Request failed with status code 500"** ❌

## Why This Happened

The GitHub Actions workflow deployed the **code** successfully, but didn't configure the Lambda's **timeout** and **memory** settings. The Lambda was using AWS defaults:
- Timeout: 3 seconds (way too low)
- Memory: 128MB (minimal)

With only 3 seconds, the Lambda gets killed mid-execution when:
- Refreshing Strava access token (~2-5 seconds)
- Fetching activities from Strava (~3-10 seconds)
- Storing activities in database (~5-15 seconds)

**Total time needed:** 10-30 seconds depending on number of activities

**With 3-second timeout:** Lambda killed → 500 error returned

## Long-Term Fix (In This PR)

This PR updates the GitHub Actions workflow to automatically configure timeout and memory on every deployment. After this PR is merged, future deployments will have the correct configuration.

**Files Modified:**
- `.github/workflows/deploy-lambdas.yml` - Adds configuration step
- `scripts/configure-user-update-activities-lambda.sh` - New helper script
- `scripts/verify-user-update-activities-deployment.sh` - Enhanced verification
- `FIX_SUMMARY_LAMBDA_TIMEOUT.md` - Full technical explanation

## If You Get Errors

### Error: "An error occurred (ResourceConflictException)"

**Cause:** Lambda is still being updated from a previous change

**Solution:** Wait 30 seconds and try again

### Error: "An error occurred (AccessDeniedException)"

**Cause:** AWS credentials don't have permission to update Lambda configuration

**Solution:** Ensure you're using AWS credentials with Lambda update permissions

### Still Getting 500 Errors After Fix

1. **Wait 30 seconds** for configuration to apply
2. **Check CloudWatch Logs:**
   ```bash
   aws logs tail /aws/lambda/rabbitmiles-user-update-activities --follow
   ```
3. **Look for different error** - might be environment variable issue
4. **Try disconnecting and reconnecting Strava** - token might be invalid

## Questions?

See full documentation in:
- `FIX_SUMMARY_LAMBDA_TIMEOUT.md` - Technical details
- `TROUBLESHOOTING_USER_UPDATE_ACTIVITIES.md` - General troubleshooting
- `SECURITY_SUMMARY.md` - Security scan results

---

**TL;DR:** Run this command now to fix the 500 errors:
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --timeout 60 \
  --memory-size 256
```
