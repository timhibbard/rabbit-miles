# Debug Mode Improvements - Testing Summary

## Overview

This document provides a comprehensive summary of the debug mode improvements implemented and how to test them.

## Changes Summary

### 1. Load 200 Points Instead of 50 ✅

**What Changed:**
- Previously: Point-by-point analysis showed only the first 50 points
- Now: Shows 200 points per page with pagination

**Code Changes:**
- Added `POINTS_PER_PAGE = 200` constant
- Updated slice logic from `slice(0, 50)` to `slice(currentPage * POINTS_PER_PAGE, (currentPage + 1) * POINTS_PER_PAGE)`

### 2. Paginate the Rest of the Points ✅

**What Changed:**
- Added pagination controls (Previous/Next buttons)
- Shows current page number, total pages, and point range
- Pagination only appears when there are more than 200 points

**Code Changes:**
- Added `currentPage` state variable
- Implemented pagination UI with Previous/Next buttons
- Buttons are disabled appropriately (Previous on first page, Next on last page)
- Page indicator shows: "Page X of Y (showing A - B of Z points)"

### 3. Add Button to Reset last_matched ✅

**What Changed:**
- Added red "Reset last_matched to NULL" button in debug section
- Only visible when `?debug=1` is in the URL
- Shows confirmation dialog before reset
- Reloads page after successful reset
- Displays loading state while resetting

**Code Changes:**
- Added `resettingMatching` state variable
- Implemented `handleResetMatching` function
- Added button with proper styling and disabled state
- Backend Lambda enhanced to support single activity reset via `POST /activities/{id}/reset-matching`

### 4. Show the ID of the Record ✅

**What Changed:**
- Added "Activity ID" field to debug information section
- Shows the database `id` field of the activity record

**Code Changes:**
- Added display of `activity.id` in the debug info section

### Additional Improvements Made

1. **Last Matched Timestamp Display:**
   - Shows when the activity was last matched against trail data
   - Displays "Never" if never matched (last_matched is NULL)

2. **Code Quality Improvements:**
   - Extracted magic number (200) to `POINTS_PER_PAGE` constant
   - Fixed React key prop to use `point.pointIndex` instead of array index
   - Ensures proper key uniqueness across pagination

## How to Test

### Prerequisites
1. User must be authenticated with a valid session cookie
2. Activity must have polyline data
3. Activity must have been trail-matched (distance_on_trail !== null)
4. Must navigate to activity detail page with `?debug=1` query parameter

### Test Case 1: View Activity ID and Last Matched

**Steps:**
1. Navigate to any activity detail page
2. Add `?debug=1` to the URL (e.g., `/activity/123?debug=1`)
3. Scroll down to the "Debug Information" section

**Expected Result:**
- Debug section is visible
- Shows "Activity ID: [number]"
- Shows "Last Matched: [timestamp]" or "Last Matched: Never"

### Test Case 2: View 200 Points Per Page

**Steps:**
1. Navigate to an activity with polyline data and `?debug=1`
2. In the Debug Information section, click "View point-by-point analysis (200 points per page)"

**Expected Result:**
- Details expand to show a table
- Table shows up to 200 points
- Each point shows: #, Lat, Lon, On Trail (✓/✗), Distance (m)

### Test Case 3: Pagination (More than 200 points)

**Steps:**
1. Navigate to an activity with more than 200 points with `?debug=1`
2. Open the point-by-point analysis
3. Check pagination controls at the bottom

**Expected Result:**
- Pagination controls appear at the bottom of the table
- Shows: "Page 1 of X (showing 1 - 200 of Y points)"
- Previous button is disabled on first page
- Click Next button to go to page 2
- Previous button becomes enabled
- Page indicator updates correctly
- On last page, Next button is disabled

### Test Case 4: Pagination (Less than 200 points)

**Steps:**
1. Navigate to an activity with fewer than 200 points with `?debug=1`
2. Open the point-by-point analysis

**Expected Result:**
- No pagination controls appear
- All points are shown in a single view

### Test Case 5: Reset last_matched Button

**Steps:**
1. Navigate to any activity with `?debug=1`
2. Note the current "Last Matched" value
3. Click the red "Reset last_matched to NULL" button
4. Confirm the dialog by clicking OK

