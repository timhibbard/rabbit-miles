# Logging Improvements for Cookie Issue Diagnosis

## Problem Summary

From the existing logs, we can see a clear pattern:

### Working Case (Tim Hibbard - Safari):
- ✅ Cookie is present: `Cookies array present: True, count: 1`
- ✅ `rm_session` cookie found and verified
- ✅ User authenticated successfully
- ℹ️ `Sec-Fetch-Storage-Access` header: empty/not present

### Failing Case (New User - Chrome):
- ❌ Cookie is missing: `Cookies array present: False, count: 0`
- ❌ No `rm_session` cookie found
- ❌ Authentication fails with "not authenticated" error
- ⚠️ `Sec-Fetch-Storage-Access: none` - indicates third-party cookies are blocked

## Root Cause Analysis

The issue is **third-party cookie blocking in Chrome**. The authentication flow is:

1. User clicks "Connect with Strava" on GitHub Pages (`timhibbard.github.io`)
2. Redirects to API Gateway (`9zke9jame0.execute-api.us-east-1.amazonaws.com`)
3. Redirects to Strava OAuth
4. Strava redirects back to API Gateway with auth code
5. API Gateway sets `rm_session` cookie (in auth_callback)
6. Redirects user back to GitHub Pages
7. GitHub Pages calls `/me` endpoint on API Gateway
8. **Chrome blocks the cookie from being sent** because it's a cross-site request

Chrome shows `Sec-Fetch-Storage-Access: none` which explicitly indicates that third-party cookies are being blocked.

## Logging Improvements Added

### auth_callback Lambda

Enhanced logging to capture:

1. **Browser Detection**
   - Detects Chrome, Safari, Firefox, Edge
   - Helps correlate cookie issues with specific browsers

2. **Security Headers**
   - `Sec-Fetch-Site`: Shows if request is cross-site
   - `Sec-Fetch-Mode`: Shows the fetch mode (navigate, cors, etc.)
   - `Sec-Fetch-Dest`: Shows destination type
   - `Sec-Fetch-Storage-Access`: **Critical** - shows if third-party cookies are blocked
     - `none`: Cookies blocked
     - `inactive`: Storage Access API available but not active
     - `active`: Storage Access API is active (cookies allowed)

3. **Cookie Setting Details**
   - Full cookie string preview (first 100 chars)
   - Cookie value preview (first 20 and last 10 chars)
   - All cookie attributes (HttpOnly, Secure, SameSite, Path, Max-Age)

4. **Cross-Site Analysis**
   - Request origin
   - API domain
   - Explicit confirmation of cross-site nature
   - SameSite=None requirement

5. **Critical Warnings**
   - When Chrome + `Sec-Fetch-Storage-Access: none` detected
   - Provides user guidance on enabling cookies

### auth_start Lambda

Added logging for:

1. **Browser Detection**
   - Same as auth_callback

2. **Storage Access Header**
   - Logs `Sec-Fetch-Storage-Access` if present
   - Warns if third-party cookies may be blocked

## What to Look for After Deployment

When the new user tries to connect again, check the **auth_callback** logs for:

### Expected Findings:

```
LOG - Browser type detected: Chrome
LOG - Sec-Fetch-Storage-Access: none
WARNING - Sec-Fetch-Storage-Access: none - Browser may be blocking third-party cookies
...
CRITICAL WARNING - Chrome with blocked third-party cookies detected!
CRITICAL WARNING - Cookie will be set but may not be sent on subsequent requests
CRITICAL WARNING - This is the most likely cause of authentication failures
```

### Key Questions to Answer:

1. **Is the cookie being set correctly?**
   - Check `LOG - Full Set-Cookie string:` output
   - Should include: `HttpOnly; Secure; SameSite=None; Path=/; Max-Age=2592000`

2. **What is the Sec-Fetch-Storage-Access value?**
   - `none` = cookies blocked (expected for new user)
   - Empty or not present = cookies may work (like Tim's Safari)

3. **Is the browser Chrome?**
   - Chrome has stricter third-party cookie policies than Safari

4. **Is the cookie value correct?**
   - Check first 20 and last 10 chars match what's logged in auth_callback

## Solution Options

Once we confirm the diagnosis with enhanced logs, here are the potential solutions:

### Option 1: Storage Access API (Recommended)
- Use the Storage Access API in the frontend
- Requires user interaction (button click)
- Most compatible with modern browsers
- Works with Chrome's privacy features

### Option 2: User Instructions
- Guide users to enable third-party cookies for the site
- Not ideal for user experience
- Many users have privacy concerns

### Option 3: Change Architecture
- Move to token-based auth (Authorization header)
- Requires significant refactoring
- Current codebase explicitly uses cookie-based auth per requirements

## Next Steps

1. **Deploy these changes** to the Lambda functions
2. **Have the new user try connecting again**
3. **Review the auth_callback logs** for the new session
4. **Confirm the diagnosis** with the enhanced logging
5. **Implement the appropriate solution** based on findings

## Files Changed

- `backend/auth_callback/lambda_function.py` - Enhanced logging for cookie setting
- `backend/auth_start/lambda_function.py` - Added browser detection and security headers
