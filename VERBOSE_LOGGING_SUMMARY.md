# Verbose Logging Enhancement Summary

## Problem
PR #234 attempted to fix projection calculation issues by implementing timezone-aware period boundary calculations. However, the issue persists with projections still returning 0.00 despite the user having activity data in the database. The existing logging was insufficient to diagnose the root cause.

## Solution
Added comprehensive verbose logging to the `stats_period_summary` Lambda function to help diagnose why queries are returning no results.

## New Logging Features

### 1. Activity Data Debug Section
**Location**: After authentication, before timezone query  
**Purpose**: Show what activities actually exist in the database for the athlete

```python
print(f"\n--- ACTIVITY DATA DEBUG ---")
# Shows the 5 most recent activities with:
# - activity_id
# - start_date_local
# - timezone
# - distance_on_trail
print("--- END ACTIVITY DATA DEBUG ---\n")
```

**Benefits**:
- Confirms whether activities exist in the database
- Shows the actual start_date_local format being stored
- Shows timezone values from Strava
- Shows distance_on_trail values

### 2. Enhanced Timezone Query Logging
**Location**: Timezone query section  
**Added logging**:
- Raw database result from timezone query
- Parsed timezone field structure
- Whether stringValue exists in the field
- Detailed error messages when timezone not found

**Benefits**:
- Understand if timezone query is working correctly
- See the exact structure of RDS Data API responses
- Identify issues with timezone field parsing

### 3. Detailed SQL Query Logging in aggregate_distance()
**Added logging**:
- The complete SQL query being executed
- All parameter values being passed to the query
- Raw database result structure
- Full query result inspection

**Benefits**:
- See the exact SQL and parameters being used
- Verify date range calculations are correct
- Inspect raw RDS Data API response structure

### 4. Debug Query When No Results Found
**Location**: In aggregate_distance() when query returns 0 results  
**Purpose**: Show what activities exist and why they don't match

**Features**:
- Lists all activities with distance for the athlete (up to 10)
- Shows each activity's:
  - activity_id
  - start_date_local
  - distance_on_trail
- Compares each activity's date against the query range
- Flags activities that SHOULD match but don't (indicating a query problem)

**Benefits**:
- Identifies if it's a data problem (no activities) vs query problem (activities exist but don't match)
- Shows exact date mismatches to identify timezone or date format issues
- Helps pinpoint if the period boundary calculation is wrong

## Expected Diagnostic Output

With this logging, when the issue occurs again, we'll see:

1. **If no activities exist**: "No activities found for athlete X"
2. **If activities exist but dates don't match**: List of activities with their dates, showing they fall outside the query range
3. **If activities SHOULD match**: Explicit flag showing "This activity SHOULD match the query range!"
4. **Timezone issues**: Raw timezone data and any parsing errors

## Example Log Analysis Scenarios

### Scenario 1: No Activities in Database
```
Recent activities for athlete 3519964:
  No activities found for athlete 3519964
```
**Diagnosis**: User needs to sync activities from Strava

### Scenario 2: Timezone Mismatch
```
Recent activities for athlete 3519964:
  1. Activity 12345: start_date_local=2026-02-14 15:30:00, timezone=(GMT-08:00) America/Los_Angeles, distance_on_trail=5000m
...
Processing week:
  Current period: 2026-02-09 00:00:00 to 2026-02-15 23:59:59
  Querying with athlete_id=3519964, start=2026-02-09 00:00:00, end=2026-02-15 23:59:59
  No records returned from query
  DEBUG: All activities with distance for athlete 3519964:
    Activity 12345: start_date_local=2026-02-14 15:30:00, distance=5000m
      ^ This activity SHOULD match the query range!
```
**Diagnosis**: Query is failing despite matching date range - possible SQL parameter issue or timezone handling problem

### Scenario 3: Wrong Period Boundaries
```
Recent activities for athlete 3519964:
  1. Activity 12345: start_date_local=2026-02-14 15:30:00, timezone=(GMT-08:00) America/Los_Angeles, distance_on_trail=5000m
...
Current time in athlete timezone (America/Los_Angeles): 2026-02-14T15:30:00
Processing week:
  Current period: 2026-02-16 00:00:00 to 2026-02-22 23:59:59
```
**Diagnosis**: Period boundaries are calculated incorrectly, looking at the wrong week

## Files Modified
- `backend/stats_period_summary/lambda_function.py` - Added verbose logging throughout

## Security Considerations

### Logging Sensitive Data
The verbose logging added in this PR logs query parameters, raw database results, and activity data including:
- Athlete IDs
- Activity dates and times
- Distance values
- Activity IDs

**Justification for including this data**:
1. This is diagnostic logging for debugging a specific issue
2. CloudWatch logs are access-controlled (AWS IAM permissions required)
3. The data logged is the athlete's own activity data during their authenticated request
4. No authentication tokens, secrets, or personally identifiable information (PII) is logged

**Recommendations**:
- Once the issue is diagnosed and fixed, consider removing or reducing verbose logging
- Or add an environment variable flag (e.g., `VERBOSE_LOGGING=true`) to enable/disable this logging
- Ensure CloudWatch log retention policies are appropriate for your security requirements

### Exception Handling
The code uses specific exception types (`ValueError`, `TypeError`) rather than bare except clauses to avoid silently catching system exceptions.

## Deployment
The changes only add logging and do not modify any business logic. They are safe to deploy and will provide critical diagnostic information on the next invocation.

## Next Steps
After this is deployed:
1. Reproduce the issue by calling the endpoint
2. Review CloudWatch logs with new verbose output
3. Identify the root cause based on the diagnostic information
4. Create a targeted fix for the specific issue found