**Expected Result:**
- Confirmation dialog appears with warning message
- After clicking OK, button shows "Resetting..." text and is disabled
- Success alert appears: "Trail matching reset successfully. The activity will be reprocessed."
- Page reloads automatically
- After reload, "Last Matched" should show "Never"

### Test Case 6: Reset Button Cancel

**Steps:**
1. Navigate to any activity with `?debug=1`
2. Click the red "Reset last_matched to NULL" button
3. Click Cancel in the confirmation dialog

**Expected Result:**
- Dialog closes
- No reset occurs
- Page remains unchanged

### Test Case 7: Debug Mode Not Active

**Steps:**
1. Navigate to any activity WITHOUT `?debug=1` in the URL

**Expected Result:**
- Debug Information section is not visible
- No Activity ID displayed
- No reset button visible
- No point-by-point analysis available

## Backend Testing

### Test Single Activity Reset Endpoint

```bash
# Replace with your actual values
API_URL="https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod"
ACTIVITY_ID="123"
SESSION_COOKIE="your_session_cookie_here"

# Test authenticated request
curl -X POST "$API_URL/activities/$ACTIVITY_ID/reset-matching" \
  -H "Content-Type: application/json" \
  -H "Cookie: rm_session=$SESSION_COOKIE" \
  -v

# Expected: 200 OK with {"success": true, "activities_reset": 1, "message": "..."}
```

### Test Without Authentication

```bash
curl -X POST "$API_URL/activities/$ACTIVITY_ID/reset-matching" \
  -H "Content-Type: application/json" \
  -v

# Expected: 401 Unauthorized with {"error": "not authenticated"}
```

### Test Invalid Activity ID

```bash
curl -X POST "$API_URL/activities/999999999/reset-matching" \
  -H "Content-Type: application/json" \
  -H "Cookie: rm_session=$SESSION_COOKIE" \
  -v

# Expected: 404 Not Found with {"error": "activity not found or access denied"}
```

## Manual Verification Checklist

- [x] Code compiles without errors (`npm run build`)
- [x] No Python syntax errors in Lambda
- [x] Code review completed and feedback addressed
- [x] Security scan completed with no vulnerabilities
- [ ] Frontend displays Activity ID in debug mode
- [ ] Frontend displays Last Matched timestamp in debug mode
- [ ] Frontend shows 200 points per page (not 50)
- [ ] Pagination controls appear when points > 200
- [ ] Pagination controls work correctly (Previous/Next)
- [ ] Reset button appears in debug mode
- [ ] Reset button confirmation dialog works
- [ ] Reset button successfully resets last_matched
- [ ] Page reloads after successful reset
- [ ] Backend Lambda accepts single activity reset requests
- [ ] Backend Lambda verifies activity ownership
- [ ] Backend Lambda returns appropriate errors (401, 404)

## Known Limitations

1. **API Gateway Route:** The new route `POST /activities/{id}/reset-matching` must be manually added to API Gateway. See DEBUG_MODE_IMPROVEMENTS_DEPLOYMENT.md for instructions.

2. **Authentication Required:** All functionality requires a valid authenticated session.

3. **Debug Mode Only:** All new UI elements only appear when `?debug=1` is in the URL.

4. **Page Reload:** After resetting, the page performs a full reload rather than a soft refresh. This ensures the updated `last_matched` value is fetched.

## Files Modified

1. **src/pages/ActivityDetail.jsx**
   - Added POINTS_PER_PAGE constant
   - Added currentPage and resettingMatching state
   - Added handleResetMatching function
   - Updated debug section UI
   - Implemented pagination

2. **src/utils/api.js**
   - Added resetActivityTrailMatching function

3. **backend/reset_last_matched/lambda_function.py**
   - Enhanced to support single activity reset
   - Added path parameter handling
   - Added activity ownership verification

4. **DEBUG_MODE_IMPROVEMENTS_DEPLOYMENT.md** (new file)
   - Deployment instructions
   - API Gateway configuration

## Security Considerations

- ✅ All authentication handled via session cookies
- ✅ Backend verifies activity ownership before reset
- ✅ No sensitive data exposed in debug mode
- ✅ CodeQL scan found no vulnerabilities
- ✅ Proper error messages without information leakage
