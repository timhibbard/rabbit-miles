# Authentication Troubleshooting Guide

This guide helps debug issues with the Strava OAuth authentication flow and user information display.

## Common Issues and Solutions

### Issue 1: User information not showing after connecting with Strava

**Symptoms:**
- OAuth flow completes successfully
- User is redirected back to the app
- Dashboard shows "Unable to Connect" error or redirects back to /connect
- Browser console shows `/me` endpoint returning 401 or 500

**Root Causes and Solutions:**

#### A. Database Table Issues

**Check:** Look at CloudWatch logs for auth_callback Lambda. If you see database errors mentioning "relation 'users' does not exist" or similar, there may be a database schema issue.

**Solution:**
Check if the users table exists and has the correct schema:
```bash
# Verify table exists
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_name = 'users'"
```

#### B. Cookie Not Being Set

**Check:** 
1. Open browser DevTools → Network tab
2. Find the request to `/auth/callback`
3. Check the Response Headers for `Set-Cookie`
4. Look for `rm_session=...` with `HttpOnly`, `Secure`, `SameSite=Lax`

**Common Issues:**
- Cookie not in response → Lambda not setting cookie correctly
- Cookie set but not stored → Browser blocking third-party cookies (shouldn't happen with SameSite=Lax)
- Cookie domain mismatch → Check FRONTEND_URL matches actual domain

**Solution:**
Verify Lambda environment variables:
- `FRONTEND_URL` should be `https://timhibbard.github.io/rabbit-miles` (no trailing slash)
- `APP_SECRET` must be set and consistent across auth_callback and me Lambdas

#### C. Cookie Not Being Sent to /me Endpoint

**Check:**
1. Open browser DevTools → Network tab
2. Find the request to `/me`
3. Check Request Headers for `Cookie`
4. Look for `rm_session=...`

**Common Issues:**
- Cookie not sent → CORS issue or withCredentials not set
- Different domain → Cookie domain doesn't match
- Expired cookie → Token expired or clock skew

**Solution:**
- Verify `withCredentials: true` in axios config (already set in src/utils/api.js)
- Check CORS headers in /me response include `Access-Control-Allow-Credentials: true`
- Verify `Access-Control-Allow-Origin` matches the frontend origin (not wildcard)

#### D. /me Endpoint Returns 401 or 404

**Check CloudWatch Logs:**

**401 "not authenticated":**
```
Cookie header received: False
```
→ Cookie not sent from browser. See section C above.

**401 "invalid session":**
```
Session token verification failed for token: ...
```
→ Token signature invalid or expired. Check:
- `APP_SECRET` is the same in auth_callback and me Lambdas
- System time is correct (token uses Unix timestamps)

**404 "user not found":**
```
User not found in database for athlete_id: 12345
```
→ User record not created. Check auth_callback logs for database errors.

#### E. /me Endpoint Returns 500

**Check CloudWatch Logs:**

Look for "Unexpected error in /me handler:" followed by the error message and stack trace.

**Common Issues:**
- Database connection error → Check DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME
- RDS Data API permissions → Lambda execution role needs rds-data:ExecuteStatement
- Database query error → Check users table schema matches code expectations

### Issue 2: OAuth Flow Fails with "invalid state"

**Symptoms:**
- User redirected to Strava successfully
- Strava redirects back to callback
- Error: "invalid state"

**Solution:**
See [DEPLOYMENT.md](DEPLOYMENT.md) for OAuth state table migration.

## Debugging Steps

### 1. Check Browser Console

Open DevTools (F12) → Console tab. Look for:
```
Calling /me endpoint...
/me response: {...}
```

Or errors:
```
/me endpoint error: Request failed with status code 401
User not authenticated (401)
```

### 2. Check Network Tab

**For /me endpoint:**
1. Status: Should be 200 (success) or 401 (not authenticated)
2. Request Headers: Should include `Cookie: rm_session=...`
3. Response Headers: Should include CORS headers
4. Response Body: Should be JSON with user data or error

**For /auth/callback:**
1. Status: Should be 302 (redirect)
2. Response Headers: Should include `Set-Cookie: rm_session=...`
3. Location header: Should redirect to `/connect?connected=1`

### 3. Check CloudWatch Logs

#### For auth_callback Lambda:
```bash
aws logs tail /aws/lambda/YOUR_AUTH_CALLBACK_FUNCTION --follow
```

Look for:
- "Successfully upserted user XXXXX (...) to database"
- "Created session token for athlete_id: XXXXX"
- Any error messages

#### For me Lambda:
```bash
aws logs tail /aws/lambda/YOUR_ME_FUNCTION --follow
```

Look for:
- "Cookie header received: True"
- "Verified session for athlete_id: XXXXX"
- "Successfully retrieved user from database"
- Any error messages

### 4. Verify Database State

```bash
# Check if users table exists
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT COUNT(*) FROM users"

# Check specific user exists
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT athlete_id, display_name FROM users WHERE athlete_id = YOUR_ATHLETE_ID"
```

## Quick Diagnosis Flowchart

```
User completes OAuth → Redirected to app
                          ↓
                    Does /connect show success?
                          ↓
        No ←――――――――――――――┴――――――――――――――→ Yes
         ↓                                    ↓
  Check CloudWatch                    Click "Go to Dashboard"
  auth_callback logs                          ↓
         ↓                          Does Dashboard load?
  Database error?                            ↓
         ↓                        No ←――――――┴―――――→ Yes
  Run migration              Check /me in Network    ↓
  (000_create_users_table)            ↓          SUCCESS! ✓
                            Status 401 or 500?
                                      ↓
                            401 → Cookie issue
                                (See section C/D)
                                      ↓
                            500 → Server error
                                (See section E)
```

## Testing After Fix

1. **Clear browser cookies** for the app domain
2. **Open browser DevTools** (F12) → Console and Network tabs
3. **Navigate to** `/connect` page
4. **Click** "Connect with Strava"
5. **Authorize** on Strava
6. **Observe**:
   - Redirected to `/connect?connected=1`
   - Success message with profile picture and name
   - Console logs show successful /me call
7. **Click** "Go to Dashboard"
8. **Verify**:
   - Dashboard loads with user info
   - Profile picture and name displayed
   - No errors in console

## Environment Variables Checklist

### Frontend (.env)
- [ ] `VITE_API_BASE_URL` - Points to API Gateway with /prod stage

### auth_start Lambda
- [ ] `DB_CLUSTER_ARN`
- [ ] `DB_SECRET_ARN`
- [ ] `DB_NAME` (default: postgres)
- [ ] `API_BASE_URL`
- [ ] `STRAVA_CLIENT_ID`

### auth_callback Lambda
- [ ] `DB_CLUSTER_ARN`
- [ ] `DB_SECRET_ARN`
- [ ] `DB_NAME`
- [ ] `API_BASE_URL`
- [ ] `FRONTEND_URL` (https://timhibbard.github.io/rabbit-miles)
- [ ] `APP_SECRET` (long random string)
- [ ] `STRAVA_CLIENT_ID`
- [ ] `STRAVA_CLIENT_SECRET` or `STRAVA_SECRET_ARN`

### me Lambda
- [ ] `DB_CLUSTER_ARN`
- [ ] `DB_SECRET_ARN`
- [ ] `DB_NAME`
- [ ] `APP_SECRET` (MUST match auth_callback)
- [ ] `FRONTEND_URL` (for CORS headers)

## Common Gotchas

1. **APP_SECRET mismatch**: auth_callback and me must use the same APP_SECRET
2. **FRONTEND_URL format**: No trailing slash, include /rabbit-miles path
3. **Cookie domain**: Cookies are set for the API domain, not frontend domain
4. **CORS configuration**: Origin must match exactly, no wildcard with credentials
5. **Database permissions**: Lambda needs rds-data:ExecuteStatement permission
6. **VPC configuration**: Lambdas using RDS Data API should NOT be in a VPC

## Still Having Issues?

If you've gone through this guide and still have issues:

1. **Capture logs**:
   - Browser console output
   - Network tab screenshots for /me and /auth/callback
   - CloudWatch logs for both Lambdas
   
2. **Check the basics**:
   - Are the Lambda functions deployed with the latest code?
   - Are environment variables set correctly?
   - Has the database migration been run?

3. **Test components individually**:
   - Can you query the database directly?
   - Can you manually verify a session token?
   - Does the /me endpoint work with curl?
