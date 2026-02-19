# 🏆 Leaderboard Fix - Quick Start Guide

## What This PR Does

This PR fixes the 500 error on the leaderboard endpoint by adding a way to populate the `leaderboard_agg` table from existing activities.

**Problem**: The leaderboard endpoint was failing because the aggregates table was empty.  
**Solution**: New admin endpoint to recalculate aggregates from the activities table.

## Files Changed

1. ✅ **New Lambda**: `backend/admin_recalculate_leaderboard/lambda_function.py`
2. ✅ **CI/CD Updated**: `.github/workflows/deploy-lambdas.yml`
3. ✅ **Docs Updated**: `docs/leaderboard-runbook.md`
4. ✅ **Deployment Guide**: `DEPLOYMENT_LEADERBOARD_RECALC.md` (detailed)
5. ✅ **Summary**: `LEADERBOARD_FIX_SUMMARY.md` (technical)

## What You Need To Do

### Step 1: Create the Lambda Function (5 minutes)

```bash
# Replace with your actual values
LAMBDA_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT:role/YOUR_LAMBDA_ROLE"
DB_CLUSTER_ARN="your-db-cluster-arn"
DB_SECRET_ARN="your-db-secret-arn"
APP_SECRET="your-app-secret"
ADMIN_IDS="your-admin-athlete-ids"

aws lambda create-function \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --runtime python3.12 \
  --role $LAMBDA_ROLE_ARN \
  --handler lambda_function.handler \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    DB_CLUSTER_ARN=$DB_CLUSTER_ARN,
    DB_SECRET_ARN=$DB_SECRET_ARN,
    DB_NAME=postgres,
    APP_SECRET=$APP_SECRET,
    FRONTEND_URL=https://rabbitmiles.com,
    ADMIN_ATHLETE_IDS=$ADMIN_IDS
  }" \
  --zip-file fileb://function.zip
```

### Step 2: Add GitHub Secret

Go to your repository settings and add:
```
Name: LAMBDA_ADMIN_RECALCULATE_LEADERBOARD
Value: rabbitmiles-admin-recalculate-leaderboard
```

### Step 3: Configure API Gateway (2 minutes)

Add a route to your API Gateway:
- **Method**: POST
- **Path**: `/admin/leaderboard/recalculate`
- **Integration**: rabbitmiles-admin-recalculate-leaderboard

### Step 4: Deploy the Code

When you merge this PR to `main`, GitHub Actions will automatically deploy the Lambda.

Or deploy manually:
```bash
cd backend/admin_recalculate_leaderboard
zip -r function.zip lambda_function.py
zip -j function.zip ../admin_utils.py
aws lambda update-function-code \
  --function-name rabbitmiles-admin-recalculate-leaderboard \
  --zip-file fileb://function.zip
```

### Step 5: Run the Recalculation (30 seconds)

```bash
# Get your admin session cookie from browser DevTools
# Then run:
curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
  -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE"
```

Expected response:
```json
{
  "message": "Leaderboard recalculation completed successfully",
  "activities_processed": 1234,
  "athletes_processed": 56,
  "duration_ms": 1234.56
}
```

### Step 6: Verify It Works

```bash
curl "https://api.rabbitmiles.com/leaderboard?window=week&metric=distance&activity_type=foot&limit=50" \
  -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE"
```

Should return data, not a 500 error! 🎉

## How It Works

1. **Normal Operation**: The `webhook_processor` Lambda updates leaderboard aggregates when Strava activities change
2. **This Fix**: Backfills historical data that existed before the leaderboard feature was deployed
3. **One-Time Use**: You should only need to run recalculation once (unless data corruption occurs)

## Architecture

```
Activities Table (populated by Strava webhooks)
        ↓
[webhook_processor] → Updates aggregates incrementally
        ↓
Leaderboard_Agg Table
        ↓
[leaderboard_get] → Returns rankings
```

This PR adds:
```
Activities Table
        ↓
[admin_recalculate_leaderboard] → Bulk recalculates all aggregates
        ↓
Leaderboard_Agg Table
```

## Troubleshooting

### "not authenticated" error
- Make sure you're using a valid admin session cookie
- Check that your athlete ID is in the ADMIN_ATHLETE_IDS environment variable

### "no activities found"
- Run the activities backfill first: `POST /admin/users/{athlete_id}/backfill-activities`
- Check users have `show_on_leaderboards = true`

### Lambda times out
- Increase Lambda timeout to 600 seconds (10 minutes)
- Increase memory to 1024 MB

### Aggregates still wrong
- Check CloudWatch logs for errors
- Try running recalculation again (it's idempotent)

## Need Help?

- 📖 **Detailed Guide**: See `DEPLOYMENT_LEADERBOARD_RECALC.md`
- 🔧 **Technical Details**: See `LEADERBOARD_FIX_SUMMARY.md`
- 📚 **Operations**: See `docs/leaderboard-runbook.md`

## Security

✅ CodeQL scan passed (0 alerts)  
✅ Admin-only access  
✅ Session-based authentication  
✅ Parameterized SQL queries  
✅ Audit logging enabled

---

**After deployment, the leaderboard should work! 🚀**
