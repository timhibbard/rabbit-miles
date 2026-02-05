# Error Loading Activity - CORS Domain Mismatch Fix

## Summary
The frontend successfully migrated to the custom domain `https://rabbitmiles.com`, but the backend Lambda functions were not updated with the new domain, causing CORS policy violations.

## The Error
```
Access to XMLHttpRequest at 'https://api.rabbitmiles.com/activities/363' from origin 'https://rabbitmiles.com' 
has been blocked by CORS policy: The 'Access-Control-Allow-Origin' header has a value 
'https://timhibbard.github.io' that is not equal to the supplied origin.
```

## Root Cause
- **Frontend**: Deployed at `https://rabbitmiles.com` (confirmed by `public/CNAME`)
- **Backend**: Lambda `FRONTEND_URL` env var still set to `https://timhibbard.github.io/rabbit-miles`
- **Result**: Browser receives mismatched CORS origin and blocks API requests

## Why This Happens
Lambda functions extract the origin from `FRONTEND_URL` using:
```python
def get_cors_origin():
    parsed = urlparse(FRONTEND_URL)
    return f"{parsed.scheme}://{parsed.netloc}"
```

When `FRONTEND_URL` = `https://timhibbard.github.io/rabbit-miles`, this returns `https://timhibbard.github.io`.
The browser expects `https://rabbitmiles.com`.

## The Fix
Update the `FRONTEND_URL` environment variable in AWS Lambda from the old domain to the new one.

### Quick Fix (Recommended)
```bash
cd scripts
./update-lambda-frontend-url.sh
```

**Prerequisites:**
- AWS CLI configured with credentials
- Permissions to update Lambda function configurations
- `jq` installed for JSON manipulation

### What Gets Updated
8 Lambda functions that interact with the frontend:
1. `rabbitmiles-auth-start` - OAuth initiation
2. `rabbitmiles-auth-callback` - OAuth callback handling
3. `rabbitmiles-auth-disconnect` - User disconnect
4. `rabbitmiles-me` - User info API
5. `rabbitmiles-get-activities` - Activities list API
6. `rabbitmiles-get-activity-detail` - Single activity API (**this one is failing**)
7. `rabbitmiles-fetch-activities` - Strava sync
8. `rabbitmiles-reset-last-matched` - Admin utility

### Verification
After running the script, test:
```bash
curl -i -H "Origin: https://rabbitmiles.com" https://api.rabbitmiles.com/me
```

Expected headers:
```
Access-Control-Allow-Origin: https://rabbitmiles.com
Access-Control-Allow-Credentials: true
```

Then visit https://rabbitmiles.com/activity/[id] (replace `[id]` with any activity ID) - the error should be resolved.

## Alternative: Manual Update
See [CORS_DOMAIN_FIX.md](./CORS_DOMAIN_FIX.md) for step-by-step manual instructions via AWS Console.

## Files Changed in This PR
- ✅ `scripts/update-lambda-frontend-url.sh` - Automated fix script
- ✅ `CORS_DOMAIN_FIX.md` - Detailed documentation
- ✅ `QUICKFIX_CORS.md` - Quick reference guide

## No Code Changes Required
The Lambda function code is already correct - it properly extracts the origin from `FRONTEND_URL`. This is purely an environment variable configuration issue that must be fixed in AWS Lambda itself.
