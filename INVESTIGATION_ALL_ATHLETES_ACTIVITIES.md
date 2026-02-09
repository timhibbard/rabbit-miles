# Investigation: All Athletes' Activities Feature

## Issue Statement
"All Athletes' Activities (50) should look the 50 recent activities from all the users, not just the admin logged in user"

## Investigation Summary

After thorough investigation of the codebase, **the feature is already correctly implemented**. The `/admin/activities` endpoint returns activities from ALL users, not filtered to just the admin.

## Evidence

### 1. Backend SQL Query
**File:** `backend/admin_all_activities/lambda_function.py` (lines 142-164)

```sql
SELECT 
    a.id,
    a.athlete_id,
    a.strava_activity_id,
    a.name,
    a.distance,
    a.moving_time,
    a.elapsed_time,
    a.total_elevation_gain,
    a.type,
    a.start_date,
    a.start_date_local,
    a.created_at,
    a.updated_at,
    a.time_on_trail,
    a.distance_on_trail,
    u.display_name as athlete_name
FROM activities a
LEFT JOIN users u ON a.athlete_id = u.athlete_id
ORDER BY a.start_date_local DESC
LIMIT :limit OFFSET :offset
```

**Key observations:**
- ✅ NO `WHERE athlete_id = :athlete_id` clause
- ✅ Joins with `users` table to get `athlete_name` for each activity
- ✅ Orders by most recent activities first
- ✅ Returns activities from ALL users

### 2. Frontend Implementation
**File:** `src/pages/Admin.jsx` (lines 56-67)

```javascript
// Fetch all activities (last 50 from all users)
setActivitiesLoading(true);
const activitiesResult = await fetchAllActivities(50, 0);
if (activitiesResult.success) {
  setActivities(activitiesResult.data.activities || []);
  // ...
}
```

**File:** `src/utils/api.js` (lines 224-231)

```javascript
export const fetchAllActivities = async (limit = 50, offset = 0) => {
  const response = await api.get('/admin/activities', {
    params: { limit, offset },
  });
  return { success: true, data: response.data };
};
```

**Key observations:**
- ✅ Calls `/admin/activities` endpoint correctly
- ✅ Displays athlete name for each activity when no specific user is selected (line 516-518 in Admin.jsx)

### 3. Test Coverage
Added comprehensive test in `backend/admin_all_activities/test_lambda.py`:

**Test:** `test_all_activities_from_multiple_users()`
- ✅ Validates that activities from 3 different users are returned
- ✅ Confirms admin's activities (athlete_id: 12345) are mixed with other users
- ✅ Verifies athlete_name field is correctly populated for each user

All tests pass successfully.

## Conclusion

The code is **correctly implemented**. The "All Athletes' Activities" feature:
1. ✅ Fetches activities from ALL users in the database
2. ✅ Does NOT filter to only the admin user
3. ✅ Includes athlete name for each activity
4. ✅ Orders by most recent first
5. ✅ Has proper test coverage

## Possible Explanations for Issue Report

If users are experiencing behavior where only admin activities are shown, possible causes could be:

1. **Test Data Issue**: Database only contains activities from the admin user
2. **Deployment Lag**: Stale Lambda function deployed (though code history shows it's always been correct)
3. **Caching Issue**: Frontend or API Gateway caching old responses
4. **User Confusion**: User may have clicked on a specific user, changing the view to single-user mode

## Verification Steps for Deployment

To verify the feature works correctly in production:

1. Check that database contains activities from multiple users:
   ```sql
   SELECT COUNT(DISTINCT athlete_id) FROM activities;
   ```

2. Call the API endpoint directly and verify response:
   ```bash
   curl -X GET 'https://api.rabbitmiles.com/admin/activities?limit=10' \
     --cookie 'rm_session=<token>'
   ```

3. Verify the deployed Lambda has the correct code version

4. Check CloudWatch logs to see the actual SQL query being executed
