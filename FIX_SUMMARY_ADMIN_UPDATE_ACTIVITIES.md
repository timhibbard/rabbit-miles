# Fix Summary: Admin Update Activities 500 Error

**Status**: ✅ COMPLETE  
**Date**: February 12, 2026  
**Issue**: Admin endpoint for updating user activities returns 500 error

---

## Problem Statement

Admin users encounter a 500 error when attempting to update activities for any user via the admin interface. The endpoint `POST /admin/users/{athlete_id}/update-activities` fails immediately upon invocation.

## Root Cause

The `admin_update_activities` Lambda function (located at `backend/admin_update_activities/lambda_function.py`) imports the shared `admin_utils` module but fails to configure the Python path correctly.

### What Went Wrong

```python
# ❌ INCORRECT - Missing sys.path setup
import boto3
from admin_utils import is_admin, audit_log_admin_action
```

When the Lambda runs in AWS, it cannot find the `admin_utils` module because:
1. The module is in the parent directory (`backend/admin_utils.py`)
2. Python's import system doesn't check parent directories by default
3. This causes an `ImportError` which manifests as a 500 error to the user

### Correct Pattern

All other admin Lambda functions use this pattern:

```python
# ✅ CORRECT - Adds parent directory to path
import sys
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
from admin_utils import is_admin, audit_log_admin_action
```

## Solution Implemented

### Code Changes

**File**: `backend/admin_update_activities/lambda_function.py`

**Before** (Lines 12-21):
```python
import os
import json
import time
import base64
import hmac
import hashlib
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import boto3
from admin_utils import is_admin, audit_log_admin_action
```

**After** (Lines 12-27):
```python
import os
import sys
import json
import time
import base64
import hmac
import hashlib
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import boto3

# Add parent directory to path to import admin_utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from admin_utils import is_admin, audit_log_admin_action
```

### What Changed
- ✅ Added `import sys`
- ✅ Added 3 lines to compute parent directory path
- ✅ Insert parent directory into `sys.path` before import
- ✅ Moved `admin_utils` import to separate line after path setup

### Lines Changed
- **Total**: 6 lines added
- **Files modified**: 1 file
- **Impact**: Minimal, surgical fix

## Verification

### Code Review
✅ **Passed** - No issues found

### Security Scan (CodeQL)
✅ **Passed** - 0 security alerts

### Pattern Consistency
All admin Lambda functions now follow the same pattern:
- ✅ `admin_all_activities` - Uses parent path setup
- ✅ `admin_backfill_activities` - Uses parent path setup
- ✅ `admin_delete_user` - Uses parent path setup
- ✅ `admin_list_users` - Uses parent path setup
- ✅ `admin_update_activities` - **Now fixed** - Uses parent path setup
- ✅ `admin_user_activities` - Uses parent path setup

## Deployment

