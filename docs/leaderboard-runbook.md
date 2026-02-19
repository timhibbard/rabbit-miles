# Leaderboard Feature Runbook

## Overview

The admin-only leaderboard feature allows authorized administrators to view runner rankings by time period (week, month, year). This document provides operational guidance for deploying, monitoring, and rolling back the feature.

## Feature Status

- **Current State**: Admin-only (pre-release testing)
- **Rollout Flag**: `leaderboard_public_enabled` (default: false)
- **Access Control**: Restricted to users in `ADMIN_ATHLETE_IDS` environment variable

## Architecture

### Database Components

1. **users.show_on_leaderboards** (boolean, default true)
   - Controls user opt-in/opt-out for leaderboard visibility
   - Existing users backfilled to `true`
   - Can be toggled via Settings page

2. **leaderboard_agg** table
   - Pre-computed aggregations by window (week, month, year)
   - Updated incrementally by webhook processor
   - Indexed for efficient ranking queries

### Backend Components

1. **webhook_processor** Lambda
   - Updates leaderboard aggregates when activities are created/updated/deleted
   - Respects `show_on_leaderboards` setting
   - Implements idempotency to prevent double-counting

2. **leaderboard_get** Lambda
   - GET /leaderboard endpoint
   - Admin-only access
   - Returns current rankings and previous period top 3

3. **leaderboard_user_contrib** Lambda
   - GET /users/:id/leaderboard_contrib endpoint
   - Returns activities contributing to user's leaderboard aggregate

4. **update_user_settings** Lambda
   - PATCH /user/settings endpoint
   - Allows users to toggle `show_on_leaderboards`

### Frontend Components

1. **Leaderboard.jsx** page
   - Admin-only route at `/leaderboard`
   - Window selector (week, month, year)
   - Current rankings table
   - Previous period top 3 display
   - User's current rank (if applicable)

2. **Settings page** updates
   - Leaderboard privacy toggle
   - Explanatory text

3. **Navigation** updates
   - Leaderboard link only visible to admins

## Deployment

### Prerequisites

1. Run database migrations:
   ```sql
   -- 007_add_show_on_leaderboards.sql
   -- 008_create_leaderboard_agg_table.sql
   ```

2. Deploy updated Lambda functions:
   - webhook_processor
   - leaderboard_get (new)
   - leaderboard_user_contrib (new)
   - update_user_settings (new)
   - admin_recalculate_leaderboard (new)
   - me (updated to include show_on_leaderboards)

3. Configure API Gateway routes:
   - GET /leaderboard → leaderboard_get
   - GET /users/:id/leaderboard_contrib → leaderboard_user_contrib
   - PATCH /user/settings → update_user_settings
   - POST /admin/leaderboard/recalculate → admin_recalculate_leaderboard

4. Set environment variables:
   - All leaderboard Lambdas need: `ADMIN_ATHLETE_IDS`, `APP_SECRET`, `FRONTEND_URL`, `DB_CLUSTER_ARN`, `DB_SECRET_ARN`

### GitHub Actions Updates

If new Lambda functions are added, update `.github/workflows/deploy-lambdas.yml` to include:
- leaderboard_get
- leaderboard_user_contrib
- update_user_settings
- admin_recalculate_leaderboard

## Monitoring

### Telemetry Events

The feature emits the following telemetry events to CloudWatch:

1. **leaderboard_api_call**
   - When: Admin views leaderboard
   - Data: admin_id, window, metric, activity_type

2. **leaderboard_page_view**
   - When: Frontend loads leaderboard page
   - Data: window, window_key

3. **leaderboard_agg_update_start**
   - When: Webhook processor starts updating aggregates
   - Data: athlete_id, activity_id

4. **leaderboard_agg_update_complete**
   - When: Aggregate update succeeds
   - Data: athlete_id, activity_id, duration_ms

5. **leaderboard_agg_error**
   - When: Aggregate update fails
   - Data: athlete_id, error, duration_ms

6. **leaderboard_agg_delete_start/complete/error**
   - When: Activity deletion affects aggregates
   - Similar data to update events

### CloudWatch Queries

```
# Count leaderboard API calls by window
fields @timestamp, window, metric
| filter @message like /TELEMETRY - leaderboard_api_call/
| stats count() by window

# Track aggregate update performance
fields @timestamp, athlete_id, duration_ms
| filter @message like /TELEMETRY - leaderboard_agg_update_complete/
| stats avg(duration_ms), max(duration_ms), count() by bin(5m)

# Find aggregate errors
fields @timestamp, athlete_id, error
| filter @message like /TELEMETRY - leaderboard_agg_error/
```

### Health Checks

1. **Aggregate freshness**: Check `leaderboard_agg.last_updated` for recent updates
2. **Data consistency**: Verify aggregate sums match actual activity data
3. **Admin access**: Test admin endpoints return 403 for non-admin users
4. **Opt-out behavior**: Verify opted-out users don't appear in rankings

## Initial Setup

### First-Time Deployment

After deploying the leaderboard feature for the first time, the `leaderboard_agg` table will be empty. To populate it with historical data:

1. **Ensure users have activities**: Use the admin backfill activities endpoint for each user if needed:
   ```bash
   POST /admin/users/{athlete_id}/backfill-activities
   ```

2. **Recalculate leaderboard aggregates**: Once activities exist in the database, run the recalculation:
   ```bash
   POST /admin/leaderboard/recalculate
   ```

3. **Verify data**: Check that aggregates were created:
   ```sql
   SELECT window_key, metric, activity_type, COUNT(*) as athlete_count, SUM(value) as total_distance
   FROM leaderboard_agg
   GROUP BY window_key, metric, activity_type
   ORDER BY window_key DESC;
   ```

