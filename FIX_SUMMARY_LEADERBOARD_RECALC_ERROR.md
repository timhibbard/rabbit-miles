# Fix for Leaderboard Recalculation Error

## Issue Summary

**Error Message:**
```
Recalculation failed: An error occurred (DatabaseErrorException) when calling the ExecuteStatement operation: ERROR: relation "leaderboard_agg" does not exist; Position: 13; SQLState: 42P01
```

**Root Cause:**
The database migration `backend/migrations/008_create_leaderboard_agg_table.sql` was not applied to the RDS Aurora database before attempting to run the leaderboard recalculation Lambda function.

## Solution Implemented

This fix implements a defensive programming approach with minimal changes:

### 1. Code Changes (backend/admin_recalculate_leaderboard/lambda_function.py)

Added a pre-check to verify the `leaderboard_agg` table exists before attempting any operations:

```python
# Step 0: Verify that leaderboard_agg table exists
print("LOG - Checking if leaderboard_agg table exists")
check_table_sql = """
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'leaderboard_agg'
);
"""
result = exec_sql(check_table_sql)
records = result.get("records", [])

# Safely extract the boolean value
table_exists = False
if records and len(records) > 0 and len(records[0]) > 0:
    table_exists = records[0][0].get("booleanValue", False)

if not table_exists:
    error_msg = (
        "The leaderboard_agg table does not exist. "
        "Please run the database migration: backend/migrations/008_create_leaderboard_agg_table.sql"
    )
    print(f"ERROR: {error_msg}")
    return 0, 0, error_msg

print("LOG - leaderboard_agg table exists")
```

**Key Features:**
- Uses PostgreSQL `information_schema.tables` to check table existence
- Safely handles edge cases (empty records, missing keys)
- Returns a clear, actionable error message
- No changes to business logic when table exists
- No breaking changes to existing functionality

### 2. Documentation Updates

Updated deployment guides to make the migration a clear prerequisite:

#### QUICKSTART_LEADERBOARD_FIX.md
- Added **Step 0: Run Database Migration (REQUIRED - 2 minutes)**
- Included migration command using AWS RDS Data API
- Added verification step to confirm table creation
- Updated troubleshooting section with specific error

#### DEPLOYMENT_LEADERBOARD_RECALC.md
- Added **Step 0: Run Database Migration (REQUIRED - FIRST)**
- Included detailed explanation of why it's required
- Added verification commands
- Explained the error message users will see if skipped

## How to Use This Fix

### For Users Who See This Error

If you encounter the "relation 'leaderboard_agg' does not exist" error, follow these steps:

1. **Run the database migration** (replace with your actual values):
   ```bash
   aws rds-data execute-statement \
     --resource-arn "$DB_CLUSTER_ARN" \
     --secret-arn "$DB_SECRET_ARN" \
     --database "postgres" \
     --sql "$(cat backend/migrations/008_create_leaderboard_agg_table.sql)"
   ```

2. **Verify the migration succeeded:**
   ```bash
   aws rds-data execute-statement \
     --resource-arn "$DB_CLUSTER_ARN" \
     --secret-arn "$DB_SECRET_ARN" \
     --database "postgres" \
     --sql "SELECT COUNT(*) FROM leaderboard_agg;"
   ```
   
   Expected result: `0` (table exists but is empty)

3. **Deploy the updated Lambda code** (from this PR)

4. **Run the recalculation again:**
   ```bash
   curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
     -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE"
   ```

### For New Deployments

Follow the updated deployment guides:
- See `QUICKSTART_LEADERBOARD_FIX.md` for a quick start
- See `DEPLOYMENT_LEADERBOARD_RECALC.md` for detailed instructions
- **Critical:** Always run Step 0 (database migration) FIRST

## Testing

### Validation Performed

1. **Python Syntax Check:** ✓ Passed
2. **CodeQL Security Scan:** ✓ 0 alerts found
3. **Table Check Logic:** ✓ Tested 4 scenarios:
   - Table exists (booleanValue: true)
   - Table doesn't exist (booleanValue: false)
   - Empty records list (edge case)
   - Missing records key (edge case)
4. **Edge Case Handling:** ✓ No exceptions thrown

### Test Results

All scenarios handled correctly without IndexError or KeyError:
- ✓ Table exists → Continues with recalculation
- ✓ Table doesn't exist → Returns helpful error message
- ✓ Empty result → Safely defaults to "table doesn't exist"
- ✓ Missing key → Safely defaults to "table doesn't exist"

## Impact Assessment

### What Changed
- One Lambda function: `admin_recalculate_leaderboard`
- Two documentation files

### What Didn't Change
- No database schema changes
- No changes to other Lambda functions
- No changes to API Gateway routes
- No changes to frontend code
- No changes to existing business logic

### Risk Level
**LOW** - This is a defensive check that only affects error handling. The Lambda will:
- Work exactly as before when the table exists
- Fail gracefully with a helpful message when the table doesn't exist
- Not impact any other functionality

## Rollback Plan

If needed, simply revert to the previous version:
```bash
git revert dad4c79 44f1cf6
```

However, this shouldn't be necessary as:
1. The change is backward compatible
2. It only adds defensive checking
3. It doesn't modify any existing logic

## Security Summary

✅ **CodeQL Scan:** 0 vulnerabilities found  
✅ **SQL Injection:** Uses parameterized queries via RDS Data API  
✅ **Authentication:** Admin-only access with session verification  
✅ **Error Messages:** Don't expose sensitive information  
✅ **Edge Cases:** All handled safely without exceptions

## Next Steps

1. **Deploy:** Merge this PR to update the Lambda code
2. **Verify:** Ensure migrations are documented as prerequisites
3. **Monitor:** Watch for the improved error message in logs
4. **Educate:** Share the updated deployment docs with the team

## References

- Issue: Recalculate leaderboard error
- Migration file: `backend/migrations/008_create_leaderboard_agg_table.sql`
- Lambda function: `backend/admin_recalculate_leaderboard/lambda_function.py`
- Deployment guides:
  - `QUICKSTART_LEADERBOARD_FIX.md`
  - `DEPLOYMENT_LEADERBOARD_RECALC.md`
  - `docs/leaderboard-runbook.md`

---

**Status:** ✅ Ready for deployment  
**Risk:** LOW  
**Security:** ✅ Scanned, 0 alerts  
**Testing:** ✅ Validated