### Prerequisites
Ensure the Lambda has these environment variables configured:
- `DB_CLUSTER_ARN`
- `DB_SECRET_ARN`
- `DB_NAME` (default: postgres)
- `APP_SECRET` ⚠️ **Critical**
- `FRONTEND_URL` (https://rabbitmiles.com)
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET` (or `STRAVA_SECRET_ARN`)
- `ADMIN_ATHLETE_IDS` (comma-separated list of admin athlete IDs)

### Deployment Methods

#### Method 1: Automatic (Recommended)
1. Merge this PR to `main` branch
2. GitHub Actions automatically deploys via `.github/workflows/deploy-lambdas.yml`
3. Monitor workflow for success

#### Method 2: Manual
```bash
cd backend/admin_update_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-admin-update-activities \
  --zip-file fileb://function.zip
```

**Note**: If using manual deployment, ensure `admin_utils.py` is included:
```bash
cd backend
zip -r function.zip admin_update_activities/lambda_function.py admin_utils.py
```

### Post-Deployment Testing

#### Test 1: Verify Import Works
Check CloudWatch Logs for the Lambda. After deployment:
- ❌ Should NOT see: `ImportError: No module named 'admin_utils'`
- ✅ Should see: `admin_update_activities handler invoked`

#### Test 2: Functional Test (Admin User)
1. Log in to https://rabbitmiles.com as an admin user
2. Navigate to Admin panel → Users
3. Select a user
4. Click "Update Activities" button
5. **Expected**: Success message showing number of activities updated
6. **Not**: 500 error

#### Test 3: API Test
```bash
# Get session cookie from browser after logging in as admin
SESSION_COOKIE="your-session-cookie-here"

curl -X POST https://api.rabbitmiles.com/admin/users/123456/update-activities \
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

## Related Issues

### User Activity Update
The `user_update_activities` Lambda (endpoint `POST /activities/update`) was already fixed in PR #217 to:
- Handle OPTIONS preflight requests for CORS
- Validate APP_SECRET environment variable

If users are still experiencing 500 errors on that endpoint, verify the Lambda has been redeployed with the latest code from PR #217.

## Impact

### Before Fix
- ❌ Admin cannot update user activities
- ❌ 500 error on every attempt
- ❌ ImportError in CloudWatch Logs
- ❌ No admin functionality for activity management

### After Fix
- ✅ Admin can successfully update user activities
- ✅ Consistent with other admin endpoints
- ✅ Clean imports, no errors
- ✅ Full admin functionality restored

## Risk Assessment

### Low Risk
- ✅ Small, focused change (6 lines)
- ✅ Pattern proven in 5 other admin Lambda functions
- ✅ No changes to business logic
- ✅ No database schema changes
- ✅ No changes to authentication mechanism
- ✅ No changes to Strava API integration

### Zero Security Impact
- ✅ No new vulnerabilities (CodeQL scan: 0 alerts)
- ✅ No changes to security controls
- ✅ Authentication unchanged
- ✅ Authorization unchanged

## Rollback Plan

If issues occur after deployment:

### Quick Rollback
```bash
aws lambda update-alias \
  --function-name rabbitmiles-admin-update-activities \
  --name PROD \
  --function-version <PREVIOUS_VERSION>
```

### Full Rollback
1. Revert PR merge commit on GitHub
2. Push to `main`
3. GitHub Actions redeploys previous version

## Monitoring

Monitor for 24-48 hours after deployment:

### CloudWatch Metrics
- ✅ Invocation count increases (when admins use the feature)
- ✅ Error rate drops to ~0%
- ✅ Duration remains similar (~2-5 seconds)

### CloudWatch Logs
Look for:
- ✅ `admin_update_activities handler invoked`
- ✅ `Updating activities for user {athlete_id}`
- ✅ `Fetched X activities from Strava`
- ✅ `Successfully stored activity {id}`
- ❌ No `ImportError` messages
- ❌ No unhandled exceptions

### Admin Experience
- ✅ No 500 error reports
- ✅ Successful activity update reports
- ✅ Audit logs showing admin actions

## Files Modified

```
backend/admin_update_activities/lambda_function.py | +6 lines
FIX_SUMMARY_ADMIN_UPDATE_ACTIVITIES.md            | +250 lines (new)
```

Total: 1 file modified, 1 file created, ~256 lines added

## Success Criteria

Deployment is successful when:
- ✅ Lambda can import `admin_utils` without errors
- ✅ Admin POST requests return 200 with data (not 500)
- ✅ CloudWatch Logs show no ImportError
- ✅ Admin users can update activities for any user
- ✅ Audit logs capture admin actions

---

## Next Steps

1. **Review** this summary
2. **Merge** PR to main branch
3. **Monitor** GitHub Actions deployment
4. **Verify** Lambda environment variables
5. **Test** admin functionality
6. **Monitor** CloudWatch Logs for 24-48 hours

## Questions?

- CloudWatch Logs: `/aws/lambda/rabbitmiles-admin-update-activities`
- GitHub Actions: `.github/workflows/deploy-lambdas.yml`
- Related Fix: `FIX_SUMMARY_ACTIVITIES_500_ERROR.md` (for user endpoint)

---

**Prepared by**: GitHub Copilot  
**Date**: February 12, 2026  
**Status**: Ready for deployment ✅
