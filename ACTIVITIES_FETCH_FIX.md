# Activities Fetch Fix

## Problem

Activities were not being fetched from Strava even though the fetch endpoint returned 200 OK. The database showed 0 rows in the activities table, and the UI displayed "Successfully fetched activities (no new activities found)".

## Root Cause

Users who authorized RabbitMiles before the `activity:read_all` scope was properly configured were getting auto-approved with their existing (insufficient) permissions when reconnecting. This happened because:

1. The OAuth flow used `approval_prompt=auto`
2. Strava auto-approves with existing authorization if scopes haven't changed
3. Old authorizations only had `read` scope, not `activity:read_all`
4. When calling the activities API without proper scope, Strava returns 200 OK with an empty array instead of an error

## Solution

### 1. Force Re-Authorization (Critical Fix)

Changed `approval_prompt` from `auto` to `force` in `backend/auth_start/lambda_function.py`:

```python
"approval_prompt": "force",  # Force re-authorization to ensure correct scope
```

This ensures that users must explicitly re-authorize the app, granting the required `activity:read_all` scope.

### 2. Enhanced Logging

Added comprehensive logging throughout the `backend/fetch_activities/lambda_function.py` to make debugging easier:

- Strava API response status and body length
- Token expiration and refresh details
- Activity storage success/failure per activity
- Detailed error information including HTTP status codes and response bodies

### 3. Improved User Messaging

When 0 activities are fetched, the backend now returns a helpful message:

> "Successfully fetched activities (no new activities found). If you have activities in Strava but don't see them here, try disconnecting and reconnecting to grant the required permissions."

## Testing Instructions

### For Users Currently Experiencing the Issue:

1. **Disconnect from Strava**:
   - Go to Settings in RabbitMiles
   - Click "Disconnect from Strava"

2. **Reconnect to Strava**:
   - You will be prompted to authorize RabbitMiles
   - Make sure to approve the permissions when prompted
   - You should see the authorization screen even if you previously authorized the app

3. **Refresh Activities**:
   - Go to Dashboard
   - Click "Refresh Activities"
   - Your activities should now appear!

### For Developers:

After deploying the changes:

1. **Deploy Lambda Functions**:
   ```bash
   # The GitHub Actions workflow will auto-deploy when merged to main
   # Or manually trigger: gh workflow run deploy-lambdas.yml
   ```

2. **Check CloudWatch Logs**:
   - Look for the new detailed logging in `fetch_activities` Lambda
   - Verify Strava API response status and activity count

3. **Test the Flow**:
   - Disconnect and reconnect to Strava
   - Check that you see the Strava authorization prompt
   - Verify activities are fetched successfully

## Files Changed

### Backend:
- `backend/auth_start/lambda_function.py` - Changed `approval_prompt` to `force`
- `backend/fetch_activities/lambda_function.py` - Added comprehensive logging and improved error messages

### Frontend:
- `src/pages/Dashboard.jsx` - Improved message display for empty activity results

## Related Strava API Behavior

From Strava API documentation:

- **Scope:** `activity:read_all` is required to read ALL activities (public and private)
- **Auto-approval:** When `approval_prompt=auto`, Strava will auto-approve if the user has already authorized with the same or broader scope
- **Scope mismatch:** When calling an API endpoint without the required scope, Strava returns 200 OK with an empty result instead of 401 Unauthorized

## Prevention

To prevent this issue in the future:

1. Always use `approval_prompt=force` when adding new scopes
2. Store the granted scope in the database for future verification
3. Add scope validation before making API calls
4. Provide clear error messages when scope is insufficient

## References

- [Strava OAuth Guide](https://developers.strava.com/docs/authentication/)
- [Strava API - List Activities](https://developers.strava.com/docs/reference/#api-Activities-getLoggedInAthleteActivities)
