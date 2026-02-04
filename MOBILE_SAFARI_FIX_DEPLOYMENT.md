# Mobile Safari Authentication Fix - Deployment Guide

## Overview

This fix implements dual authentication (cookies + Authorization header) to resolve Mobile Safari's Intelligent Tracking Prevention (ITP) blocking third-party cookies.

## What Changed

### Backend Changes (6 Lambda Functions)
1. **auth_callback** - Includes session token in URL fragment
2. **me** - Accepts Authorization header
3. **get_activities** - Accepts Authorization header
4. **fetch_activities** - Accepts Authorization header
5. **get_activity_detail** - Accepts Authorization header
6. **reset_last_matched** - Accepts Authorization header

### Frontend Changes
1. **ConnectStrava.jsx** - Extracts token from URL fragment and stores in sessionStorage
2. **api.js** - Sends Authorization header with requests

## Deployment Steps

### 1. Deploy Backend Lambda Functions

Deploy these 6 Lambda functions in AWS:

```bash
cd backend

# Deploy auth_callback
cd auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-callback \
  --zip-file fileb://function.zip
cd ..

# Deploy me
cd me
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-me \
  --zip-file fileb://function.zip
cd ..

# Deploy get_activities
cd get_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-get-activities \
  --zip-file fileb://function.zip
cd ..

# Deploy fetch_activities
cd fetch_activities
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-fetch-activities \
  --zip-file fileb://function.zip
cd ..

# Deploy get_activity_detail
cd get_activity_detail
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-get-activity-detail \
  --zip-file fileb://function.zip
cd ..

# Deploy reset_last_matched
cd reset_last_matched
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-reset-last-matched \
  --zip-file fileb://function.zip
cd ..
```

### 2. Deploy Frontend

```bash
# Build frontend
npm run build

# Deploy to GitHub Pages
# The dist/ folder contains the built assets
# Deploy using your preferred method (e.g., gh-pages, manual commit)
```

### 3. Verify Deployment

#### Test on Desktop Browser (Chrome/Firefox/Safari)
1. Visit https://timhibbard.github.io/rabbit-miles/connect
2. Click "Connect with Strava"
3. Complete OAuth flow
4. **Expected**: Redirect to dashboard, user logged in
5. **Expected**: Cookie-based auth continues to work
6. Check browser DevTools:
   - Network tab: No 401 errors
   - Application → Cookies: `rm_session` cookie present
   - Console: No errors

#### Test on Mobile Safari (iPhone/iPad)
1. Visit connect page in Mobile Safari
2. Click "Connect with Strava"
3. Complete OAuth flow
4. **Expected**: Redirect to dashboard, user logged in
5. **Expected**: Authorization header auth works
6. In Safari Web Inspector (if available):
   - Network tab: No 401 errors
   - Console: Token extracted from URL fragment
   - sessionStorage: `rm_session` token present

#### Debug Mode Testing
Visit: `https://timhibbard.github.io/rabbit-miles/connect?debug=1`

**Expected logs:**
- ✅ "Valid session token found in URL fragment" (Mobile Safari)
- ✅ "Calling /me endpoint..."
- ✅ "/me response received successfully"
- ❌ NO 401 errors

## Verification Checklist

- [ ] All 6 Lambda functions deployed successfully
- [ ] Frontend deployed to GitHub Pages
- [ ] Desktop Chrome: Connect → Dashboard works
- [ ] Desktop Safari: Connect → Dashboard works
- [ ] Desktop Firefox: Connect → Dashboard works
- [ ] Mobile Safari (iPhone): Connect → Dashboard works
- [ ] Mobile Safari (iPad): Connect → Dashboard works
- [ ] No 401 errors in browser console
- [ ] Cookies visible in DevTools (desktop)
- [ ] sessionStorage token present (Mobile Safari)
- [ ] Disconnect works correctly
- [ ] Page refresh maintains authentication

## How It Works

### Desktop Browsers
1. User completes OAuth
2. Backend sets `rm_session` cookie with `SameSite=None; Secure`
3. Backend redirects to frontend with token in URL fragment
4. Frontend extracts and stores token in sessionStorage
5. Frontend sends **both** cookie and Authorization header
6. Backend checks Authorization header first, then cookie
7. Cookie authentication succeeds ✅

### Mobile Safari
1. User completes OAuth
2. Backend sets `rm_session` cookie (blocked by ITP)
3. Backend redirects to frontend with token in URL fragment
4. Frontend extracts and stores token in sessionStorage
5. Frontend sends Authorization header (cookie blocked by ITP)
6. Backend checks Authorization header first ✅
7. Authorization header authentication succeeds ✅

## Security Features

- ✅ Token sent via URL fragment (client-side only, never logged)
- ✅ Token validated with strict regex (min 20 chars + 64 char signature)
- ✅ Empty/whitespace tokens rejected
- ✅ sessionStorage used (cleared on tab close)
- ✅ Authorization header redacted in debug logs
- ✅ Backward compatible with cookie auth
- ✅ CodeQL scan: 0 alerts
- ✅ HMAC-signed tokens (30-day expiration)

## Rollback Plan

If issues occur:

```bash
# Revert Lambda functions to previous version
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --revert-to-version PREVIOUS_VERSION

# Or rollback entire stack
# Restore from previous git commit and redeploy
git revert <commit-sha>
npm run build
# Deploy previous version
```

## Troubleshooting

### Issue: Still getting 401 errors on Mobile Safari

**Check:**
1. Lambda functions deployed successfully
2. URL fragment includes `#session=...`
3. Token stored in sessionStorage
4. Authorization header sent with requests

**Debug:**
```javascript
// In browser console
console.log(sessionStorage.getItem('rm_session'));
// Should show token
```

### Issue: Desktop browsers not working

**Check:**
1. Cookies not blocked
2. Cookie domain/path settings correct
3. CORS headers include Authorization

**Debug:**
```javascript
// Check cookies in DevTools
document.cookie
```

### Issue: Token not extracted from URL

**Check:**
1. URL includes `#session=...` fragment
2. Token format matches regex pattern
3. No JavaScript errors in console

## Environment Variables

Ensure these are set on all Lambda functions:
- `APP_SECRET` - Must be same value across all functions
- `FRONTEND_URL` - Must match GitHub Pages URL exactly
- `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME`
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`

## Testing Commands

```bash
# Test backend Lambda locally (if using SAM)
sam local invoke rabbitmiles-me --event events/me-with-auth-header.json

# Test frontend locally
npm run dev
# Visit http://localhost:5173/connect?debug=1
```

## Success Criteria

✅ Mobile Safari users can successfully authenticate
✅ Desktop browser users unaffected (cookie auth still works)
✅ No new security vulnerabilities
✅ No increase in 401 errors in CloudWatch logs
✅ User feedback confirms fix

## Monitoring

After deployment, monitor:
1. CloudWatch Logs for 401 errors
2. User reports of connection issues
3. Success rate of OAuth flow

## Related Documentation

- `MOBILE_SAFARI_AUTHORIZATION_HEADER_FIX.md` - Technical details
- `SAMESITE_NONE_REQUIRED.md` - Why SameSite=None is needed
- `TROUBLESHOOTING_AUTH.md` - General auth troubleshooting

## Support

If issues persist after deployment:
1. Check CloudWatch logs for detailed error messages
2. Enable debug mode: `?debug=1`
3. Test with different browsers/devices
4. Review Lambda environment variables
5. Verify CORS configuration on API Gateway
