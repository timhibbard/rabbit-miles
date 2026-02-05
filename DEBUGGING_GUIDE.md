# RabbitMiles Debugging Guide - New User Login Issues

This guide provides comprehensive strategies for debugging authentication issues when new users cannot log in.

## Quick Diagnosis Checklist

Use this checklist to quickly identify the problem area:

### 1. Environment Variables ✅
- [ ] All required environment variables are set (see [ENV_VARS.md](ENV_VARS.md))
- [ ] `APP_SECRET` is identical across auth_callback, me, and auth_disconnect Lambdas
- [ ] `FRONTEND_URL` has no trailing slash and matches across all Lambdas
- [ ] `API_BASE_URL` includes the stage (e.g., `/prod`)
- [ ] `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` are correctly set

### 2. Database Setup ✅
- [ ] `oauth_states` table exists (migration 001)
- [ ] `users` table exists with correct schema
- [ ] Database is accessible from Lambda (check security groups if in VPC - but Lambdas should NOT be in VPC for RDS Data API)
- [ ] Lambda has `rds-data:ExecuteStatement` permission

### 3. IAM Permissions ✅
- [ ] Lambda execution role has `rds-data:ExecuteStatement`
- [ ] Lambda execution role has `secretsmanager:GetSecretValue`
- [ ] Lambda execution role has CloudWatch Logs permissions

### 4. API Gateway Configuration ✅
- [ ] Routes are configured correctly (GET /auth/start, GET /auth/callback, GET /me, GET /auth/disconnect)
- [ ] Routes are connected to correct Lambda integrations
- [ ] CORS is configured if needed (usually not for Lambda proxy integrations)

### 5. Frontend Configuration ✅
- [ ] `.env` file has correct `VITE_API_BASE_URL`
- [ ] Frontend is making requests with `credentials: 'include'` (for cookies)
- [ ] Frontend code is built and deployed (`npm run build`)

---

## Detailed Debugging Strategies

### Strategy 1: Follow the OAuth Flow Step-by-Step

The complete OAuth flow is:
1. User clicks "Connect with Strava" → Frontend redirects to `/auth/start`
2. `/auth/start` generates state, stores in DB, sets cookie, redirects to Strava
3. User authorizes on Strava
4. Strava redirects to `/auth/callback` with code and state
5. `/auth/callback` validates state, exchanges code for tokens, creates user, sets session cookie, redirects to frontend
6. Frontend calls `/me` to get user info
7. `/me` validates session cookie and returns user data

**Debugging approach**: Follow each step and verify it works before moving to the next.

#### Step 1: Test /auth/start

**Manual test**:
```bash
# Visit in browser (or use curl with -L to follow redirects)
curl -v "https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/start"
```

**Expected behavior**:
- HTTP 302 redirect to Strava OAuth page
- `Set-Cookie` header with `rm_state=...` cookie
- Location header pointing to `https://www.strava.com/oauth/authorize?...`

**Check CloudWatch logs** (`/aws/lambda/rabbitmiles-auth-start`):
```
============================================================================
AUTH START LAMBDA - START
============================================================================
LOG - Environment configuration:
LOG -   FRONTEND_URL: https://timhibbard.github.io/rabbit-miles
LOG -   API_BASE_URL: https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod
LOG -   STRAVA_CLIENT_ID: 123456...
LOG - State token generated: ...
LOG - State stored successfully in oauth_states table
LOG - OAuth redirect_uri: https://timhibbard.github.io/rabbit-miles/callback
LOG - Setting rm_state cookie:
...
============================================================================
AUTH START LAMBDA - SUCCESS
============================================================================
```

**Common issues**:
- ❌ "ERROR - FRONTEND_URL environment variable not set" → Set FRONTEND_URL
- ❌ "ERROR - STRAVA_CLIENT_ID environment variable not set" → Set STRAVA_CLIENT_ID
- ❌ "ERROR - Failed to store state in database" → Check database connection and oauth_states table
- ❌ No redirect to Strava → Check API Gateway route configuration

#### Step 2: Verify State Storage

**Check database**:
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT state, expires_at, created_at FROM oauth_states ORDER BY created_at DESC LIMIT 5"
```

**Expected**: Recent state entries with future expires_at timestamps

**Common issues**:
- ❌ Table doesn't exist → Run migration 001
- ❌ No entries → Lambda can't write to database (check IAM permissions)
- ❌ Permission denied → Lambda execution role missing `rds-data:ExecuteStatement`

#### Step 3: Test Complete OAuth Flow

**Manual test**:
1. Open browser in incognito/private mode (clean slate)
2. Open DevTools (F12) → Network tab
3. Navigate to `https://timhibbard.github.io/rabbit-miles/connect`
4. Click "Connect with Strava"
5. Authorize on Strava
6. Observe redirect back to frontend

