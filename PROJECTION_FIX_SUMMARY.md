# Projection Calculation Fix - Summary

## Issue
The `/stats/period_summary` Lambda endpoint was returning 0.00 for all projections despite the user having activities with distance data in the database.

## Root Cause
The Lambda was using UTC time to calculate period boundaries (week/month/year), but the database stores activity timestamps in `start_date_local` which represents the athlete's local timezone. This timezone mismatch caused period boundaries to be misaligned in certain edge cases.

### Example Edge Case
When it's Sunday 11:00 PM PST (athlete's local time):
- In PST: This is still Sunday, part of the current week (Feb 2-8)
- In UTC: This is Monday 7:00 AM, part of the NEXT week (Feb 9-15)

If the Lambda calculates the "current week" as Feb 9-15 (UTC), but activities are timestamped in PST, it would look for activities that haven't happened yet, returning 0.00 miles.

## Solution
Modified the Lambda to query the athlete's timezone from their most recent activity and use that timezone for period boundary calculations. This ensures period boundaries align with how `start_date_local` is stored in the database.

### Changes Made
1. **Query athlete timezone**: Added SQL query to fetch timezone from most recent activity
2. **Use athlete timezone**: Calculate `now` in athlete's timezone instead of UTC
3. **Fallback to UTC**: Gracefully handle missing or invalid timezone data
4. **Better debugging**: Added logging for query parameters and results
5. **Bug fix**: Fixed potential issue with zero distance values in RDS Data API response

## Testing
- Created unit tests demonstrating the timezone edge case
- Validated timezone parsing for different Strava timezone formats
- Verified naive timestamp comparison logic works correctly
- Confirmed no security vulnerabilities with CodeQL

## Files Changed
- `backend/stats_period_summary/lambda_function.py` - Core fix and improvements
- `backend/stats_period_summary/test_timezone_fix.py` - New test file

## Deployment Notes
- No environment variable changes required
- No database schema changes required
- Backward compatible (falls back to UTC if timezone unavailable)
- Lambda runtime must support Python 3.9+ for `zoneinfo` module

## Expected Behavior After Fix
When the endpoint is called:
1. Lambda queries athlete's timezone from most recent activity
2. Calculates period boundaries in athlete's local timezone
3. Queries activities using these timezone-aligned boundaries
4. Returns correct distance and projection values

The fix ensures consistency between:
- Frontend Dashboard.jsx (uses browser local time)
- Database `start_date_local` (stores athlete local time)
- Lambda period calculations (now uses athlete local time)
