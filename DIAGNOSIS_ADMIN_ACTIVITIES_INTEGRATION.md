# Diagnosing the Admin Activities Issue

## Current Status

The API Gateway route `GET /admin/activities` exists (confirmed by screenshot), but the frontend is showing only Tim Hibbard's activities without athlete names displayed.

## Key Observations

1. ✅ Route exists in API Gateway: `GET /admin/activities` (ID: pnkvb29)
2. ✅ Integration exists: `vgjpa5n`
3. ❌ Activities shown don't display "Athlete: [name]" field
4. ❌ All activities appear to be from Tim Hibbard only

## Likely Root Cause

The `/admin/activities` route integration is pointing to the **wrong Lambda function**. It's probably calling:
- `get_activities` (user's own activities) ❌
instead of:
- `admin_all_activities` (all users' activities) ✅

## Evidence

### Backend Code Comparison

**`admin_all_activities` (correct):**
```python
SELECT a.id, a.athlete_id, ..., u.display_name as athlete_name
FROM activities a
LEFT JOIN users u ON a.athlete_id = u.athlete_id  -- Joins users table
ORDER BY a.start_date_local DESC
LIMIT :limit OFFSET :offset
-- NO WHERE clause!
```

**`get_activities` (wrong for this use case):**
```python
SELECT id, ..., distance_on_trail
FROM activities
WHERE athlete_id = :aid  -- Filters to logged-in user only!
ORDER BY start_date DESC
LIMIT :limit OFFSET :offset
-- No users table join, no athlete_name field
```

### Frontend Behavior

The frontend code at `src/pages/Admin.jsx:516-518` displays:
```jsx
{!selectedUser && activity.athlete_name && (
  <p className="text-orange-600 font-medium">Athlete: {activity.athlete_name}</p>
)}
```

**If this line doesn't appear in the UI**, it means `activity.athlete_name` is undefined/null, which indicates:
- The Lambda being called doesn't return the `athlete_name` field
- This matches `get_activities` behavior (no user join, no athlete_name)

## Solution

Update the API Gateway integration for route `GET /admin/activities` to point to the correct Lambda:

### Option 1: Via AWS CLI

```bash
# 1. Get the current integration details
aws apigatewayv2 get-integration \
  --api-id 9zke9jame0 \
  --integration-id vgjpa5n

# 2. Update to point to admin_all_activities
aws apigatewayv2 update-integration \
  --api-id 9zke9jame0 \
  --integration-id vgjpa5n \
  --integration-uri "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:rabbitmiles-admin-all-activities"
```

### Option 2: Via AWS Console

1. Go to API Gateway console
2. Select the `rabbitmiles` API
3. Click on route `GET /admin/activities`
4. Under "Integration", click "Edit"
5. Change the Lambda function to: `rabbitmiles-admin-all-activities`
6. Save changes
7. Deploy the API

## Expected Result After Fix

Activities should display with athlete names:

```
Afternoon Run
Athlete: Tim Hibbard      ← This line should appear
Type: Run
Distance: 6.35 mi
...

Dog walk  
Athlete: Alyssa Smith     ← Different athlete
Type: Walk
Distance: 1.70 mi
...
```

## Verification Steps

1. **Check which Lambda is being called:**
   ```bash
   aws apigatewayv2 get-integration \
     --api-id 9zke9jame0 \
     --integration-id vgjpa5n \
     --query 'IntegrationUri' \
     --output text
   ```
   
   Should show: `...function:rabbitmiles-admin-all-activities`
   If it shows: `...function:rabbitmiles-get-activities` ← **This is the problem!**

2. **Test the endpoint after fix:**
   ```bash
   curl "https://api.rabbitmiles.com/admin/activities?limit=5" \
     --cookie "rm_session=TOKEN" | jq '.activities[0] | keys'
   ```
   
   Should include `"athlete_name"` in the keys

3. **Check CloudWatch logs:**
   ```bash
   aws logs tail /aws/lambda/rabbitmiles-admin-all-activities --follow
   ```
   
   After refreshing the admin page, you should see:
   ```
   LOG - Fetching activities for all users
   LOG - Querying all activities (limit=50, offset=0)
   ```

## Additional Notes

- The Lambda `rabbitmiles-admin-all-activities` was created in PR #211
- The GitHub Actions workflow includes this Lambda in deployments
- The code is correct; only the API Gateway integration is misconfigured
- This is why my previous tests passed—the Lambda code itself works perfectly
