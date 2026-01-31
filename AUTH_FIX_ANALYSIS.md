# Authentication Flow Issues - Analysis and Fixes

## Problem Statement

After a user connects with Strava, the authenticated user information is not showing in the SPA.

## Root Cause Analysis

### Issue 1: Missing Database Schema (CRITICAL)

**Problem:** The `users` table does not exist in the database.

**Evidence:**
- No `CREATE TABLE users` migration file found
- Only `002_add_profile_picture.sql` which tries to ALTER TABLE users
- If the table doesn't exist, the auth_callback Lambda will fail when trying to INSERT/UPSERT user data

**Impact:**
- OAuth flow completes on Strava side
- auth_callback receives the code and exchanges it for tokens
- Database INSERT fails silently (caught by try/catch)
- User record is never created
- Session cookie is never set
- /me endpoint returns 401 because no valid session exists

**Fix:**
- Created `backend/migrations/000_create_users_table.sql`
- Defines complete schema with all required columns:
  - athlete_id (BIGINT PRIMARY KEY)
  - display_name (VARCHAR(255))
  - profile_picture (TEXT, nullable)
  - access_token (TEXT)
  - refresh_token (TEXT)
  - expires_at (BIGINT)
  - created_at (TIMESTAMP)
  - updated_at (TIMESTAMP)

### Issue 2: Suboptimal OAuth Redirect Flow

**Problem:** After OAuth success, user is redirected to `/?connected=1` (Dashboard page)

**Issues with this flow:**
1. Dashboard immediately calls /me endpoint
2. If there's any delay or issue, user sees loading spinner then error
3. No clear success message
4. User doesn't know if connection succeeded
5. If /me fails, user is redirected to /connect, creating confusion

**Better Flow:**
- Redirect to `/connect?connected=1`
- ConnectStrava page is designed to handle this:
  - Calls /me to verify connection
  - Shows success message with user profile picture and name
  - Provides clear "Go to Dashboard" button
  - If connection fails, shows appropriate error

**Fix:**
- Changed auth_callback redirect from `{FRONTEND}/?connected=1` to `{FRONTEND}/connect?connected=1`

### Issue 3: Insufficient Logging and Error Messages

**Problem:** When issues occur, it's difficult to diagnose them.

**Issues:**
- auth_callback doesn't log when user is created
- /me endpoint catches all exceptions and returns generic error
- No logging to indicate which step of authentication failed
- Frontend doesn't log /me calls or responses

**Fix:**
Added comprehensive logging:

**Backend (auth_callback):**
- Log when user is successfully upserted to database
- Log when session token is created

**Backend (me):**
- Log cookie presence
- Log session verification success/failure
- Log database query success
- Log detailed error messages with stack traces
- Return error message in 500 response for debugging

**Frontend:**
- Log /me endpoint calls
- Log response data
- Log authentication status changes
- Log OAuth callback detection

### Issue 4: Poor Error Handling in /me Endpoint

**Problem:** Generic error handling makes debugging difficult

**Issues:**
- All exceptions caught and return same generic error
- No indication of what went wrong
- No stack trace in logs

**Fix:**
- Added specific error messages at each failure point
- Added print statements before each return
- Added traceback output for exceptions
- Return error message in response body (in addition to logs)

## Deployment Requirements

### 1. Database Migration (CRITICAL)

Must run before OAuth will work:

```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "$(cat backend/migrations/000_create_users_table.sql)"
```

Verify:
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_name = 'users'"
```

### 2. Lambda Deployment

Deploy updated Lambda functions:

**auth_callback:**
- Updated redirect URL
- Added logging

```bash
cd backend/auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION \
  --zip-file fileb://function.zip
```

**me:**
- Added comprehensive logging
- Better error handling

```bash
cd backend/me
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_ME_FUNCTION \
  --zip-file fileb://function.zip
