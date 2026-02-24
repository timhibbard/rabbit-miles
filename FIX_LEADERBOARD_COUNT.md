# Fix: Leaderboard Total Athletes Count

## Issue
The leaderboard was displaying "#5 out of 30" while the Admin Panel showed "All Users (51)", creating confusion about the total community size.

## Root Cause
The `get_total_athletes_count()` function in `backend/leaderboard_get/lambda_function.py` was counting only users who:
1. Had entries in `leaderboard_agg` for the specific time window, metric, and activity type
2. Had `show_on_leaderboards = true`

This meant the displayed count changed based on who had activities in each time period, rather than showing the total community size.

## Solution
Modified `get_total_athletes_count()` to count ALL users with `show_on_leaderboards = true`, regardless of whether they have activities in the current time period.

### Changes Made
1. Simplified the SQL query to: `SELECT COUNT(*) FROM users WHERE show_on_leaderboards = true`
2. Removed unused parameters (`window_key`, `metric`, `activity_type`) from the function signature
3. Updated the call site to not pass these parameters

## Deployment

### Automatic Deployment
The Lambda function will be automatically deployed when this PR is merged to `main` via the GitHub Actions workflow defined in `.github/workflows/deploy-lambdas.yml`.

### Manual Deployment (if needed)
If you need to deploy manually before merging:

1. Navigate to the GitHub Actions tab
2. Select "Deploy Lambda Functions" workflow
3. Click "Run workflow"
4. Select the branch `copilot/fix-leaderboard-athlete-count`
5. Click "Run workflow"

Or use AWS CLI:
```bash
cd backend/leaderboard_get
zip -r function.zip lambda_function.py
zip -j function.zip ../admin_utils.py
aws lambda update-function-code \
  --function-name rabbitmiles-leaderboard-get \
  --zip-file fileb://function.zip
```

## Verification

### Before Fix
- Leaderboard showed: "#5 out of 30"
- Admin Panel showed: "All Users (51)"
- Discrepancy: 21 users

### After Fix
1. Navigate to the Leaderboard page
2. Verify the "Your Rank" section shows "#X out of 51" (or the correct total of opted-in users)
3. Navigate to the Admin Panel
4. Verify the count matches the number of users with `show_on_leaderboards = true`
5. Check different time periods (week/month/year) and verify the total count remains consistent

### Expected Behavior
- The leaderboard will display the total count of users who have opted into leaderboards (via `show_on_leaderboards = true`)
- This count will remain consistent across different time periods
- The count will match the total shown in the Admin Panel (assuming all users have opted in)
- If some users have opted out, the leaderboard count will be less than the Admin Panel count, which is expected

## Database Query for Verification
To verify the correct count in the database:

```sql
-- Count total users with show_on_leaderboards = true
SELECT COUNT(*) FROM users WHERE show_on_leaderboards = true;

-- Count all users
SELECT COUNT(*) FROM users;

-- List users who have opted out
SELECT athlete_id, display_name, show_on_leaderboards 
FROM users 
WHERE show_on_leaderboards = false;
```

## Notes
- This fix does NOT change the actual leaderboard rankings, only the total count displayed
- Users who have opted out (`show_on_leaderboards = false`) will not be included in the count
- The count is now independent of time period, metric, and activity type
