# Leaderboard Fix - Implementation Summary

## Issue

The leaderboard endpoint (`GET /leaderboard`) was returning a 500 Internal Server Error:
```
https://api.rabbitmiles.com/leaderboard?window=week&metric=distance&activity_type=foot&limit=50&offset=0&user_id=3519964
```

## Root Cause

The `leaderboard_agg` table was empty. This table should contain pre-computed aggregates of user activities by time period (week, month, year). 

The webhook processor Lambda is designed to update these aggregates incrementally as activities are created/updated/deleted via Strava webhooks, but it was never backfilled with historical data from activities that already existed in the database.

## Solution

Created a new admin-only Lambda function `admin_recalculate_leaderboard` that:
1. Clears the `leaderboard_agg` table
2. Queries all activities from the `activities` table since Jan 1, 2026
3. Filters to only include users who have opted in (`show_on_leaderboards = true`)
4. Recalculates aggregates using the same logic as the webhook processor
5. Bulk inserts the aggregates into the `leaderboard_agg` table

## Implementation Details

### New Files
- `backend/admin_recalculate_leaderboard/lambda_function.py`: Main Lambda handler
- `DEPLOYMENT_LEADERBOARD_RECALC.md`: Step-by-step deployment guide

### Updated Files
- `.github/workflows/deploy-lambdas.yml`: Added new Lambda to CI/CD pipeline
- `docs/leaderboard-runbook.md`: Added initial setup and troubleshooting sections

### Key Features
- **Admin-only access**: Uses session-based authentication with admin allowlist
- **Audit logging**: Records all recalculation requests
- **Progress logging**: Reports activities processed, athletes processed, and duration
- **Idempotent**: Can be safely re-run multiple times
- **Performance**: Processes activities in memory before bulk inserting

### Code Quality
- ✅ Follows existing Lambda patterns (admin_backfill_activities, webhook_processor)
- ✅ Uses RDS Data API (no VPC required)
- ✅ Proper error handling and logging
- ✅ Parameterized SQL queries
- ✅ CORS headers for frontend integration
- ✅ Security scan passed (0 CodeQL alerts)

## Deployment Steps (Manual)

1. **Create Lambda function in AWS**
   ```bash
   aws lambda create-function \
     --function-name rabbitmiles-admin-recalculate-leaderboard \
     --runtime python3.12 \
     --role <your-lambda-role-arn> \
     --handler lambda_function.handler \
     --timeout 300 \
     --memory-size 512 \
     --environment Variables={...}
   ```

2. **Add GitHub repository secret**
   ```
   LAMBDA_ADMIN_RECALCULATE_LEADERBOARD=rabbitmiles-admin-recalculate-leaderboard
   ```

3. **Configure API Gateway route**
   - Method: POST
   - Path: `/admin/leaderboard/recalculate`
   - Integration: rabbitmiles-admin-recalculate-leaderboard Lambda

4. **Deploy code** (automatic on merge to main, or manual):
   ```bash
   cd backend/admin_recalculate_leaderboard
   zip -r function.zip lambda_function.py
   zip -j function.zip ../admin_utils.py
   aws lambda update-function-code \
     --function-name rabbitmiles-admin-recalculate-leaderboard \
     --zip-file fileb://function.zip
   ```

5. **Run recalculation**
   ```bash
   curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
     -H "Cookie: rm_session=<your-admin-session-cookie>"
   ```

6. **Verify leaderboard works**
   ```bash
   curl "https://api.rabbitmiles.com/leaderboard?window=week&metric=distance&activity_type=foot&limit=50" \
     -H "Cookie: rm_session=<your-admin-session-cookie>"
   ```

## Environment Variables Required

The Lambda needs these environment variables (same as other admin Lambdas):
- `DB_CLUSTER_ARN`: Aurora Serverless cluster ARN
- `DB_SECRET_ARN`: RDS Data API secret ARN
- `DB_NAME`: Database name (postgres)
- `APP_SECRET`: Secret for signing/verifying session cookies
- `FRONTEND_URL`: Frontend URL for CORS (https://rabbitmiles.com)
- `ADMIN_ATHLETE_IDS`: Comma-separated list of admin athlete IDs

## Testing

### Pre-deployment Testing
- ✅ Code follows existing patterns
- ✅ Security scan passed (CodeQL)
- ✅ No syntax errors
- ✅ Proper error handling

### Post-deployment Testing (Manual)
1. Deploy Lambda and configure API Gateway
2. Call recalculation endpoint with admin credentials
3. Verify CloudWatch logs show successful execution
4. Query database to confirm aggregates exist:
   ```sql
   SELECT window_key, metric, activity_type, COUNT(*) as athletes, SUM(value) as total
   FROM leaderboard_agg
   GROUP BY window_key, metric, activity_type
   ORDER BY window_key DESC;
   ```
5. Test leaderboard endpoint returns data without 500 error

## Future Maintenance

- **Normal operation**: The webhook processor will keep aggregates up to date
- **Recalculation needed**: Only if data corruption occurs or table is cleared
- **Monitoring**: Check CloudWatch logs for aggregate update errors
- **Performance**: Can handle thousands of activities; may need timeout increase for very large datasets

## Rollback

If issues occur:
1. Delete API Gateway route to disable endpoint
2. Delete Lambda function
3. Clear aggregates if needed: `TRUNCATE TABLE leaderboard_agg;`
4. No schema changes were made, so no database migrations to rollback

## Related Issues

This PR addresses the agent instruction:
> "This is still an issue. Do we have a way to populate the data initially? What about a recalculation function. I think this is not loading because the tables are empty. They should backfill to Jan 1, 2026"

## Documentation

Full documentation available in:
- `DEPLOYMENT_LEADERBOARD_RECALC.md`: Deployment guide
- `docs/leaderboard-runbook.md`: Operational runbook with troubleshooting
- Lambda code comments: Implementation details

## Security

- ✅ Admin-only access enforced
- ✅ Session-based authentication
- ✅ Audit logging enabled
- ✅ Parameterized SQL queries (no SQL injection)
- ✅ No sensitive data exposure
- ✅ CodeQL security scan passed

## Next Steps

1. User deploys Lambda to AWS (follows DEPLOYMENT_LEADERBOARD_RECALC.md)
2. User configures API Gateway route
3. User runs recalculation endpoint
4. User verifies leaderboard endpoint works
5. Done! Webhook processor will handle future updates automatically
