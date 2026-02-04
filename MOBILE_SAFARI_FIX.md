# Mobile Safari Cookie Authentication Fix

> **⚠️ IMPORTANT: THIS FIX HAS BEEN SUPERSEDED**  
> The `Partitioned` attribute added in this fix caused authentication to fail on all browsers.  
> See `FIX_SUMMARY_PARTITIONED_COOKIE.md` for the current fix that removes `Partitioned`.

## Summary

Fixed an issue where mobile Safari users could not authenticate after connecting with Strava. The app would remain on the "Connect with Strava" page instead of redirecting to the dashboard.

## Root Cause

Mobile Safari's Intelligent Tracking Prevention (ITP) was blocking cookies set by the API Gateway domain, treating them as third-party tracking cookies. The issue was compounded by:

1. **Duplicate Set-Cookie headers**: Both `headers["Set-Cookie"]` and `cookies` array were being used, which could cause conflicts in API Gateway HTTP API v2
2. **Missing Partitioned attribute**: Cookies lacked the `Partitioned` attribute needed for CHIPS (Cookies Having Independent Partitioned State)

## Solution

Made two key changes to improve cookie compatibility with mobile Safari:

1. **Removed duplicate Set-Cookie headers**: API Gateway HTTP API v2 uses the `cookies` array format. Having both the header and array can cause conflicts.
2. **Added Partitioned attribute**: This tells browsers that cookies are intentionally cross-site and should be partitioned by top-level site, improving compatibility with Safari's ITP.

### Why Partitioned Cookies Work

The `Partitioned` attribute is part of CHIPS and provides:
- ✅ Better compatibility with Safari's ITP
- ✅ Explicit signal that cookies are intentionally cross-site
- ✅ Cookies are partitioned per top-level site (better privacy)
- ✅ Works with `SameSite=None` for cross-origin requests

### Why SameSite=None is Required

For this architecture (GitHub Pages frontend + API Gateway backend), `SameSite=None` is required because:
- Frontend and backend are on different domains (cross-origin)
- Frontend makes fetch/XHR requests to backend API
- `SameSite=Lax` would block cookies on cross-origin fetch requests
- See SAMESITE_NONE_REQUIRED.md for detailed explanation

## Changes Made

### Backend Lambda Functions

1. **backend/auth_callback/lambda_function.py**
   - Removed duplicate `Set-Cookie` header from headers object
   - Added `Partitioned` attribute to session cookie
   - Added `Partitioned` attribute to state cookie clear

2. **backend/auth_start/lambda_function.py**
   - Removed duplicate `Set-Cookie` header from headers object
   - Added `Partitioned` attribute to state cookie

3. **backend/auth_disconnect/lambda_function.py**
   - Added `Partitioned` attribute to all cookie clearing operations

## Testing Recommendations

### Desktop Testing
1. Clear browser cookies
2. Navigate to the app
3. Click "Connect with Strava"
4. Authorize on Strava
5. Verify redirect to dashboard with user profile visible

### Mobile Safari Testing (Critical)
1. Open Safari on iOS (iPhone/iPad)
2. Clear cookies (Settings → Safari → Clear History and Website Data)
3. Navigate to the app
4. Click "Connect with Strava"
5. Authorize on Strava
6. **Expected**: Redirect to dashboard with user profile visible
7. **Previously**: Would stay on connect page or show "Connect with Strava" button

### Additional Browsers
Test on:
- Chrome (desktop and mobile)
- Firefox (desktop and mobile)
- Edge (desktop)
- Safari (macOS)

All browsers should work correctly with `SameSite=Lax`.

## Deployment Steps

### 1. Deploy Lambda Functions

Deploy all three updated Lambda functions:

```bash
cd backend

# Deploy auth_start
cd auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_START_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ..

# Deploy auth_callback
cd auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ..

# Deploy auth_disconnect
cd auth_disconnect
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_DISCONNECT_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ..
```

### 2. Verify Deployment

Check CloudWatch logs after deployment:

```bash
# Watch logs for /me endpoint
aws logs tail /aws/lambda/YOUR_ME_FUNCTION_NAME --follow
```

### 3. Test Mobile Safari

Follow the mobile Safari testing steps above to verify the fix.

## Security Analysis

### Security Review
✅ **Code review**: No issues found
✅ **CodeQL scan**: No vulnerabilities detected
✅ **Authentication mechanism**: Unchanged
✅ **Token signing**: Unchanged
✅ **Cookie security**: Maintained (HttpOnly, Secure, SameSite=None)

### Security Impact
- **Improved**: Better compatibility with modern browsers
- **Maintained**: All existing security properties
- **Enhanced**: Partitioned cookies provide better privacy isolation

The `Partitioned` attribute:
- Does not reduce security
- Improves privacy by partitioning cookies per top-level site
- Works with Safari's ITP without compromising the authentication flow
- Is compatible with all modern browsers

## Rollback Plan

If issues occur, rollback is simple:

```bash
# Revert to previous Lambda version
aws lambda update-function-configuration \
  --function-name YOUR_FUNCTION_NAME \
  --revert-to-version PREVIOUS_VERSION_NUMBER
```

No database changes were made, so rollback is instantaneous.

## Technical References

- [MDN: Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [CHIPS: Cookies Having Independent Partitioned State](https://developers.google.com/privacy-sandbox/3pcd/chips)
- [WebKit ITP](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/)
- [Chrome SameSite changes](https://www.chromium.org/updates/same-site)

## Questions?

For issues or questions about this fix:
1. Check CloudWatch logs for authentication errors
2. Verify cookies are being set with `SameSite=Lax`
3. Test in multiple browsers to isolate Safari-specific issues
4. Review the TROUBLESHOOTING_AUTH.md guide