### Ongoing Operations

After initial setup, the `webhook_processor` Lambda will automatically update aggregates as new activities are created, updated, or deleted via Strava webhooks. Manual recalculation should only be needed if:
- Data corruption occurs
- The table is accidentally truncated
- Logic bugs are fixed and need re-application to historical data

## Troubleshooting

### Issue: Leaderboard not updating after new activities

**Diagnosis**:
1. Check webhook processor logs for errors
2. Verify `show_on_leaderboards` is true for the user
3. Check if activity date falls within current window

**Resolution**:
- Review webhook processor CloudWatch logs
- Manually trigger activity update if needed
- Check idempotency table for duplicate event prevention

### Issue: Incorrect rankings or missing users

**Diagnosis**:
1. Query `leaderboard_agg` table directly
2. Check user's `show_on_leaderboards` setting
3. Verify window_key calculation

**Resolution**:
```sql
-- Check user's aggregate
SELECT * FROM leaderboard_agg 
WHERE athlete_id = <user_id> AND window_key = '<current_window_key>';

-- Check if there are any aggregates at all
SELECT COUNT(*) FROM leaderboard_agg;
```

**Recalculate Aggregates (Admin API)**:
If the `leaderboard_agg` table is empty or has incorrect data, use the admin recalculation endpoint:

```bash
# Recalculate all aggregates from activities since Jan 1, 2026
POST /admin/leaderboard/recalculate

# Example using curl:
curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
  -H "Cookie: rm_session=<admin_session_cookie>" \
  -H "Content-Type: application/json"

# Response:
{
  "message": "Leaderboard recalculation completed successfully",
  "activities_processed": 1234,
  "athletes_processed": 56,
  "duration_ms": 1234.56
}
```

This endpoint:
- Clears the `leaderboard_agg` table
- Recalculates all aggregates from the `activities` table
- Only includes activities from users with `show_on_leaderboards = true`
- Processes activities from Jan 1, 2026 onwards
- Admin-only access (requires session cookie and admin allowlist)

### Issue: Previous period top 3 not showing

**Diagnosis**:
1. Check if previous window data exists
2. Verify window key calculation

**Resolution**:
- Previous period data may not exist yet (new feature)
- Data accumulates over time as activities are processed

## Rollback Procedures

### Level 1: Disable Frontend Access (Immediate)

```javascript
// In Leaderboard.jsx, add early return
if (!isAdmin || !import.meta.env.VITE_LEADERBOARD_ENABLED) {
  navigate('/');
  return null;
}
```

Redeploy frontend with environment variable:
```bash
VITE_LEADERBOARD_ENABLED=false npm run build
```

### Level 2: Disable Backend Updates (Quick)

Option A - Lambda environment variable:
```bash
# Add to webhook_processor Lambda
LEADERBOARD_UPDATES_DISABLED=true
```

Option B - Code change:
```python
# In webhook_processor/lambda_function.py
LEADERBOARD_UPDATES_DISABLED = os.environ.get("LEADERBOARD_UPDATES_DISABLED", "false").lower() == "true"

if not LEADERBOARD_UPDATES_DISABLED:
    update_leaderboard_aggregates(owner_id, activity)
```

### Level 3: Remove API Routes (Moderate)

Remove or disable API Gateway routes:
- GET /leaderboard
- GET /users/:id/leaderboard_contrib

### Level 4: Database Rollback (Full)

If data issues occur:
```sql
-- Disable future updates
ALTER TABLE users ALTER COLUMN show_on_leaderboards SET DEFAULT false;

-- Clear aggregate data (preserves table structure)
TRUNCATE TABLE leaderboard_agg;

-- Or drop tables entirely (destructive)
DROP TABLE IF EXISTS leaderboard_agg;
ALTER TABLE users DROP COLUMN IF EXISTS show_on_leaderboards;
```

## Testing Checklist

### Pre-Deployment

- [ ] Database migrations applied successfully
- [ ] Lambda functions deployed with correct environment variables
- [ ] API Gateway routes configured
- [ ] Admin allowlist configured with test user

### Post-Deployment

- [ ] Admin can access /leaderboard page
- [ ] Non-admin gets 403 on API calls
- [ ] Non-admin cannot see leaderboard navigation link
- [ ] Settings toggle updates show_on_leaderboards
- [ ] New activities trigger aggregate updates
- [ ] Opted-out users don't appear in rankings
- [ ] Previous period top 3 displays correctly
- [ ] Window switching works (week, month, year)
- [ ] User's rank displays if they have data

## Rollout Plan

### Phase 1: Admin-Only Testing (Current)

- Access restricted to `ADMIN_ATHLETE_IDS`
- Feature flag: `leaderboard_public_enabled = false`
- Duration: 1-2 weeks
- Goals: Validate logic, UI, performance

### Phase 2: Beta Test (Future)

- Expand `ADMIN_ATHLETE_IDS` to include beta testers
- Feature flag: `leaderboard_public_enabled = false`
- Duration: 2-4 weeks
- Goals: Gather user feedback, load testing

### Phase 3: Public Release (Future)

- Remove admin-only restriction
- Feature flag: `leaderboard_public_enabled = true`
- Gradual rollout: 10% → 50% → 100%
- Goals: Full public availability

## Support

For issues or questions:
- **Developer**: Check CloudWatch logs first
- **Admin**: Contact tim@rabbitmiles.com
- **Documentation**: This runbook + code comments

## Changelog

- 2026-02-15: Initial implementation (admin-only)
