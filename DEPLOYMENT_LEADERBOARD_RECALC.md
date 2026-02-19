# Leaderboard Recalculation Deployment Guide

## Summary

This deployment adds a new Lambda function `admin_recalculate_leaderboard` that populates the `leaderboard_agg` table from existing activities. This solves the issue where the leaderboard endpoint returns a 500 error because the aggregates table is empty.

## Problem

The leaderboard endpoint (`GET /leaderboard`) is returning a 500 Internal Server Error because the `leaderboard_agg` table is empty. This table should be automatically populated by the `webhook_processor` Lambda when activities are created/updated/deleted, but it was never backfilled with historical data.

## Solution

A new Lambda function `admin_recalculate_leaderboard` recalculates all leaderboard aggregates from the `activities` table, processing all activities since January 1, 2026.

## Deployment Steps

### 1. Create the Lambda Function in AWS

```bash
# Function name (add to repository secrets)
LAMBDA_ADMIN_RECALCULATE_LEADERBOARD=rabbitmiles-admin-recalculate-leaderboard

# Create the Lambda function
aws lambda create-function \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/YOUR_LAMBDA_ROLE \
  --handler lambda_function.handler \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    DB_CLUSTER_ARN=YOUR_DB_CLUSTER_ARN,
    DB_SECRET_ARN=YOUR_DB_SECRET_ARN,
    DB_NAME=postgres,
    APP_SECRET=YOUR_APP_SECRET,
    FRONTEND_URL=https://rabbitmiles.com,
    ADMIN_ATHLETE_IDS=YOUR_ADMIN_IDS
  }" \
  --zip-file fileb://function.zip
```

### 2. Add Repository Secret

Add the Lambda function name to GitHub repository secrets:

```
LAMBDA_ADMIN_RECALCULATE_LEADERBOARD=rabbitmiles-admin-recalculate-leaderboard
```

### 3. Configure API Gateway Route

Add a new route to your API Gateway:

- **Method**: POST
- **Path**: `/admin/leaderboard/recalculate`
- **Integration**: Lambda function `rabbitmiles-admin-recalculate-leaderboard`
- **Authorization**: None (uses cookie-based session auth)

### 4. Deploy the Lambda Code

The Lambda will be automatically deployed by the GitHub Actions workflow when changes are merged to `main`. Alternatively, deploy manually:

```bash
cd backend/admin_recalculate_leaderboard
zip -r function.zip lambda_function.py
zip -j function.zip ../admin_utils.py

aws lambda update-function-code \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --zip-file fileb://function.zip
```

### 5. Run the Recalculation

Once deployed, trigger the recalculation endpoint:

```bash
curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
  -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE" \
  -H "Content-Type: application/json"
```

You can get your admin session cookie by:
1. Logging into https://rabbitmiles.com as an admin user
2. Opening browser DevTools → Application → Cookies
3. Copy the `rm_session` cookie value

Expected response:
```json
{
  "message": "Leaderboard recalculation completed successfully",
  "activities_processed": 1234,
  "athletes_processed": 56,
  "duration_ms": 1234.56
}
```

### 6. Verify the Leaderboard

After recalculation, the leaderboard endpoint should work:

```bash
curl "https://api.rabbitmiles.com/leaderboard?window=week&metric=distance&activity_type=foot&limit=50&offset=0&user_id=YOUR_USER_ID" \
  -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE"
```

Expected response:
```json
{
  "rows": [
    {
      "rank": 1,
      "user": {
        "id": 123456,
        "display_name": "John Doe",
        "avatar_url": "https://..."
      },
      "value": 50000.0,
      "last_updated": "2026-02-19T..."
    },
    ...
  ],
  "my_rank": {...},
  "previous_top3": [...],
  "cursor": "50",
  "window_key": "week_2026-02-17",
  "metric": "distance",
  "activity_type": "foot",
  "total_returned": 50
}
```

## Environment Variables

The Lambda function requires these environment variables (same as other admin Lambdas):

- `DB_CLUSTER_ARN`: Aurora Serverless cluster ARN
- `DB_SECRET_ARN`: RDS Data API secret ARN
- `DB_NAME`: Database name (postgres)
- `APP_SECRET`: Secret for signing/verifying session cookies
- `FRONTEND_URL`: Frontend URL for CORS (https://rabbitmiles.com)
- `ADMIN_ATHLETE_IDS`: Comma-separated list of admin athlete IDs

## Security

- Admin-only access: Requires valid session cookie with admin athlete ID
- Uses existing admin authentication infrastructure (`admin_utils.py`)
- Audit logs all recalculation requests
- Does not expose sensitive data

## Performance

- Typical execution time: 1-5 seconds for hundreds of activities
- Lambda timeout: 5 minutes (300 seconds)
- Lambda memory: 512 MB (can be increased if needed)
- Processes activities in memory before bulk inserting

## Rollback

If issues occur, you can:

1. Delete the API Gateway route
2. Delete the Lambda function
3. Clear the aggregates table if needed:
   ```sql
   TRUNCATE TABLE leaderboard_agg;
   ```

## Future Considerations

- This endpoint should only be needed rarely (initial setup, data corruption)
- The webhook processor handles incremental updates automatically
- Consider adding a scheduled recalculation (e.g., weekly) for data consistency checks
- Could be enhanced to support partial recalculation (single user, date range, etc.)

## Testing

### Local Testing

You cannot easily test this Lambda locally as it requires:
- AWS RDS Data API credentials
- Access to the production database
- Admin session cookie

### Production Testing

1. Deploy to production
2. Use your admin account to call the endpoint
3. Verify CloudWatch logs show successful execution
4. Check database for populated `leaderboard_agg` records
5. Test leaderboard endpoint returns data

## Troubleshooting

### Issue: Lambda times out

**Solution**: Increase Lambda timeout to 10 minutes or memory to 1024 MB

### Issue: "not authenticated" error

**Solution**: Ensure your session cookie is valid and you're in the admin allowlist

### Issue: "no activities found"

**Solution**: Users need to have activities in the `activities` table first. Use the backfill activities endpoint:
```bash
POST /admin/users/{athlete_id}/backfill-activities
```

### Issue: Aggregates still incorrect after recalculation

**Solution**: Check CloudWatch logs for errors. Verify users have `show_on_leaderboards = true`:
```sql
SELECT athlete_id, show_on_leaderboards FROM users;
```

## Related Documentation

- [Leaderboard Runbook](./docs/leaderboard-runbook.md)
- [Admin Backfill Activities Lambda](./backend/admin_backfill_activities/lambda_function.py)
- [Webhook Processor Lambda](./backend/webhook_processor/lambda_function.py)
