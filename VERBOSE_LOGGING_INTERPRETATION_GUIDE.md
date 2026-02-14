# Quick Reference: Interpreting Verbose Logs

## What to Look For in CloudWatch Logs

After deploying this change, when the `/stats/period_summary` endpoint is called, look for these sections in CloudWatch Logs:

### 1. Activity Data Debug Section
```
--- ACTIVITY DATA DEBUG ---
Recent activities for athlete 3519964:
  1. Activity 12345: start_date_local=2026-02-14 15:30:00, timezone=(GMT-08:00) America/Los_Angeles, distance_on_trail=5000m
  2. Activity 12346: start_date_local=2026-02-13 10:00:00, timezone=(GMT-08:00) America/Los_Angeles, distance_on_trail=3000m
--- END ACTIVITY DATA DEBUG ---
```

**Key Questions:**
- ✅ Are there any activities listed? → If NO: User needs to sync from Strava
- ✅ Do the dates look reasonable? → If NO: Check activity import logic
- ✅ Are distances non-zero? → If NO: Check distance_on_trail calculation

### 2. Timezone Query Results
```
Executing timezone query for athlete_id=3519964
Timezone query raw result: {'records': [[{'stringValue': '(GMT-08:00) America/Los_Angeles'}]], ...}
Timezone field from result: {'stringValue': '(GMT-08:00) America/Los_Angeles'}
Athlete timezone from recent activity: (GMT-08:00) America/Los_Angeles
Current time in athlete timezone (America/Los_Angeles): 2026-02-14T15:30:00
```

**Key Questions:**
- ✅ Is a timezone found? → If NO: Activities don't have timezone data
- ✅ Is the timezone parsed correctly? → Look for "Current time in athlete timezone"
- ✅ Does the current time make sense? → Compare to actual time in that timezone

### 3. Period Boundary Calculations
```
Processing week:
  Current period: 2026-02-09 00:00:00 to 2026-02-15 23:59:59
  Previous period: 2026-02-02 00:00:00 to 2026-02-08 23:59:59
  Elapsed days: 6, Total days: 7
```

**Key Questions:**
- ✅ Is the period calculated correctly? → Compare to the activity dates shown earlier
- ✅ Should the activities fall within this range? → Check activity dates vs period boundaries

### 4. SQL Query Execution
```
    Querying with athlete_id=3519964, start=2026-02-09 00:00:00, end=2026-02-15 23:59:59
    Executing SQL: SELECT COALESCE(SUM(distance_on_trail), 0) as total_distance...
    With parameters: athlete_id=3519964, start_date='2026-02-09 00:00:00', end_date='2026-02-15 23:59:59'
    Raw query result: {'records': [[{'longValue': 0}]], ...}
    No records returned from query
```

**Key Questions:**
- ✅ Do the date parameters match the period boundaries? → If NO: Bug in date formatting
- ✅ Does the query return 0? → If YES: Continue to debug query

### 5. Debug Query (When Main Query Returns 0)
```
    DEBUG: All activities with distance for athlete 3519964:
      Activity 12345: start_date_local=2026-02-14 15:30:00, distance=5000m
        ^ This activity SHOULD match the query range!
      Activity 12346: start_date_local=2026-02-10 08:00:00, distance=3000m
        ^ This activity SHOULD match the query range!
```

**Key Questions:**
- ✅ Are there activities listed? → If NO: No activities with distance in database
- ✅ Are activities flagged as "SHOULD match"? → If YES: **SQL query bug** (likely timezone or date format issue)
- ✅ Do activity dates fall outside the period? → If YES: Period boundary calculation is wrong

## Common Diagnosis Patterns

### Pattern A: No Activities at All
```
Recent activities for athlete 3519964:
  No activities found for athlete 3519964
```
**Root Cause**: User hasn't synced activities or activity import is broken  
**Fix**: Check activity import/webhook functionality

### Pattern B: Activities Exist but Outside Period Range
```
Recent activities:
  1. Activity 12345: start_date_local=2026-01-14 15:30:00, ...
Processing week:
  Current period: 2026-02-09 00:00:00 to 2026-02-15 23:59:59
  ...
  Current distance: 0.00 miles
```
**Root Cause**: No activities in the queried period (working correctly)  
**Fix**: None needed - user doesn't have activities in this period

### Pattern C: Activities SHOULD Match but Don't
```
Recent activities:
  1. Activity 12345: start_date_local=2026-02-14 15:30:00, ...
Processing week:
  Current period: 2026-02-09 00:00:00 to 2026-02-15 23:59:59
  ...
    DEBUG: All activities with distance for athlete 3519964:
      Activity 12345: start_date_local=2026-02-14 15:30:00, distance=5000m
        ^ This activity SHOULD match the query range!
  Current distance: 0.00 miles
```
**Root Cause**: SQL query bug - activities in range but not returned  
**Possible Issues**:
1. Date format mismatch in SQL query
2. Timezone handling in SQL comparison
3. Parameter binding issue with RDS Data API

### Pattern D: Timezone Not Found / UTC Fallback
```
No timezone records found in query result
No athlete timezone found, using UTC
Current UTC time: 2026-02-14T21:16:22
```
**Root Cause**: Activities don't have timezone data, falling back to UTC  
**Impact**: May cause timezone mismatch if athlete is in a different timezone  
**Fix**: Ensure activities imported from Strava include timezone data

### Pattern E: Wrong Period Boundaries
```
Current time in athlete timezone (America/Los_Angeles): 2026-02-14T15:30:00
Processing week:
  Current period: 2026-02-16 00:00:00 to 2026-02-22 23:59:59
```
**Root Cause**: Period boundary calculation bug - looking at wrong week  
**Fix**: Check `get_period_boundaries()` logic

## Next Steps After Diagnosis

1. **Identify the pattern** that matches your logs
2. **Locate the root cause** from the diagnostic information
3. **Create a targeted fix** for the specific issue
4. **Test the fix** with the same athlete_id to verify
5. **Remove or reduce verbose logging** after issue is resolved (optional)

## Tips for Using These Logs

- Search for `"--- ACTIVITY DATA DEBUG ---"` to jump to the diagnostic section
- Search for `"SHOULD match the query range!"` to find the smoking gun
- Compare the "Current time" with "Recent activities" dates to spot timezone issues
- Look for gaps between what activities exist vs what the period query looks for