**Check each request in Network tab**:

**Request 1: /auth/start**
- Status: 302
- Set-Cookie: `rm_state=...`
- Location: Strava URL

**Request 2: Strava authorization page**
- User sees authorization prompt

**Request 3: /auth/callback** (after user clicks "Authorize")
- Status: 200 (HTML page) or 302 (redirect)
- Set-Cookie: `rm_session=...`
- Set-Cookie: `rm_state=; Max-Age=0` (clearing state cookie)

**Check /auth/callback logs**:
```
============================================================================
AUTH CALLBACK LAMBDA - START
============================================================================
LOG - Query string parameters: code=True, state=True, error=None
LOG - OAuth code present: abc123...xyz789 (length: 64)
LOG - OAuth state present: def456...uvw012 (length: 32)
LOG - State validation SUCCESS via database
LOG - Exchanging OAuth code for tokens with Strava
LOG - Strava response status: 200
LOG - Extracted from Strava response:
LOG -   access_token: True (length: 40)
LOG -   refresh_token: True (length: 40)
LOG -   athlete_id: 12345678
LOG - Database upsert SUCCESS for user 12345678 (John Doe)
LOG - Session token created successfully
LOG - Cookie configuration:
...
============================================================================
AUTH CALLBACK LAMBDA - SUCCESS
============================================================================
```

**Common issues**:
- ❌ "ERROR - Missing required parameters" → State or code not in query string (Strava redirect failed)
- ❌ "ERROR - State validation FAILED" → State not in database or expired (check clock sync, oauth_states table)
- ❌ "ERROR - Token exchange failed" → Invalid Strava credentials, wrong redirect_uri, or network issue
- ❌ "ERROR - Missing required fields in token response" → Strava API returned unexpected response
- ❌ Database error during upsert → Check users table exists and Lambda has permissions

#### Step 4: Test /me Endpoint

After successful OAuth, the frontend calls `/me` to get user info.

**Manual test** (must have valid session cookie from previous step):
```bash
# Use browser DevTools → Console
fetch('https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/me', {
  method: 'GET',
  credentials: 'include'  // Important: send cookies
})
  .then(r => r.json())
  .then(console.log)
  .catch(console.error)
```

**Expected response**:
```json
{
  "athlete_id": 12345678,
  "display_name": "John Doe",
  "profile_picture": "https://..."
}
```

**Check /me logs**:
```
============================================================================
/ME LAMBDA - START
============================================================================
LOG - Environment variables OK
LOG - Cookie analysis:
LOG -   Cookies array present: True, count: 1
LOG -   Cookie header present: True
LOG - Session token found!
LOG -   Token length: 120 chars
LOG - Session token verification SUCCESS
LOG - Verified athlete_id: 12345678
LOG - User found in database!
LOG - User data:
LOG -   athlete_id: 12345678
LOG -   display_name: John Doe
...
============================================================================
/ME LAMBDA - SUCCESS
============================================================================
```

**Common issues**:
- ❌ 401 "not authenticated" + "No session cookie found" → Cookie not sent from browser
  - Check `credentials: 'include'` in frontend
  - Check cookie was actually set in /auth/callback response
  - Check browser cookie storage (DevTools → Application → Cookies)
- ❌ 401 "invalid session" → Token signature/expiration check failed
  - Verify `APP_SECRET` matches between auth_callback and me Lambda
  - Check system time (token uses Unix timestamps)
- ❌ 404 "user not found" → User record not in database
  - Check auth_callback logs for database errors
  - Verify users table exists
  - Check user was actually created (query database)
- ❌ 500 "internal server error" → Unexpected error
  - Check CloudWatch logs for full stack trace
  - Common causes: database connection, missing env vars, code errors

---

### Strategy 2: Check Cookies in Browser

Cookies are the authentication mechanism. If cookies aren't working, nothing will work.

#### Where to Look

**Chrome/Edge**:
1. Open DevTools (F12)
2. Go to Application tab
3. Expand Cookies in left sidebar
4. Look for cookies on both:
   - `https://timhibbard.github.io` (frontend domain)
   - `https://9zke9jame0.execute-api.us-east-1.amazonaws.com` (API Gateway domain)

