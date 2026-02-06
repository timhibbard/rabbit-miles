# Activity Detail Admin Access Fix - Deployment Guide

## Summary

Fixed 403 Forbidden error when admin users try to view activity details from the Admin panel. Admin users can now view any user's activity details, while regular users can only view their own activities.

## Changes Made

### Backend Changes

**File**: `backend/get_activity_detail/lambda_function.py`

1. Added `load_admin_athlete_ids()` function to load admin IDs from the `ADMIN_ATHLETE_IDS` environment variable
2. Modified the authorization check to allow access if:
   - User owns the activity, OR
   - User is an admin (athlete_id is in the admin allowlist)
3. Added debug logging for access denied cases
4. Updated docstring to document the `ADMIN_ATHLETE_IDS` environment variable requirement

**File**: `backend/get_activity_detail/test_lambda.py` (new)

1. Created unit tests for the `load_admin_athlete_ids()` function
2. Created tests for the admin authorization logic

## Deployment Steps

### 1. Deploy Lambda Function Code

The `get_activity_detail` Lambda function will be automatically deployed via GitHub Actions when this PR is merged to `main`.

**Function Name**: `rabbitmiles-get-activity-detail`

### 2. Set Environment Variable

⚠️ **CRITICAL**: You must add the `ADMIN_ATHLETE_IDS` environment variable to the Lambda function.

#### Via AWS Console:
1. Go to AWS Lambda console
2. Select `rabbitmiles-get-activity-detail` function
3. Go to Configuration → Environment variables
4. Click Edit
5. Add a new variable:
   - **Key**: `ADMIN_ATHLETE_IDS`
   - **Value**: Comma-separated list of admin athlete IDs (e.g., `3519964,12345,67890`)
6. Click Save

#### Via AWS CLI:
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-get-activity-detail \
  --environment Variables="{
    DB_CLUSTER_ARN=${DB_CLUSTER_ARN},
    DB_SECRET_ARN=${DB_SECRET_ARN},
    DB_NAME=postgres,
    APP_SECRET=${APP_SECRET},
    FRONTEND_URL=https://rabbitmiles.com,
    ADMIN_ATHLETE_IDS=3519964,12345,67890
  }"
```

**Note**: Replace the values with your actual configuration. The admin athlete IDs should be the Strava athlete IDs of users who should have admin access.

### 3. Verify Existing Environment Variables

Ensure the following environment variables are already set on the Lambda (these were required before this change):

| Variable | Description |
|----------|-------------|
| `DB_CLUSTER_ARN` | Aurora Serverless cluster ARN |
| `DB_SECRET_ARN` | Database credentials secret ARN |
| `DB_NAME` | Database name (default: `postgres`) |
| `APP_SECRET` | Secret key for session verification (must match `auth_callback` and `me` Lambdas) |
| `FRONTEND_URL` | Frontend URL for CORS (e.g., `https://rabbitmiles.com`) |

### 4. Verify IAM Permissions

The Lambda execution role should have these permissions (no changes needed):
- `rds-data:ExecuteStatement` - for database queries
- `secretsmanager:GetSecretValue` - for accessing database credentials

## Testing

### Manual Testing Steps

1. **As an admin user**:
   - Log in to the application
   - Navigate to the Admin panel (`/admin`)
   - Select a user from the list
   - Click on any activity
   - Verify that the activity detail page loads successfully
   - Verify you can see the activity map, stats, and trail data

2. **As a regular user**:
   - Log in as a non-admin user
   - Navigate to the Dashboard
   - Click on your own activity
   - Verify it loads correctly
   - Try to manually navigate to another user's activity (e.g., `/activity/123` where 123 belongs to another user)
   - Verify you get a 403 Forbidden error

### Automated Tests

Run the unit tests:
```bash
cd backend/get_activity_detail
python3 test_lambda.py
```

Expected output:
```
================================================================================
Running get_activity_detail tests
================================================================================

Testing load_admin_athlete_ids...
✓ Valid IDs loaded correctly
✓ IDs with whitespace loaded correctly
✓ Empty string returns empty set
✓ Invalid IDs skipped correctly
✅ load_admin_athlete_ids tests passed

Testing admin authorization logic...
✓ Regular user can access their own activity
✓ Regular user cannot access another user's activity
✓ Admin can access their own activity
✓ Admin can access another user's activity
✅ Admin authorization logic tests passed

================================================================================
✅ ALL TESTS PASSED
================================================================================
```

## Rollback Plan

If issues occur after deployment:

1. **Immediate**: Remove the `ADMIN_ATHLETE_IDS` environment variable
   - This will cause the Lambda to treat all users as non-admins
   - Regular users can still access their own activities
   - Admins will temporarily lose the ability to view other users' activities

2. **Full rollback**: Revert the Lambda function code to the previous version using AWS Console:
   - Go to Lambda console → `rabbitmiles-get-activity-detail`
   - Click "Versions" tab
   - Find the previous version
   - Click "Actions" → "Publish new version" to restore

## Security Considerations

- **Access Control**: Only users whose `athlete_id` is in the `ADMIN_ATHLETE_IDS` environment variable can view other users' activities
- **Regular Users**: Regular users can only view their own activities (existing behavior preserved)
- **Logging**: Access denied attempts are logged to CloudWatch with the user's athlete_id and the activity's athlete_id for audit purposes
- **No Frontend Changes**: The frontend does not need to be updated; it already sends proper authentication cookies

## CloudWatch Logs

After deployment, you can verify the fix is working by checking CloudWatch logs:

### Success (admin viewing another user's activity):
```
LOG - Access granted to activity 123 for athlete 3519964 (admin)
```

### Denied (regular user trying to view another user's activity):
```
LOG - Access denied: athlete_id=11111, activity_athlete_id=22222, is_admin=False
```

## Related Files

- `backend/get_activity_detail/lambda_function.py` - Lambda function implementation
- `backend/get_activity_detail/test_lambda.py` - Unit tests
- `backend/admin_utils.py` - Shared admin utility functions (used by other admin Lambdas)
- `src/pages/Admin.jsx` - Frontend Admin panel (no changes needed)

## Environment Variable Documentation

This change has been documented in:
- This deployment guide
- The Lambda function docstring
- Code comments

The `ENV_VARS.md` file should be updated to include `ADMIN_ATHLETE_IDS` for the `get_activity_detail` Lambda.

---

**Deployed**: [Date will be filled when deployed]
**Deployed by**: [Name will be filled when deployed]
**Version**: 1.0.0