```

### 3. Frontend Deployment

Frontend changes are automatically deployed via GitHub Actions when merged to main.

## Potential Database Connection Issues

### Issue: Lambda Cannot Connect to RDS

**Symptoms:**
- CloudWatch logs show database connection errors
- Timeout errors
- Permission denied errors

**Common Causes:**

1. **VPC Configuration**
   - Lambdas using RDS Data API should NOT be in a VPC
   - If Lambda is in VPC, it needs:
     - NAT Gateway for internet access
     - VPC endpoints for RDS Data API

2. **IAM Permissions**
   - Lambda execution role needs:
     ```json
     {
       "Effect": "Allow",
       "Action": [
         "rds-data:ExecuteStatement",
         "rds-data:BatchExecuteStatement"
       ],
       "Resource": "arn:aws:rds:REGION:ACCOUNT:cluster:CLUSTER_ID"
     }
     ```
   - Also needs access to Secrets Manager:
     ```json
     {
       "Effect": "Allow",
       "Action": [
         "secretsmanager:GetSecretValue"
       ],
       "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET_NAME"
     }
     ```

3. **Cluster Status**
   - Aurora Serverless cluster might be paused
   - Check cluster status in RDS console
   - First request might timeout while cluster scales up

4. **Incorrect ARNs**
   - Verify DB_CLUSTER_ARN matches actual cluster
   - Verify DB_SECRET_ARN matches actual secret
   - Verify DB_NAME is correct (default: postgres)

### Issue: RDS Data API Query Errors

**Symptoms:**
- Query execution fails
- Invalid parameter errors
- Type conversion errors

**Common Causes:**

1. **NULL Value Handling**
   - Must use `{"isNull": True}` for NULL values
   - Cannot use empty string or None for NULL
   - Fixed in auth_callback for profile_picture

2. **Type Mismatches**
   - Must use correct value types:
     - `longValue` for BIGINT, INTEGER
     - `stringValue` for VARCHAR, TEXT
     - `booleanValue` for BOOLEAN
   - Check parameter types match column types

3. **Response Parsing**
   - RDS Data API returns records as array of arrays
   - Each field is an object with type-specific key
   - Example: `[{"longValue": 123}, {"stringValue": "test"}]`
   - Code must handle NULL fields correctly

## Testing the Fix

### Prerequisites

1. Database migration has been run
2. Lambda functions have been deployed
3. Environment variables are set correctly

### Test Steps

1. **Clear browser cookies**
   - Open DevTools → Application → Cookies
   - Delete all cookies for the app domain

2. **Open browser console**
   - Press F12
   - Go to Console tab
   - Go to Network tab

3. **Navigate to /connect page**
   - Should show "Connect with Strava" button
   - Console should show: "ConnectStrava: User not connected"

4. **Click "Connect with Strava"**
   - Redirected to Strava OAuth page
   - Authorize the application

5. **After authorization**
   - Redirected to `/connect?connected=1`
   - Console should show:
     ```
     ConnectStrava: Just connected? true
     ConnectStrava: Checking authentication...
     Calling /me endpoint...
     /me response: {athlete_id: ..., display_name: ..., profile_picture: ...}
     ConnectStrava: fetchMe result: {success: true, user: {...}}
     ConnectStrava: User is connected: {...}
     ```
   - Page should show:
     - Profile picture
     - "You're Connected!" message
     - "Welcome, [Your Name]"
     - "Go to Dashboard" button

6. **Check Network tab**
   - Find request to `/auth/callback`
     - Status: 302
     - Set-Cookie header with rm_session
   - Find request to `/me`
     - Status: 200
     - Cookie header with rm_session
     - Response: user data JSON

7. **Click "Go to Dashboard"**
   - Dashboard loads
   - Console shows:
     ```
     Dashboard: Checking authentication...
     Calling /me endpoint...
     /me response: {...}
     Dashboard: fetchMe result: {success: true, user: {...}}
     Dashboard: User authenticated: {...}
     ```
   - Page shows:
     - Profile picture
     - "Welcome back, [Your Name]!"
     - Stats (currently 0.0 miles)

### Expected CloudWatch Logs

**auth_callback:**
```
Successfully upserted user 12345678 (John Doe) to database
Created session token for athlete_id: 12345678
```

**me (first call):**
```
Cookie header received: True
Verified session for athlete_id: 12345678
Successfully retrieved user from database
```

**me (subsequent calls):**
```
Cookie header received: True
Verified session for athlete_id: 12345678
Successfully retrieved user from database
```

## Success Criteria

- [ ] User can complete OAuth flow
- [ ] User is redirected to `/connect?connected=1`
- [ ] Success message displays with user info
- [ ] Dashboard loads with user info
- [ ] /me endpoint returns 200 with user data
- [ ] Browser console shows no errors
- [ ] CloudWatch logs show successful operations
- [ ] User can navigate between pages without re-authenticating

## Rollback Plan

If issues occur after deployment:

1. **Database cannot be rolled back** - the users table is needed for the application to work
2. **Lambda functions can be rolled back** to previous versions via AWS Console
3. **Frontend can be rolled back** by reverting the commit and pushing to main

## Security Considerations

All changes maintain security best practices:

- No changes to authentication mechanism (still cookie-based)
- No changes to token signing (still HMAC-SHA256)
- No changes to CORS configuration
- Logging does not expose sensitive data (tokens are truncated)
- Error messages are informative but don't expose internals

## Additional Notes

### Why the users table was missing

The migrations directory only had:
1. `001_create_oauth_states.sql` - for OAuth state validation
2. `002_add_profile_picture.sql` - ALTER TABLE to add column

This suggests:
1. The users table was created manually in initial setup
2. The migration was lost or never committed
3. A new environment was created without the schema

### Migration Order

Correct order:
1. `000_create_users_table.sql` - Creates users table
2. `001_create_oauth_states.sql` - Creates oauth_states table
3. `002_add_profile_picture.sql` - Adds profile_picture column (optional if running 000)

### Future Improvements

1. Add health check endpoint to verify database connectivity
2. Add endpoint to test session token validation
3. Add migration script to run all migrations
4. Add database schema version tracking
5. Add automated tests for OAuth flow
