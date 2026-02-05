# OAuth Callback Domain Fix - Summary

## Problem
New users cannot authenticate because the OAuth callback was configured to use the frontend domain (`timhibbard.github.io`), but the Strava application's Authorization Callback Domain was never updated to allow this domain.

## Solution
Reverted the OAuth callback flow to use the API Gateway domain (`9zke9jame0.execute-api.us-east-1.amazonaws.com`) directly, which is already configured in Strava.

## Changes Made

### Code Changes (Minimal - 3 lines)

**backend/auth_start/lambda_function.py (Line 113):**
```python
# Before:
redirect_uri = f"{FRONTEND}/callback"

# After:
redirect_uri = f"{API_BASE}/auth/callback"
```

**backend/auth_callback/lambda_function.py (Lines 224-227):**
```python
# Before:
redirect_uri = f"{FRONTEND}/callback"

# After:
redirect_uri = f"{API_BASE}/auth/callback"
```

### Documentation Updates

1. **DEPLOYMENT_CALLBACK_DOMAIN_FIX.md** - Complete deployment guide
2. **OAUTH_CALLBACK_UPDATE.md** - Marked previous approach as reverted
3. **README.md** - Updated OAuth flow documentation

## Deployment Steps

### 1. Update Strava Application Settings
In https://www.strava.com/settings/api:
- Set **Authorization Callback Domain** to: `9zke9jame0.execute-api.us-east-1.amazonaws.com`
- Save changes

### 2. Deploy Lambda Functions

```bash
# Deploy auth_start
cd backend/auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://function.zip

# Deploy auth_callback
cd ../auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-callback \
  --zip-file fileb://function.zip
```

### 3. Verify
- Test new user OAuth flow
- Check CloudWatch logs for correct redirect_uri
- Confirm authentication succeeds

## OAuth Flow (After Fix)

```
User clicks "Connect with Strava"
  ↓
Frontend → /auth/start
  ↓
Backend → Strava OAuth
  (redirect_uri = https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback)
  ↓
User authorizes
  ↓
Strava → Backend /auth/callback ✨ (direct, no frontend hop)
  ↓
Backend validates, sets cookie
  ↓
Backend → Frontend /connect?connected=1
```

## Benefits

✅ **Simpler** - Eliminates frontend callback hop
✅ **More reliable** - Direct backend OAuth flow
✅ **Easier to configure** - Only one domain in Strava
✅ **Standard OAuth** - Follows typical patterns
✅ **Faster** - One less redirect

## Quality Assurance

✅ Code review: No issues found
✅ Security scan (CodeQL): 0 vulnerabilities
✅ Changes: Minimal (3 lines changed)
✅ No database changes required
✅ Easy rollback if needed

## Expected Result

New users will be able to complete Strava authentication successfully once:
1. Strava Authorization Callback Domain is set to `9zke9jame0.execute-api.us-east-1.amazonaws.com`
2. Lambda functions are deployed with updated code

## See Also

- **DEPLOYMENT_CALLBACK_DOMAIN_FIX.md** - Complete deployment instructions
- **README.md** - Updated OAuth flow documentation
- **ENV_VARS.md** - Environment variable reference
