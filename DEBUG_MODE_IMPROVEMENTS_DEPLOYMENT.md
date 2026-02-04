# Debug Mode Improvements - Deployment Guide

## Summary

Enhanced debug mode functionality for the ActivityDetail page to improve debugging and analysis capabilities.

## Changes Made

### Frontend Changes (src/pages/ActivityDetail.jsx)

1. **Increased Point Analysis Limit**: Changed from 50 to 200 points per page
2. **Added Pagination**: Implemented pagination for point-by-point analysis table
   - Previous/Next buttons
   - Page indicator showing current page and total pages
   - Shows range of points being displayed
3. **Added Activity ID Display**: Now shows the database `id` field in debug info
4. **Added Last Matched Display**: Shows when the activity was last matched against trail data
5. **Added Reset Button**: Button to reset `last_matched` to NULL (only visible in debug mode)
   - Red button with confirmation dialog
   - Reloads page after successful reset

### Backend Changes (backend/reset_last_matched/lambda_function.py)

Enhanced the Lambda to support two modes:
1. **Reset All Activities** (existing): `POST /activities/reset-matching`
   - Resets all activities for the authenticated user
2. **Reset Single Activity** (new): `POST /activities/{id}/reset-matching`
   - Resets only the specified activity
   - Verifies the activity belongs to the authenticated user
   - Returns 404 if activity not found or access denied

### API Changes (src/utils/api.js)

Added new function:
- `resetActivityTrailMatching(activityId)`: Resets trail matching for a single activity

## API Gateway Configuration Required

### New Route to Add

The Lambda already exists and is deployed, but you need to add a new route in API Gateway:

**Route:** `POST /activities/{id}/reset-matching`
**Integration:** Lambda function `rabbitmiles-reset-last-matched`
**Method:** POST
**Authorization:** None (authentication handled in Lambda via session cookie)

### Configuration Steps

1. Open AWS API Gateway console
2. Select your HTTP API (the one with the RabbitMiles endpoints)
3. Go to "Routes"
4. Click "Create"
5. Configure the route:
   - Method: `POST`
   - Path: `/activities/{id}/reset-matching`
   - Integration: Select the existing `rabbitmiles-reset-last-matched` Lambda
6. Deploy the API

### Existing Route (Should Already Exist)

The following route should already be configured:
- `POST /activities/reset-matching` → `rabbitmiles-reset-last-matched`

If it doesn't exist, add it following the same steps above but without the `{id}` path parameter.

## Testing

### Test Single Activity Reset

1. Navigate to any activity detail page with `?debug=1` query parameter
2. Verify the debug section shows:
   - Activity ID
   - Last Matched timestamp (or "Never" if null)
   - "Reset last_matched to NULL" button
3. Click the reset button
4. Confirm the dialog
5. Verify success message appears
6. Check that the page reloads

### Test Point Pagination

1. Navigate to an activity with more than 200 points with `?debug=1`
2. Open the "View point-by-point analysis" details
3. Verify:
   - Shows 200 points per page
   - Pagination controls appear at the bottom
   - Previous button is disabled on first page
   - Next button is disabled on last page
   - Page indicator shows correct information

### Test Backend Directly

```bash
# Test single activity reset (replace with your values)
curl -X POST https://YOUR-API-GATEWAY-URL/prod/activities/123/reset-matching \
  -H "Content-Type: application/json" \
  -H "Cookie: rm_session=YOUR_SESSION_TOKEN" \
  --cookie-jar cookies.txt \
  --cookie cookies.txt

# Expected response:
# {
#   "success": true,
#   "activities_reset": 1,
#   "message": "Successfully reset activity 123 for trail matching"
# }

# Test without authentication (should fail)
curl -X POST https://YOUR-API-GATEWAY-URL/prod/activities/123/reset-matching \
  -H "Content-Type: application/json"

# Expected response: 401 with {"error": "not authenticated"}
```

## Rollback Plan

If issues occur:

1. **Frontend only**: Revert the frontend deployment by deploying the previous commit
2. **Backend only**: The Lambda changes are backward compatible with existing `/activities/reset-matching` route
3. **Full rollback**: Revert both frontend and backend to previous versions

## Notes

- The Lambda function is backward compatible - it continues to support the existing route for resetting all activities
- Debug mode is only accessible with `?debug=1` query parameter
- The reset button is only visible in debug mode
- All authentication is handled via session cookies, no tokens in localStorage
- The Lambda verifies that users can only reset their own activities