**Firefox**:
1. Open DevTools (F12)
2. Go to Storage tab
3. Expand Cookies
4. Check both domains

#### What to Look For

After successful OAuth (/auth/callback), you should see on the API Gateway domain:
- `rm_session` cookie with:
  - Long value (100+ characters)
  - HttpOnly: ✅ Yes
  - Secure: ✅ Yes
  - SameSite: None
  - Partitioned: ✅ Yes (in Chrome)
  - Path: /
  - Expires: ~30 days in future

You should NOT see:
- `rm_state` cookie (should be cleared after callback)
- Any cookies on the frontend domain (auth cookies are on API domain only)

#### Common Cookie Issues

**Issue 1: Cookie not set at all**
- **Cause**: Lambda not returning cookie in response
- **Fix**: Check /auth/callback logs to confirm cookie is in response
- **Fix**: Check API Gateway is configured to handle `cookies` array (HTTP API v2 format)

**Issue 2: Cookie set but not stored**
- **Cause**: Browser blocking third-party cookies
- **Fix**: This shouldn't happen with SameSite=None and Partitioned attributes
- **Fix**: Check browser settings (Privacy → Cookies)
- **Fix**: Try different browser for testing

**Issue 3: Cookie not sent to /me**
- **Cause**: Frontend not including credentials in request
- **Fix**: Verify `credentials: 'include'` in fetch/axios config
- **Fix**: Check CORS headers include `Access-Control-Allow-Credentials: true`

**Issue 4: Cookie domain mismatch**
- **Cause**: Cookie set for wrong domain
- **Fix**: Cookies should be on API Gateway domain, not frontend domain
- **Fix**: This is automatic with cross-origin requests + Secure + SameSite=None

---

### Strategy 3: Compare Working vs Broken User Flow

If some users can log in but new users cannot, compare the two flows.

#### Capture Working User Flow

1. **Have a working user log out** (clear cookies in DevTools)
2. **Capture full flow**:
   - CloudWatch logs for all three auth Lambdas
   - Browser Network tab (save as HAR file)
   - Browser Cookie storage screenshots
3. **Note specific values**:
   - State token length and format
   - Session token length and format
   - Redirect URLs
   - Cookie attributes

#### Capture Broken User Flow

1. **Have new user attempt to log in**
2. **Capture same data** as working user
3. **Compare side-by-side**

#### What to Compare

| Aspect | Working User | New User | Notes |
|--------|-------------|----------|-------|
| State cookie set? | ✅ Yes | ? | Check /auth/start response |
| State in database? | ✅ Yes | ? | Query oauth_states table |
| OAuth redirect URL | https://... | ? | Should be identical |
| Strava callback successful? | ✅ Yes | ? | Check query params |
| Session cookie set? | ✅ Yes | ? | Check /auth/callback response |
| Session cookie stored? | ✅ Yes | ? | Check browser storage |
| Session cookie sent to /me? | ✅ Yes | ? | Check /me request headers |
| User in database? | ✅ Yes | ? | Query users table |

---

### Strategy 4: Test Individual Components

Test each component in isolation to identify which one is failing.

#### Test 1: Database Connection

```bash
# Test database is accessible
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT 1"

# Expected output: {"numberOfRecordsUpdated": 0, "records": [[{"longValue": 1}]]}
```

#### Test 2: Lambda Can Write to Database

**Invoke auth_start and check if state is stored**:
```bash
# Invoke Lambda
aws lambda invoke \
  --function-name rabbitmiles-auth-start \
  --payload '{"requestContext":{"http":{"method":"GET"}},"headers":{}}' \
  /tmp/response.json

# Check response
cat /tmp/response.json

# Check if state was written to database
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT COUNT(*) FROM oauth_states"
```

#### Test 3: Session Token Creation/Verification

**Create a test token using Python** (must use same APP_SECRET):
```python
import os
import json
import time
import hmac
import hashlib
import base64

APP_SECRET = os.environ.get("APP_SECRET", "").encode()
athlete_id = 12345678  # Test athlete ID

# Create token (same logic as auth_callback)
payload = {"aid": athlete_id, "exp": int(time.time()) + 30 * 24 * 3600}
b = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
sig = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
token = f"{b}.{sig}"

print(f"Test token: {token}")

# Verify token (same logic as me Lambda)
b2, sig2 = token.rsplit(".", 1)
expected = hmac.new(APP_SECRET, b2.encode(), hashlib.sha256).hexdigest()
print(f"Signature valid: {hmac.compare_digest(sig2, expected)}")
```

