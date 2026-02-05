# Fix Summary: Remove Authorization Header Fallback

## Problem Statement

New users were unable to connect to Strava after completing OAuth authorization. The `/me` endpoint was returning 401 Unauthorized errors, and the browser console showed CORS errors.

### Symptoms
- Existing user (Tim Hibbard) could disconnect and reconnect successfully
- New user (Strava Athlete) existed in the database but couldn't authenticate
- Browser console showed: `Access to XMLHttpRequest blocked by CORS policy: Response to preflight request doesn't pass access control check`
- Lambda logs showed: `No session cookie found`
- Frontend was sending an `Authorization` header with a Bearer token

## Root Cause

The frontend API client was adding an `Authorization` header with a Bearer token from `sessionStorage` as a "fallback for browsers that block third-party cookies." This approach had multiple problems:

1. **CORS Preflight Issues**: The Authorization header is a custom header that triggers CORS preflight (OPTIONS) requests
2. **Cookie Blocking**: When the Authorization header is present, browsers may block cookie transmission
3. **Architecture Violation**: The application is designed for cookie-based authentication only, not token-based authentication
4. **Inconsistent Behavior**: Existing users with valid cookies worked fine, but new users without cookies failed

## Solution

Removed all Authorization header fallback logic to align with the strict cookie-based authentication model:

### Frontend Changes (`src/utils/api.js`)
- Removed Authorization header injection from request interceptor
- Removed logic that read `rm_session` from sessionStorage
- Authentication now relies solely on cookies sent via `withCredentials: true`

### Frontend Changes (`src/pages/ConnectStrava.jsx`)
- Removed session token URL fragment parsing
- Removed sessionStorage token storage
- Removed sessionStorage token clearing from disconnect handler
- URL cleanup now only removes query parameters, not hash fragments

### Backend Changes (`backend/auth_callback/lambda_function.py`)
- Removed session token from URL fragment in redirect
- Redirect now uses clean URL: `/connect?connected=1` instead of `/connect?connected=1#session={token}`

### Backend Changes (`backend/me/lambda_function.py`)
- Renamed `parse_authorization_header` to `check_authorization_header` for clarity
- Function now only logs warnings when Authorization header is detected (but doesn't use it)
- Extracted `extract_cookie_names` helper function to reduce code duplication
- Enhanced logging to show request context (method, path, source IP)
- Improved cookie name logging for better diagnostics

## Authentication Model

The application now strictly follows cookie-based authentication:

### How It Works
1. User clicks "Connect with Strava"
2. Backend `/auth/start` generates random state, stores it in database, and redirects to Strava
3. User authorizes on Strava
4. Strava redirects to `/auth/callback` with code and state
5. Backend validates state, exchanges code for tokens, stores user in database
6. Backend creates signed session cookie (`rm_session`) and sets it with:
   - `HttpOnly`: Prevents JavaScript access (XSS protection)
   - `Secure`: Only sent over HTTPS
   - `SameSite=None`: Allows cross-site cookies (required for API Gateway + GitHub Pages)
   - `Path={COOKIE_PATH}`: Scoped to API Gateway stage
7. Backend redirects to frontend `/connect?connected=1`
8. Frontend calls `/me` with `withCredentials: true` to include cookies
9. Backend verifies cookie, returns user info

### Key Principles
- **No tokens in localStorage or sessionStorage**
- **No tokens in URL parameters**
- **No Authorization headers**
- **Cookies only**, sent automatically by the browser
- **Server-side validation** of HMAC-signed session tokens

## Testing

### What Was Tested
1. ✅ Python syntax validation for both Lambda functions
2. ✅ Frontend build succeeds without errors
3. ✅ CodeQL security scan passes with 0 alerts
4. ✅ Code review feedback addressed

### What Needs Testing
- [ ] New user OAuth flow from start to finish
- [ ] Existing user can still access dashboard
- [ ] Disconnect and reconnect works for existing users
- [ ] CORS headers work correctly in production
- [ ] Cookies are properly set and sent

## Deployment Notes

### Frontend Deployment
1. Build: `npm run build`
2. Deploy `dist/` folder to GitHub Pages

### Backend Deployment
1. Update Lambda functions:
   - `rabbitmiles-me`
   - `rabbitmiles-auth-callback`
2. No environment variable changes needed
3. No API Gateway changes needed

## Security Summary

✅ **No security vulnerabilities introduced**
- CodeQL scan: 0 alerts (Python and JavaScript)
- Removed token storage in sessionStorage (reduces attack surface)
- Maintained httpOnly cookie security
- Enhanced logging without exposing sensitive data

## Monitoring

### Lambda Logs to Watch
The enhanced logging in `/me` Lambda provides:
- Request method, path, and source IP
- Cookie presence indicators (with names only, not values)
- Warning when Authorization header is detected
- Session verification results

### Expected Log Patterns

**Successful Authentication:**
```
Debug - Request method: GET
Debug - Request path: /me
Debug - cookies array present: True, count: 1
Debug - cookie names in array: rm_session
Found session token
Verified session for athlete_id: 123456
Successfully retrieved user from database
```

**Failed Authentication (No Cookie):**
```
Debug - Request method: GET
Debug - Request path: /me
Debug - cookies array present: False, count: 0
Debug - cookie header present: False
No session cookie found
```

**Unexpected Authorization Header:**
```
Warning: Authorization header detected but ignored (cookie-based auth only)
```

## References

- Custom Instructions: "Authentication is cookie-based, not token-based"
- Related Issues: New user cannot connect to Strava
- MDN Web Docs: [HTTP Cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies)
- MDN Web Docs: [CORS Preflight](https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request)
