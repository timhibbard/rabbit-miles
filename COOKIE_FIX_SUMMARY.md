# Cookie Authentication Issue - Executive Summary

## Issue Description

After successful Strava OAuth authentication, users were being prompted to connect with Strava again. The authentication flow appeared to complete successfully (auth_callback logs showed "Created session token"), but the `/me` endpoint was returning 401 (not authenticated).

## Root Cause

**API Gateway HTTP API v2 provides cookies in a different format than expected.**

The Lambda functions were reading cookies from `event['headers']['cookie']`, but API Gateway HTTP API v2 provides cookies in `event['cookies']` as an array:

```python
# What the code expected (v1 format):
event = {
    "headers": {
        "cookie": "rm_session=value"
    }
}

# What API Gateway actually sends (v2 format):
event = {
    "cookies": [
        "rm_session=value"
    ],
    "headers": {
        # no 'cookie' key!
    }
}
```

## Impact

- Users could authenticate with Strava but immediately lost authentication
- The session cookie was set correctly and sent by the browser
- API Gateway received the cookie but didn't forward it to Lambda in the expected format
- Lambda couldn't find the cookie and returned 401

## Evidence from Logs

**Browser logs showed:**
- Cookie sent: `Cookie: rm_session=eyJhaWQiOjM1MTk5NjQsImV4cCI6MTc3MjQ3NDA4MX0...`

**Lambda logs showed:**
- `Cookie header received: False`
- `No rm_session cookie found. Cookie header: None`

This confirms the cookie was sent but not accessible to Lambda.

## Solution

Updated all Lambda functions to read cookies from the correct location:

1. **Primary**: Check `event['cookies']` array (v2 format)
2. **Fallback**: Check `event['headers']['cookie']` (v1 format, for backwards compatibility)

### Files Changed

- `backend/me/lambda_function.py` - Session validation endpoint
- `backend/auth_callback/lambda_function.py` - OAuth callback handler
- `backend/auth_disconnect/lambda_function.py` - Logout handler

### Code Changes

**Before:**
```python
cookie_header = event.get("headers", {}).get("cookie")
# Always None in v2 format!
```

**After:**
```python
# Check v2 format first
cookies_array = event.get("cookies") or []
for cookie_str in cookies_array:
    # Parse cookie_str to find rm_session
    
# Fallback to v1 format
cookie_header = event.get("headers", {}).get("cookie")
if not tok and cookie_header:
    # Parse cookie_header to find rm_session
```

## Verification

### Test Results

Created and ran comprehensive unit tests validating:
- ✅ v2 format (cookies array) parsing
- ✅ v1 format (cookie header) parsing  
- ✅ Multiple cookies in single request
- ✅ Cookie precedence (v2 over v1)
- ✅ Missing cookie handling

All tests passed successfully.

### Expected Outcome After Deployment

**CloudWatch Logs (before fix):**
```
Cookie header received: False
No rm_session cookie found. Cookie header: None
```

**CloudWatch Logs (after fix):**
```
Cookies array: ['rm_session=eyJhaWQiOjM1MTk5NjQsImV4cCI6MTc3MjQ3NDA4MX0...']
Cookie header: None
Found rm_session cookie: eyJhaWQiOjM1MTk5NjQs...
Verified session for athlete_id: 3519964
Successfully retrieved user from database
```

## Deployment Required

**Action Required:** The user must deploy the updated Lambda functions to AWS.

See `COOKIE_FIX_DEPLOYMENT.md` for detailed deployment instructions.

### Quick Deploy

```bash
cd backend/me
zip -r function.zip lambda_function.py
aws lambda update-function-code --function-name <ME_FUNCTION> --zip-file fileb://function.zip

cd ../auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code --function-name <CALLBACK_FUNCTION> --zip-file fileb://function.zip

cd ../auth_disconnect
zip -r function.zip lambda_function.py
aws lambda update-function-code --function-name <DISCONNECT_FUNCTION> --zip-file fileb://function.zip
```

## Security Analysis

✅ **No security vulnerabilities introduced** (CodeQL scan: 0 alerts)

- Authentication mechanism unchanged
- Cookie attributes unchanged (HttpOnly, Secure, SameSite)
- Token signing/verification unchanged
- No sensitive data logged

## Why This Happened

API Gateway HTTP API has two payload format versions:
- **v1.0**: Cookies in `event['headers']['cookie']`
- **v2.0**: Cookies in `event['cookies']` array

The Lambda functions were written for v1 format but API Gateway was configured for v2 format.

## Prevention

The updated code now supports both formats, preventing similar issues:
- Works with current v2 format
- Maintains compatibility with v1 format
- Logs cookie source for debugging
- Handles edge cases (multiple cookies, missing cookies)

## Documentation

Created comprehensive documentation:
- `COOKIE_FIX_DEPLOYMENT.md` - Step-by-step deployment guide
- `COOKIE_FIX_SUMMARY.md` - This executive summary
- Inline code comments explaining the logic
- Test suite validating the implementation

## Timeline

1. **Issue Reported**: User authenticated but still prompted to connect
2. **Root Cause Identified**: API Gateway v2 cookie format mismatch
3. **Fix Implemented**: Updated all Lambda functions
4. **Tests Created**: Validated cookie parsing logic
5. **Security Scan**: Passed (0 vulnerabilities)
6. **Documentation**: Created deployment guide
7. **Ready for Deployment**: Awaiting user to deploy to AWS

## Success Criteria

After deployment, verify:
- [ ] User can complete OAuth flow
- [ ] `/me` endpoint returns 200 (not 401)
- [ ] CloudWatch logs show "Cookies array: [...]"
- [ ] User stays authenticated across page refreshes
- [ ] No authentication errors in browser console
