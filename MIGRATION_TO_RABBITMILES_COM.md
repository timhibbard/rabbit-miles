# Migration to rabbitmiles.com

This document outlines all the changes required to migrate from `timhibbard.github.io/rabbit-miles` to `rabbitmiles.com`.

## Overview

The RabbitMiles application uses:
- **Frontend**: React SPA hosted on GitHub Pages
- **Backend**: AWS Lambda functions behind API Gateway
- **Authentication**: Cookie-based OAuth flow with Strava

## Changes Made

### 1. Frontend Configuration ✅

- **CNAME File**: Created `public/CNAME` with `rabbitmiles.com` to enable GitHub Pages custom domain
- **Base Path**: Updated `vite.config.js` to change `base` from `/rabbit-miles/` to `/` for root domain

### 2. GitHub Pages Configuration (Manual Steps Required)

After this PR is merged:

1. Navigate to repository Settings → Pages
2. Under "Custom domain", the field should show `rabbitmiles.com`
3. Enable "Enforce HTTPS" once DNS propagation is complete
4. GitHub will automatically verify domain ownership via DNS

### 3. DNS Configuration (Manual Steps Required)

Configure DNS records for rabbitmiles.com:

**For Apex Domain (rabbitmiles.com):**
```
Type: A
Name: @
Value: 185.199.108.153
Value: 185.199.109.153
Value: 185.199.110.153
Value: 185.199.111.153
```

**For WWW Subdomain (www.rabbitmiles.com) - Optional:**
```
Type: CNAME
Name: www
Value: timhibbard.github.io
```

### 4. Strava API Application Settings (Manual Steps Required)

Update your Strava API application at https://www.strava.com/settings/api

**Authorization Callback Domain:**
- **Old**: `timhibbard.github.io`
- **New**: `rabbitmiles.com`

**Authorization Callback URLs:**
The callback URL is handled by the backend Lambda, not the frontend, so the API Gateway URL stays the same. However, ensure your redirect URIs are configured properly:
```
https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback
```

**Application URL (optional but recommended):**
- **Old**: `https://timhibbard.github.io/rabbit-miles`
- **New**: `https://rabbitmiles.com`

### 5. AWS Lambda Environment Variables (Manual Steps Required)

Update the `FRONTEND_URL` environment variable for the following Lambda functions:

**Functions to Update:**
- `rabbitmiles-auth-callback`
- `rabbitmiles-auth-disconnect`
- `rabbitmiles-me`
- `rabbitmiles-get-activities`
- `rabbitmiles-fetch-activities`
- `rabbitmiles-get-activity-detail`

**Using AWS CLI:**
```bash
# Set the new frontend URL
FRONTEND_URL="https://rabbitmiles.com"

# Update auth_callback
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-callback \
  --environment "Variables={FRONTEND_URL=${FRONTEND_URL},...existing variables...}"

# Update auth_disconnect
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-disconnect \
  --environment "Variables={FRONTEND_URL=${FRONTEND_URL},...existing variables...}"

# Update me (and other functions that use FRONTEND_URL for CORS)
aws lambda update-function-configuration \
  --function-name rabbitmiles-me \
  --environment "Variables={FRONTEND_URL=${FRONTEND_URL},...existing variables...}"
```

**Important Notes:**
- The `FRONTEND_URL` is used for:
  - CORS headers (Access-Control-Allow-Origin)
  - OAuth redirect after successful authentication
  - Disconnect redirect
- Keep other environment variables unchanged (DB_CLUSTER_ARN, APP_SECRET, etc.)

### 6. GitHub Actions Secrets (Manual Update Recommended)

While the backend API Gateway URL stays the same initially, you can optionally migrate to a custom API domain.

**Current API URL (still works):**
```
https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod
```

**Recommended: Custom API Domain**

For a fully branded experience, migrate the API to `api.rabbitmiles.com`.

See **[API_MIGRATION_TO_CUSTOM_DOMAIN.md](API_MIGRATION_TO_CUSTOM_DOMAIN.md)** for complete instructions on:
- Setting up SSL certificate in AWS Certificate Manager
- Creating custom domain in API Gateway
- Configuring DNS records
- Updating Lambda environment variables
- Testing the migration

This is optional but recommended for:
- Professional branding
- Cleaner URLs (no `/prod` path needed)
- Same root domain as frontend (improved CORS)
- Future flexibility

## Testing Plan

### 1. Pre-Deployment Testing
- [x] Verify CNAME file is in correct location (`public/CNAME`)
- [x] Verify vite config uses correct base path (`/`)
- [x] Build frontend and verify no errors
- [x] Verify assets use root-relative paths (no `/rabbit-miles/` prefix)

### 2. Post-Deployment Testing

After DNS propagation and Lambda updates:

1. **Verify DNS Resolution:**
   ```bash
   dig rabbitmiles.com
   # Should resolve to GitHub Pages IPs
   ```

2. **Test Frontend Access:**
   - Visit `https://rabbitmiles.com`
   - Verify site loads correctly
   - Check browser console for errors

3. **Test Strava OAuth Flow:**
   - Click "Connect with Strava"
   - Should redirect to Strava authorization
   - After authorization, should redirect back to `https://rabbitmiles.com/connect?connected=1`
   - Verify cookies are set correctly

4. **Test CORS:**
   - Open browser DevTools → Network
   - Verify API requests include correct CORS headers:
     - `Access-Control-Allow-Origin: https://rabbitmiles.com`
     - `Access-Control-Allow-Credentials: true`

5. **Test Disconnect Flow:**
   - Navigate to Settings
   - Click "Disconnect Strava"
   - Should redirect to `https://rabbitmiles.com/?connected=0`
   - Verify session is cleared

## Rollback Plan

If issues occur, you can rollback by:

1. **Revert Frontend Changes:**
   ```bash
   git revert <commit-hash>
   ```

2. **Remove Custom Domain:**
   - GitHub Settings → Pages → Remove custom domain

3. **Restore Lambda Environment Variables:**
   ```bash
   FRONTEND_URL="https://timhibbard.github.io/rabbit-miles"
   # Update Lambda functions back to old URL
   ```

4. **Revert Strava API Settings:**
   - Change Authorization Callback Domain back to `timhibbard.github.io`

## Documentation Updates

The following documentation files reference the old domain and should be updated as needed:
- README.md (example URLs)
- Multiple deployment and troubleshooting guides (for future reference)

However, these updates are not critical for functionality—they are primarily for documentation accuracy.

## Summary

**Critical Changes:**
1. ✅ CNAME file created
2. ✅ Vite base path updated
3. ⚠️ DNS configuration (manual)
4. ⚠️ Lambda FRONTEND_URL environment variables (manual)
5. ⚠️ Strava API application settings (manual)

**Non-Critical Changes:**
- Documentation updates (can be done incrementally)

After completing the manual steps, the application will be fully migrated to rabbitmiles.com.