If signature doesn't verify, `APP_SECRET` is different between Lambdas!

#### Test 4: Strava API Connection

**Test token exchange manually** (after getting a code from OAuth flow):
```bash
# You need a valid OAuth code from Strava (only valid for a few minutes)
code="<code-from-oauth-callback>"

curl -X POST "https://www.strava.com/oauth/token" \
  -d "client_id=$STRAVA_CLIENT_ID" \
  -d "client_secret=$STRAVA_CLIENT_SECRET" \
  -d "code=$code" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=https://timhibbard.github.io/rabbit-miles/callback"
```

**Expected**: JSON response with access_token, refresh_token, athlete data

**Common issues**:
- Invalid code (expired or already used)
- Wrong redirect_uri (must exactly match auth_start)
- Wrong client_id or client_secret

---

### Strategy 5: Enable Verbose Logging

The Lambdas already have extensive logging. To view logs:

#### Real-time Log Tailing

```bash
# Tail logs for auth_start
aws logs tail /aws/lambda/rabbitmiles-auth-start --follow

# Tail logs for auth_callback
aws logs tail /aws/lambda/rabbitmiles-auth-callback --follow

# Tail logs for me
aws logs tail /aws/lambda/rabbitmiles-me --follow

# Tail all auth-related logs
aws logs tail /aws/lambda/rabbitmiles-auth-start /aws/lambda/rabbitmiles-auth-callback /aws/lambda/rabbitmiles-me --follow
```

#### Search Logs for Specific User

```bash
# Search for specific athlete_id
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-auth-callback \
  --filter-pattern "12345678"

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-auth-callback \
  --filter-pattern "ERROR"

# Search for specific state token
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-auth-start \
  --filter-pattern "abc123xyz"
```

#### What to Look For in Logs

**Success patterns**:
- `AUTH START LAMBDA - SUCCESS`
- `AUTH CALLBACK LAMBDA - SUCCESS`
- `/ME LAMBDA - SUCCESS`
- `State stored successfully`
- `Database upsert SUCCESS`
- `Session token created successfully`

**Failure patterns**:
- `ERROR - ...` (any error message)
- `FAILED` (failure indication)
- `Missing required fields`
- `Database error`
- `Token exchange failed`
- `State validation FAILED`

---

### Strategy 6: Verify Frontend Configuration

The frontend must be configured correctly to work with the backend.

#### Check Environment Variables

```bash
# In project root
cat .env

# Should see:
# VITE_API_BASE_URL=https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod
```

#### Check API Client Configuration

```javascript
// src/utils/api.js should have:
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true,  // CRITICAL: must be true for cookies
  headers: {
    'Content-Type': 'application/json'
  }
});
```

#### Check Frontend is Built with Latest Code

```bash
# Rebuild frontend
npm run build

# Deploy to GitHub Pages (if using gh-pages)
npm run deploy

# Or commit and push dist/ folder if deploying that way
git add dist/
git commit -m "Rebuild frontend"
git push
```

#### Test Frontend API Calls

Open browser console on the frontend page:
```javascript
// Test /me endpoint
fetch('https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/me', {
  method: 'GET',
  credentials: 'include'
})
  .then(r => r.json())
  .then(data => console.log('Success:', data))
  .catch(err => console.error('Error:', err))

// Check what cookies are being sent
fetch('https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/me', {
  method: 'GET',
  credentials: 'include'
})
  .then(r => {
    console.log('Response headers:', [...r.headers.entries()])
    return r.json()
  })
```

---

### Strategy 7: Check for Recent Changes

If login was working before and broke recently, identify what changed.

#### Common Changes That Break Auth

1. **Lambda code deployment** without updating all Lambdas
   - Fix: Redeploy all auth Lambdas
   
2. **APP_SECRET changed** in one Lambda but not others
   - Fix: Update APP_SECRET in all Lambdas (auth_callback, me, auth_disconnect)
   
3. **Environment variable changed** (e.g., FRONTEND_URL)
   - Fix: Update consistently across all Lambdas
   
4. **Database migration** that changed schema
   - Fix: Verify schema matches Lambda expectations
   
5. **API Gateway routes changed**
   - Fix: Verify routes point to correct Lambda integrations
   
6. **Frontend redeployed** with wrong .env
   - Fix: Rebuild with correct VITE_API_BASE_URL

#### Check Git History

