# Mobile Safari Cookie Authentication Fix

## Summary

Fixed an issue where mobile Safari users could not authenticate after connecting with Strava. The app would remain on the "Connect with Strava" page instead of redirecting to the dashboard.

## Root Cause

The backend was using `SameSite=None` for cookies, which has compatibility issues with mobile Safari during redirect chains. After the OAuth callback redirected to the frontend, mobile Safari would not properly handle the session cookie.

## Solution

Changed cookie `SameSite` attribute from `None` to `Lax` in all authentication Lambda functions. This provides better compatibility with mobile Safari while maintaining security.

### Why SameSite=Lax Works

`SameSite=Lax` allows cookies to be sent:
- ✅ On same-site requests (frontend to backend API calls)
- ✅ On top-level navigation GET requests (OAuth redirects)
- ✅ Perfect for our OAuth flow where the callback redirects back to frontend

`SameSite=None` was more permissive than needed and caused issues with:
- Mobile Safari's stricter cookie policies
- Cross-site tracking protection
- ITP (Intelligent Tracking Prevention) in WebKit browsers

## Changes Made

### Backend Lambda Functions

1. **backend/auth_callback/lambda_function.py**
   - Session cookie: `SameSite=None` → `SameSite=Lax`
   - State cookie clear: `SameSite=None` → `SameSite=Lax`

2. **backend/auth_start/lambda_function.py**
   - State cookie: `SameSite=None` → `SameSite=Lax`

3. **backend/auth_disconnect/lambda_function.py**
   - All cookie clearing: `SameSite=None` → `SameSite=Lax`

### Documentation

4. **COOKIE_FIX_DEPLOYMENT.md**
   - Updated references to reflect `SameSite=Lax`

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
✅ **Cookie security**: Maintained (HttpOnly, Secure)

### Security Impact
- **Improved**: Reduced cross-site cookie exposure
- **Maintained**: All existing security properties
- **Enhanced**: Better compatibility without compromising security

`SameSite=Lax` is actually more secure than `SameSite=None` as it:
- Prevents CSRF attacks in most scenarios
- Reduces cross-site tracking
- Still allows legitimate same-site and top-level navigation

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

- [MDN: SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
- [WebKit ITP](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/)
- [Chrome SameSite changes](https://www.chromium.org/updates/same-site)

## Questions?

For issues or questions about this fix:
1. Check CloudWatch logs for authentication errors
2. Verify cookies are being set with `SameSite=Lax`
3. Test in multiple browsers to isolate Safari-specific issues
4. Review the TROUBLESHOOTING_AUTH.md guide
