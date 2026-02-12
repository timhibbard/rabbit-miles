# Deployment Checklist: Activity Update 500 Errors

## Overview
This checklist covers the deployment steps to resolve 500 errors for both user and admin activity update endpoints.

## Issues Resolved

### 1. Admin Activity Update (Fixed in this PR)
- **Endpoint**: `POST /admin/users/{athlete_id}/update-activities`
- **Lambda**: `rabbitmiles-admin-update-activities`
- **Fix**: Added missing `sys.path` setup for `admin_utils` import
- **Status**: ✅ Code fixed, ready to deploy

### 2. User Activity Update (Fixed in PR #217)
- **Endpoint**: `POST /activities/update`
- **Lambda**: `rabbitmiles-user-update-activities`
- **Fix**: Added OPTIONS preflight handler and APP_SECRET validation
- **Status**: ✅ Code fixed (already merged), verify deployment

---

## Deployment Steps

### Step 1: Merge This PR
1. Review and merge this PR to `main` branch
2. GitHub Actions will automatically deploy `admin_update_activities` Lambda

### Step 2: Verify User Lambda Deployment
Check if `user_update_activities` Lambda is running the latest code from PR #217:

```bash
# Check Lambda function last modified date
aws lambda get-function \
  --function-name rabbitmiles-user-update-activities \
  --query 'Configuration.[LastModified,CodeSize]'

# If last modified is before Feb 12, 2026, redeploy:
cd backend/user_update_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-user-update-activities \
  --zip-file fileb://function.zip
```

### Step 3: Verify Environment Variables
Both Lambda functions need these environment variables:

```bash
# Check admin Lambda
aws lambda get-function-configuration \
  --function-name rabbitmiles-admin-update-activities \
  --query 'Environment.Variables'

# Check user Lambda
aws lambda get-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --query 'Environment.Variables'
```

**Required variables**:
- `DB_CLUSTER_ARN`
- `DB_SECRET_ARN`
- `DB_NAME` (default: postgres)
- `APP_SECRET` ⚠️ **Critical - Must be set!**
- `FRONTEND_URL` (https://rabbitmiles.com)
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET` (or `STRAVA_SECRET_ARN`)

**Additional for admin**:
- `ADMIN_ATHLETE_IDS` (comma-separated list)

### Step 4: Test Both Endpoints

#### Test User Endpoint
1. Log in to https://rabbitmiles.com as any user
2. Go to Settings page
3. Click "Refresh Activities from Strava"
4. **Expected**: Success message with activity count
5. **Not**: 500 error dialog

#### Test Admin Endpoint
1. Log in as admin user
2. Go to Admin panel → Users
3. Select any user
4. Click "Update Activities"
5. **Expected**: Success message with activity count
6. **Not**: 500 error

### Step 5: Monitor CloudWatch Logs

#### User Lambda Logs
```bash
aws logs tail /aws/lambda/rabbitmiles-user-update-activities --follow
```

Look for:
- ✅ `user_update_activities handler invoked`
- ✅ `Updating activities for user {id}`
- ✅ `Fetched X activities from Strava`
- ❌ No `ERROR: Missing APP_SECRET`
- ❌ No unhandled exceptions

#### Admin Lambda Logs
```bash
aws logs tail /aws/lambda/rabbitmiles-admin-update-activities --follow
```

Look for:
- ✅ `admin_update_activities handler invoked`
- ✅ `Updating activities for user {id}`
- ✅ `Fetched X activities from Strava`
- ❌ No `ImportError: No module named 'admin_utils'`
- ❌ No unhandled exceptions

---

## Troubleshooting

### If User Endpoint Still Fails (500 Error)

**Symptom**: POST /activities/update returns 500

**Possible Causes**:
1. Lambda not deployed with PR #217 code
2. Missing APP_SECRET environment variable
3. CORS preflight failing

**Solution**:
```bash
# Verify Lambda has OPTIONS handler
aws lambda get-function \
  --function-name rabbitmiles-user-update-activities \
  --query 'Code.Location' | xargs curl -s | grep "OPTIONS"

# If not found, redeploy Lambda from main branch
cd backend/user_update_activities
git checkout main
git pull
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-user-update-activities \
  --zip-file fileb://function.zip

# Verify APP_SECRET is set
aws lambda get-function-configuration \
  --function-name rabbitmiles-user-update-activities \
  --query 'Environment.Variables.APP_SECRET'
```

### If Admin Endpoint Still Fails (500 Error)

**Symptom**: POST /admin/users/{id}/update-activities returns 500

**Possible Causes**:
1. Lambda not deployed with this PR's fix
2. Missing admin_utils.py in deployment package
3. Missing ADMIN_ATHLETE_IDS environment variable

**Solution**:
```bash
# Check CloudWatch Logs for ImportError
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-admin-update-activities \
  --filter-pattern "ImportError" \
  --start-time $(date -d '10 minutes ago' +%s)000

# If ImportError found, ensure admin_utils.py is included
cd backend
zip -r function.zip \
  admin_update_activities/lambda_function.py \
  admin_utils.py

aws lambda update-function-code \
  --function-name rabbitmiles-admin-update-activities \
  --zip-file fileb://function.zip

# Verify ADMIN_ATHLETE_IDS is set
aws lambda get-function-configuration \
  --function-name rabbitmiles-admin-update-activities \
  --query 'Environment.Variables.ADMIN_ATHLETE_IDS'
```

### If Both Endpoints Fail with Same Error

**Symptom**: Both endpoints return 500 with same error message

**Possible Causes**:
1. Database connection issues
2. Strava API credentials invalid
3. Missing shared environment variables

**Solution**:
```bash
# Check database connectivity
aws rds-data execute-statement \
  --resource-arn $DB_CLUSTER_ARN \
  --secret-arn $DB_SECRET_ARN \
  --database postgres \
  --sql "SELECT 1"

# Verify Strava credentials
aws secretsmanager get-secret-value \
  --secret-id $STRAVA_SECRET_ARN \
  --query 'SecretString' --output text

# Check for recent Strava API changes
curl https://www.strava.com/api/v3/athlete \
  -H "Authorization: Bearer $TEST_ACCESS_TOKEN"
```

---

## Success Criteria

✅ **Deployment is successful when**:
1. User can refresh activities from Settings without error
2. Admin can update any user's activities without error
3. No 500 errors in CloudWatch Logs
4. No ImportError messages in logs
5. No "Missing APP_SECRET" errors in logs

---

## Rollback Plan

If issues occur after deployment:

### Rollback Admin Lambda
```bash
aws lambda publish-version \
  --function-name rabbitmiles-admin-update-activities

aws lambda update-alias \
  --function-name rabbitmiles-admin-update-activities \
  --name PROD \
  --function-version <PREVIOUS_VERSION>
```

### Rollback User Lambda
```bash
aws lambda publish-version \
  --function-name rabbitmiles-user-update-activities

aws lambda update-alias \
  --function-name rabbitmiles-user-update-activities \
  --name PROD \
  --function-version <PREVIOUS_VERSION>
```

---

## Related Documentation

- `FIX_SUMMARY_ADMIN_UPDATE_ACTIVITIES.md` - Admin endpoint fix details
- `FIX_SUMMARY_ACTIVITIES_500_ERROR.md` - User endpoint fix details (PR #217)
- `DEPLOYMENT_VERIFICATION_ACTIVITIES_UPDATE.md` - Original user endpoint deployment guide

---

**Last Updated**: February 12, 2026  
**Status**: Ready for deployment ✅
