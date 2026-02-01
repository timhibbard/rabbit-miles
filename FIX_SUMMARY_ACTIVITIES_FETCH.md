# Fix Summary: Activities Not Being Fetched

## Issue Overview

**Symptoms:**
- Activities table in database was empty (0 rows)
- `/activities/fetch` API returned 200 OK but stored 0 activities  
- Dashboard showed "Successfully fetched activities (no new activities found)"
- User definitely had activities in Strava account

**Root Cause:**
Users who previously authorized RabbitMiles with an older OAuth scope configuration were being auto-approved when reconnecting, which kept their old (insufficient) permissions. Without the `activity:read_all` scope, Strava's API returns 200 OK with an empty array instead of an error, creating a "silent failure" that was hard to diagnose.

## Changes Summary

### Files Modified: 4
- ✅ `backend/auth_start/lambda_function.py` (1 line changed)
- ✅ `backend/fetch_activities/lambda_function.py` (82 lines changed)
- ✅ `src/pages/Dashboard.jsx` (9 lines changed)
- ✅ `ACTIVITIES_FETCH_FIX.md` (109 lines added)

**Total:** +190 lines, -12 lines

## Key Changes

### 1. Critical Fix: Force Re-Authorization
**File:** `backend/auth_start/lambda_function.py`

```diff
- "approval_prompt": "auto",
+ "approval_prompt": "force",  # Force re-authorization to ensure correct scope
```

**Impact:** Users must explicitly re-authorize, ensuring they grant the required `activity:read_all` scope.

### 2. Enhanced Logging
**File:** `backend/fetch_activities/lambda_function.py`

Added comprehensive logging throughout the fetch process:

- ✅ Strava API response status and body length
- ✅ Number of activities returned from Strava  
- ✅ Token expiration and refresh status
- ✅ Per-activity storage success/failure
- ✅ Detailed exception information with HTTP codes
- ✅ Database insert error details

**Sample log output:**
```
=== fetch_activities_for_athlete START ===
athlete_id: 12345
Token expires_at: 1738534567, current_time: 1738443789, diff: 90778s
Access token is valid, skipping refresh
Fetching activities from Strava API for athlete 12345...
Strava API response status: 200, body length: 15234
Parsed 15 activities from Strava
Attempting to store 15 activities for athlete 12345
Successfully stored activity 98765: Morning Run
Successfully stored activity 98764: Evening Ride
...
Storage complete: 15 stored, 0 failed
=== fetch_activities_for_athlete END: 15 activities stored ===
```

### 3. Improved User Messaging
**File:** `backend/fetch_activities/lambda_function.py` + `src/pages/Dashboard.jsx`

When 0 activities are fetched, users now see:

```
Successfully fetched activities (no new activities found). 
If you have activities in Strava but don't see them here, 
try disconnecting and reconnecting to grant the required permissions.
```

**Display time:** Extended to 8 seconds for better readability

### 4. Comprehensive Documentation
**File:** `ACTIVITIES_FETCH_FIX.md`

Added detailed documentation covering:
- Problem description and symptoms
- Root cause analysis
- Solution explanation
- Testing instructions for users and developers
- Strava API behavior notes
- Prevention recommendations

## Testing & Validation

✅ **Code Review:** No issues found  
✅ **Security Scan (CodeQL):** No vulnerabilities detected  
✅ **Minimal Changes:** Only modified what was necessary to fix the issue

## User Instructions

**To resolve the issue:**

1. **Disconnect from Strava:**
   - Navigate to Settings
   - Click "Disconnect from Strava"

2. **Reconnect to Strava:**
   - You will see the Strava authorization prompt
   - Approve the permissions (including activity:read_all)

3. **Refresh Activities:**
   - Go to Dashboard
   - Click "Refresh Activities"
   - Your activities should now appear!

## Deployment

The changes will automatically deploy when merged to `main`:
- GitHub Actions workflow: `.github/workflows/deploy-lambdas.yml`
- Affected Lambda functions:
  - `auth_start` (force re-authorization)
  - `fetch_activities` (enhanced logging)

## Technical Details

**Strava OAuth Behavior:**
- `approval_prompt=auto`: Auto-approves if user previously authorized with same/broader scope
- `approval_prompt=force`: Always shows authorization prompt, even for existing authorizations
- Without required scope: API returns 200 OK with empty array (not 401 error)

**Required Scope:**
- `activity:read_all` - Required to read all activities (public and private)

## Prevention

To prevent similar issues in the future:

1. ✅ Use `approval_prompt=force` when adding new scopes
2. Consider storing granted scope in database for verification
3. Add scope validation before making API calls
4. Provide clear error messages for insufficient permissions

## Monitoring

After deployment, monitor CloudWatch logs for:
- Strava API response status codes
- Activity count returned from Strava
- Database insert success/failure rates
- Token refresh success/failure

Look for patterns like:
- Consistent 0 activities from Strava (scope issue)
- HTTP 401 errors (token revoked)
- HTTP 429 errors (rate limiting)
- Database insert failures (schema issues)
