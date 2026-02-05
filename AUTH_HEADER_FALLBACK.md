# Authentication Header Fallback Implementation

## Problem

New users were unable to connect to Strava because their browsers blocked third-party cookies. This issue affected users on:
- New devices/browsers (first-time visitors)
- Browsers with strict privacy settings
- Incognito/private browsing mode
- Mobile Safari with Intelligent Tracking Prevention (ITP)

Existing users who reconnected could authenticate successfully because their browsers had already established trust with the API domain.

## Root Cause

Modern browsers implement strict third-party cookie policies to protect user privacy. When a user:
1. Visits the frontend (GitHub Pages): `https://timhibbard.github.io/rabbit-miles`
2. Gets redirected to the backend (API Gateway): `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod`
3. Backend sets cookies and redirects back to frontend

The browser may block cookies from the backend domain because it's considered a "third-party" in this context, especially for first-time visitors.

## Solution

Implemented a dual authentication approach:

### 1. Primary: Cookie-Based Authentication
- Cookies remain the primary authentication mechanism
- Works for most users and browsers
- Attributes: `HttpOnly; Secure; SameSite=None; Path=/prod`

### 2. Fallback: Authorization Header
- Session token included in URL fragment after OAuth callback
- Frontend extracts token from URL and stores in sessionStorage
- API requests include `Authorization: Bearer <token>` header
- Backend already supported this mechanism (it was just not implemented in frontend)

## Changes Made

### Backend: `backend/auth_callback/lambda_function.py`

```python
# Include session token in URL fragment as fallback
redirect_to = f"{FRONTEND}/connect?connected=1#session={session_token}"
```

**Why URL fragment?**
- URL fragments (`#...`) are NOT sent to the server in HTTP requests
- They're only processed by the browser/JavaScript
- Safe for including sensitive tokens
- Not visible in server logs

### Frontend: `src/pages/ConnectStrava.jsx`

```javascript
// Check for session token in URL fragment
if (window.location.hash) {
  const hashParams = new URLSearchParams(window.location.hash.substring(1));
  const sessionToken = hashParams.get('session');
  
  if (sessionToken) {
    // Validate token format (base64.signature pattern)
    // Token must have non-empty base64 payload (minimum 10 chars) and 64-character hex signature
    const tokenPattern = /^[A-Za-z0-9_-]{10,}\.[a-f0-9]{64}$/;
    if (tokenPattern.test(sessionToken)) {
      sessionStorage.setItem('rm_session', sessionToken);
    }
  }
}
```

**Security considerations:**
- Token format validated before storing
- Pattern: `<base64>.<64-char-hex>` (minimum 10-char base64 payload + HMAC signature)
- Base64 portion must be at least 10 characters to prevent empty tokens
- Invalid tokens are rejected

### Frontend: `src/utils/api.js`

```javascript
// Add Authorization header if session token exists
const sessionToken = sessionStorage.getItem('rm_session');
if (sessionToken) {
  config.headers['Authorization'] = `Bearer ${sessionToken}`;
}
```

**Request priority:**
1. Check sessionStorage for token
2. Add Authorization header if token exists
3. Still send cookies (withCredentials: true)
4. Backend accepts either authentication method

## Security Analysis

### ✅ Secure Design
- **URL fragments don't leak**: Not sent to server, not in referrer headers
- **Token validation**: Format validation prevents injection attacks
- **sessionStorage**: Cleared when tab closes, not accessible across tabs/domains
- **HMAC signed tokens**: Cannot be forged without APP_SECRET
- **Time-limited**: Tokens expire after 30 days
- **HTTPS only**: All communication over secure channels

### ✅ Privacy Maintained
- No sensitive data in query parameters (which ARE sent to server)
- No persistent storage (sessionStorage, not localStorage)
- Token cleared on disconnect

### ✅ Backward Compatible
- Existing users with working cookies: no change
- New users: automatically use Authorization header fallback
- No code paths removed, only added

## Authentication Flow

### Cookie-Based (Primary)
```
1. OAuth callback → Backend sets rm_session cookie
2. Frontend calls /me → Cookie sent automatically
3. Backend validates cookie → Success
```

### Authorization Header (Fallback)
```
1. OAuth callback → Backend sets cookie + includes token in URL fragment
2. Frontend extracts token → Stores in sessionStorage
3. Frontend calls /me → Adds Authorization header
4. Backend validates header → Success
```

### Both Methods Work
- Backend checks Authorization header first
- If not present, checks cookies
- Either method results in successful authentication

## Testing Recommendations

### Test Case 1: Cookie-Based (Normal Browser)
1. Open browser with normal settings
2. Connect with Strava
3. Verify cookie is set in browser DevTools
4. Verify /me endpoint works
5. Verify sessionStorage has no token (cookies work)

### Test Case 2: Authorization Header (Cookie-Blocked)
1. Open browser in incognito mode OR with strict privacy settings
2. Connect with Strava
3. Verify cookie may not be set
4. Verify sessionStorage has token
5. Verify /me endpoint works with Authorization header
6. Check Network tab: Authorization header present

### Test Case 3: Disconnect Flow
1. Connect with Strava (either method)
2. Click Disconnect
3. Verify sessionStorage is cleared
4. Verify /me returns 401

## Deployment Notes

### Backend Deployment
- Lambda function: `auth_callback`
- Change: One line (redirect URL includes token fragment)
- Risk: Low (backward compatible, cookies still set)

### Frontend Deployment
- Files changed: `ConnectStrava.jsx`, `api.js`
- Testing: Build and lint passed
- Risk: Low (backward compatible, new logic only runs if fragment present)

## Verification Steps

After deployment:
1. Test with existing user → Should work as before
2. Test with new user in normal browser → Should work with cookies
3. Test with new user in incognito → Should work with Authorization header
4. Check CloudWatch logs for both `/me` and `auth_callback`
5. Verify no errors in browser console

## References

- [SAMESITE_NONE_REQUIRED.md](./SAMESITE_NONE_REQUIRED.md) - Why SameSite=None is required
- [MOBILE_SAFARI_FIX_FINAL.md](./MOBILE_SAFARI_FIX_FINAL.md) - Related Mobile Safari fixes
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Web Storage API Security](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API/Using_the_Web_Storage_API#security)
