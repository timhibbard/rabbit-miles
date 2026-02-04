# Authentication Fix Summary

## Issue
Users could not login with Strava on **any device** (desktop or mobile, Chrome or Safari) after PR #103 was merged.

## Root Cause
PR #103 changed the `SameSite` cookie attribute from `None` to `Lax` in an attempt to fix mobile Safari issues. However, this broke authentication entirely because:

1. **Cross-Origin Architecture**: The frontend and backend are on different domains:
   - Frontend: `https://timhibbard.github.io/rabbit-miles` (GitHub Pages)
   - Backend: `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod` (AWS API Gateway)

2. **SameSite=Lax Behavior**: Cookies with `SameSite=Lax` are NOT sent in cross-site XHR/fetch requests

3. **Authentication Flow Broken**: 
   - User completes OAuth successfully (top-level navigation works)
   - Backend sets `rm_session` cookie
   - Frontend tries to call `/me` API endpoint (cross-site fetch)
   - Browser doesn't include the cookie due to `SameSite=Lax`
   - Backend returns 401 Unauthorized
   - User appears not logged in

## Solution
Reverted `SameSite` attribute back to `None` in all three authentication Lambda functions:
- `backend/auth_start/lambda_function.py`
- `backend/auth_callback/lambda_function.py`
- `backend/auth_disconnect/lambda_function.py`

## Why SameSite=None is Correct

For cookie-based authentication in a **cross-origin architecture**, `SameSite=None` is required to allow cookies in cross-site API requests.

This is **secure** because we also have:
- ✅ `Secure` flag: Cookies only sent over HTTPS
- ✅ `HttpOnly` flag: Cookies not accessible via JavaScript (prevents XSS)
- ✅ CORS policy: Backend only accepts requests from trusted frontend origin
- ✅ Signed cookies: Session tokens use HMAC SHA-256 signatures
- ✅ Short expiration: 30-day token lifetime
- ✅ HTTPS everywhere: Both frontend and backend use HTTPS

## Changes Made

### Files Modified
1. `backend/auth_start/lambda_function.py`
   - Changed `rm_state` cookie from `SameSite=Lax` to `SameSite=None`

2. `backend/auth_callback/lambda_function.py`
   - Changed `rm_session` cookie from `SameSite=Lax` to `SameSite=None`
   - Changed state clear cookie from `SameSite=Lax` to `SameSite=None`

3. `backend/auth_disconnect/lambda_function.py`
   - Changed all cookie clear operations from `SameSite=Lax` to `SameSite=None`

### Files Added
4. `SAMESITE_NONE_REQUIRED.md`
   - Comprehensive documentation explaining why `SameSite=None` is required
   - Details on the cross-origin architecture
   - Security considerations
   - Alternative architectures (not applicable)

5. `AUTH_FIX_SUMMARY.md` (this file)
   - Summary of the issue and fix
   - Deployment instructions

## Security Review
- ✅ **Code Review**: No issues found
- ✅ **CodeQL Security Scan**: No vulnerabilities found
- ✅ **Cookie Security**: All cookies use `HttpOnly; Secure; SameSite=None`
- ✅ **CSRF Protection**: OAuth state validation prevents CSRF attacks
- ✅ **Token Signing**: HMAC SHA-256 prevents token tampering

## Deployment Instructions

After merging this PR, deploy the updated Lambda functions:

```bash
# Deploy auth_start Lambda
cd backend/auth_start
zip -r lambda.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://lambda.zip

# Deploy auth_callback Lambda
cd ../auth_callback
zip -r lambda.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-callback \
  --zip-file fileb://lambda.zip

# Deploy auth_disconnect Lambda
cd ../auth_disconnect
zip -r lambda.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-disconnect \
  --zip-file fileb://lambda.zip
```

Or use the GitHub Actions workflow if available.

## Testing After Deployment

### Desktop Testing
1. Clear browser cookies
2. Navigate to `https://timhibbard.github.io/rabbit-miles`
3. Click "Connect with Strava"
4. Authorize on Strava
5. ✅ Should redirect to dashboard with user profile visible

### Mobile Safari Testing
1. Open Safari on iOS
2. Clear cookies (Settings → Safari → Clear History and Website Data)
3. Navigate to the app
4. Click "Connect with Strava"
5. Authorize on Strava
6. ✅ Should redirect to dashboard with user profile visible

### Other Browsers
Test on:
- Chrome (desktop and mobile)
- Firefox (desktop and mobile)
- Edge (desktop)
- Safari (macOS)

All browsers should work correctly with `SameSite=None; Secure`.

## Verification

After deployment, verify authentication works by:

1. **Check Console Logs**: Open browser DevTools console and look for:
   ```
   Calling /me endpoint...
   /me response: {athlete_id: ..., display_name: "..."}
   ```

2. **Check Cookies**: In DevTools Application/Storage tab, verify cookies are set:
   - `rm_session` with `SameSite=None; Secure; HttpOnly`
   - Cookie domain: `.execute-api.us-east-1.amazonaws.com` or similar

3. **Check Network Tab**: Verify `/me` request includes `Cookie` header with `rm_session`

## Prevention

To prevent similar issues in the future:

1. **Understand Architecture**: Remember that frontend and backend are on different domains
2. **Test Cross-Origin**: Always test authentication changes in the actual environment
3. **Review SameSite Docs**: Consult MDN documentation before changing cookie policies
4. **Security First**: Cross-site cookies require `SameSite=None; Secure`, not `SameSite=Lax`

## References

- [MDN: SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
- [Chrome SameSite cookie policy](https://www.chromium.org/updates/same-site/)
- [SAMESITE_NONE_REQUIRED.md](./SAMESITE_NONE_REQUIRED.md) - Detailed explanation in this repo

## Contact

If authentication still doesn't work after deployment, check:
1. Lambda functions were actually updated (check last modified date)
2. API Gateway is routing to the correct Lambda versions
3. Environment variables are correctly set (APP_SECRET, API_BASE_URL, FRONTEND_URL)
4. Browser cookies are enabled
5. No browser extensions blocking cookies