```bash
# See recent commits
git log --oneline -20

# See changes to auth Lambdas
git log --oneline backend/auth_start/lambda_function.py
git log --oneline backend/auth_callback/lambda_function.py
git log --oneline backend/me/lambda_function.py

# See diff of specific commit
git show <commit-hash>
```

---

## Common Root Causes Ranked by Frequency

Based on typical deployment issues, here are the most common root causes:

### 1. APP_SECRET Mismatch (Most Common)
**Symptom**: `/me` returns 401 "invalid session" even though user completed OAuth

**How to check**:
```bash
# Get APP_SECRET from each Lambda
aws lambda get-function-configuration --function-name rabbitmiles-auth-callback \
  --query 'Environment.Variables.APP_SECRET'
  
aws lambda get-function-configuration --function-name rabbitmiles-me \
  --query 'Environment.Variables.APP_SECRET'

# They must be identical
```

**Fix**: Set same APP_SECRET in both Lambdas

### 2. Missing Environment Variables
**Symptom**: Lambda returns 500 "server configuration error"

**How to check**: Look at CloudWatch logs for specific missing variable

**Fix**: Set all required environment variables per [ENV_VARS.md](ENV_VARS.md)

### 3. Database Table Missing
**Symptom**: Database errors in CloudWatch logs

**How to check**:
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
```

**Fix**: Run migrations in `backend/migrations/`

### 4. IAM Permissions Missing
**Symptom**: "Access denied" errors in CloudWatch logs

**How to check**: Look for specific permission errors in logs

**Fix**: Add required permissions to Lambda execution role:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`

### 5. Cookie Not Being Sent from Browser
**Symptom**: `/me` returns 401 "not authenticated" + log says "No session cookie found"

**How to check**: 
- Browser DevTools → Network → /me request → Request Headers → Cookie

**Fix**: 
- Verify `withCredentials: true` in frontend API client
- Verify CORS headers include `Access-Control-Allow-Credentials: true`
- Verify cookie is actually stored in browser (DevTools → Application → Cookies)

---

## Emergency Debugging Script

If you're stuck, run this script to collect all relevant information:

```bash
#!/bin/bash
# debug-auth.sh - Collect debugging information for auth issues

echo "=== RabbitMiles Auth Debug Info ==="
echo

echo "--- Lambda Functions ---"
aws lambda list-functions --query "Functions[?contains(FunctionName, 'rabbitmiles')].FunctionName" --output table

echo
echo "--- Environment Variables (auth_callback) ---"
aws lambda get-function-configuration --function-name rabbitmiles-auth-callback \
  --query '{FRONTEND_URL: Environment.Variables.FRONTEND_URL, API_BASE_URL: Environment.Variables.API_BASE_URL, APP_SECRET_LENGTH: length(Environment.Variables.APP_SECRET), DB_NAME: Environment.Variables.DB_NAME}'

echo
echo "--- Environment Variables (me) ---"
aws lambda get-function-configuration --function-name rabbitmiles-me \
  --query '{FRONTEND_URL: Environment.Variables.FRONTEND_URL, APP_SECRET_LENGTH: length(Environment.Variables.APP_SECRET), DB_NAME: Environment.Variables.DB_NAME}'

echo
echo "--- Database Tables ---"
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"

echo
echo "--- Recent OAuth States ---"
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT COUNT(*) as count FROM oauth_states"

echo
echo "--- User Count ---"
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT COUNT(*) as user_count FROM users"

echo
echo "--- Recent Lambda Errors ---"
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-auth-callback \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --query 'events[*].[timestamp, message]' \
  --output text | tail -20

echo
echo "=== Debug info collection complete ==="
```

Save this as `debug-auth.sh`, make it executable (`chmod +x debug-auth.sh`), and run it to collect all relevant information in one place.

---

## Next Steps

If you've gone through this entire guide and still have issues:

1. **Capture complete flow**:
   - Run the debug script above
   - Save CloudWatch logs from all three auth Lambdas for a failed login attempt
   - Capture browser Network tab as HAR file
   - Screenshot browser cookies

2. **Create minimal reproduction**:
   - Try with a different test user
   - Try from a different browser/device
   - Try from incognito/private mode

3. **Check external dependencies**:
   - Is Strava API accessible?
   - Is Aurora database running?
   - Is API Gateway responding?

4. **Review recent changes**:
   - What was the last working deployment?
   - What changed since then?

5. **Contact support** with:
   - Debug script output
   - CloudWatch logs
   - Network HAR file
   - Steps to reproduce

---

**Last Updated**: 2026-02-05
**Maintained by**: RabbitMiles Team
