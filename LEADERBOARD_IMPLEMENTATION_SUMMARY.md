# Leaderboard Feature - Implementation Summary

## Overview

This PR implements an admin-only leaderboard feature for RabbitMiles. The feature allows administrators to view runner rankings by time period (week, month, year) while respecting user privacy settings. This is a pre-release version for controlled testing before public launch.

## What Changed

### Database (2 migrations)

1. **007_add_show_on_leaderboards.sql**
   - Adds `show_on_leaderboards` boolean column to users table
   - Defaults to `true` (opt-in by default)
   - Backfills all existing users to `true`
   - Creates index for efficient filtering

2. **008_create_leaderboard_agg_table.sql**
   - Creates `leaderboard_agg` table for pre-computed rankings
   - Columns: window, window_key, metric, activity_type, athlete_id, value, last_updated
   - Unique constraint on (window_key, metric, activity_type, athlete_id)
   - Three indexes for ranking queries, user queries, and cleanup

### Backend (4 new Lambda functions + 2 updates)

**New Functions:**

1. **leaderboard_get** - GET /leaderboard
   - Admin-only endpoint for viewing leaderboard
   - Query params: window (week/month/year), metric, activity_type, limit, offset, user_id
   - Returns: current rankings, user's rank, previous period top 3, cursor for pagination
   - Implements admin authorization check

2. **leaderboard_user_contrib** - GET /users/:id/leaderboard_contrib
   - Admin-only endpoint for viewing user's contributing activities
   - Query params: window
   - Returns: list of activities that contributed to user's leaderboard aggregate

3. **update_user_settings** - PATCH /user/settings
   - Allows authenticated users to toggle their `show_on_leaderboards` setting
   - Validates boolean value
   - Updates database and returns new value

**Updated Functions:**

4. **webhook_processor**
   - Extended to update leaderboard aggregates when activities are created/updated/deleted
   - Implements window calculations (current week, month, year)
   - Respects `show_on_leaderboards` setting
   - Handles incremental aggregation with delta calculation
   - Implements idempotency to prevent double-counting
   - Adds comprehensive telemetry logging

5. **me**
   - Updated to include `show_on_leaderboards` in response
   - Allows frontend to display current setting state

### Frontend (1 new page + 3 updates)

**New Page:**

1. **Leaderboard.jsx**
   - Admin-only page at /leaderboard route
   - Redirects non-admins to dashboard
   - Window selector buttons (week, month, year)
   - Current rankings table with rank, runner info, distance, last updated
   - Previous period top 3 prominently displayed
   - User's current rank shown in sticky blue banner
   - Responsive design with Tailwind CSS

**Updated Components:**

2. **Layout.jsx**
   - Added Leaderboard navigation link (only visible to admins)
   - Uses trophy icon for leaderboard

3. **Settings.jsx**
   - Added leaderboard privacy section
   - Toggle switch for show_on_leaderboards
   - Explanatory text about opt-in/opt-out
   - Calls updateUserSettings API

4. **api.js**
   - Added fetchLeaderboard() function
   - Added fetchUserLeaderboardContrib() function
   - Added updateUserSettings() function
   - All properly handle auth errors and admin access

5. **App.jsx**
   - Added /leaderboard route

### Documentation

**leaderboard-runbook.md**
- Complete operational guide
- Architecture overview
- Deployment checklist
- Monitoring guide (telemetry events, CloudWatch queries)
- Troubleshooting scenarios
- 4-level rollback procedures
- Testing checklist
- Rollout plan (3 phases: admin-only → beta → public)

### CI/CD

**.github/workflows/deploy-lambdas.yml**
- Added three new Lambda functions to deployment matrix
- All marked as `needs_utils: true` to include admin_utils.py

## Key Features

### Admin-Only Access
- All leaderboard endpoints check admin status via `ADMIN_ATHLETE_IDS` environment variable
- Non-admin requests return 403 Forbidden
- Leaderboard link hidden in navigation for non-admins
- Frontend redirects non-admins attempting to access /leaderboard

### Privacy Controls
- Users can opt-in/opt-out via Settings page
- Opted-out users excluded from rankings
- Default is opt-in (show_on_leaderboards = true)
- Setting respects user privacy preferences

### Time Windows
- Three windows supported: week, month, year
- Week: Monday to Sunday (ISO week format)
- Month: First to last day of calendar month
- Year: January 1 to December 31

### Previous Period Top 3
- Displays top 3 runners from previous period
- Week → last week, Month → last month, Year → last year
- Shows medals (🥇🥈🥉) and runner details
- Helps users track performance trends

### Incremental Aggregation
- Webhook processor updates aggregates when activities are created/updated
- Delta calculation prevents double-counting on activity updates
- Deletes subtract from aggregates
- Idempotency prevents duplicate processing

### Telemetry
Six telemetry events for monitoring:
- `leaderboard_api_call` - API usage
- `leaderboard_page_view` - Frontend views
- `leaderboard_agg_update_start/complete/error` - Aggregation events
- `leaderboard_agg_delete_start/complete/error` - Deletion events

## Security

### Authentication & Authorization
- All endpoints require valid session cookie
- Admin endpoints verify athlete_id in ADMIN_ATHLETE_IDS
- Session tokens signed with APP_SECRET
- CORS configured for FRONTEND_URL only

### Data Privacy
- User profile pictures only shown if provided by Strava
- Athlete IDs only visible to admins
- No sensitive tokens exposed in responses
- Cache-Control: no-store on admin responses

### Audit Logging
- All admin actions logged to CloudWatch
- Includes timestamp, admin_athlete_id, endpoint, action, details
- Access denied attempts logged

### Code Security
- CodeQL analysis: 0 alerts found
- No SQL injection vulnerabilities (parameterized queries only)
- No secrets committed to repository
- Proper error handling with generic error messages to clients

## Testing Checklist

Before deployment, verify:

- [ ] Database migrations run successfully
- [ ] All Lambda functions deployed with correct env vars
- [ ] API Gateway routes configured
- [ ] Admin athlete IDs configured
- [ ] Admin can access /leaderboard
- [ ] Non-admin gets 403 on API calls
- [ ] Non-admin cannot see nav link
- [ ] Settings toggle updates database
- [ ] New activities trigger aggregates
- [ ] Opted-out users excluded
- [ ] Previous top 3 displays
- [ ] Window switching works
- [ ] User rank displays correctly

## Deployment Notes

### Required AWS Secrets/Environment Variables

For all new Lambda functions, configure:
- `ADMIN_ATHLETE_IDS` - Comma-separated list of admin athlete IDs
- `APP_SECRET` - Secret for session token signing
- `FRONTEND_URL` - For CORS configuration
- `DB_CLUSTER_ARN` - Aurora Serverless cluster ARN
- `DB_SECRET_ARN` - Database credentials secret ARN
- `DB_NAME` - Database name (usually "postgres")

### API Gateway Configuration

Create new routes:
- GET /leaderboard → leaderboard_get Lambda
- GET /users/:id/leaderboard_contrib → leaderboard_user_contrib Lambda
- PATCH /user/settings → update_user_settings Lambda

### GitHub Actions Secrets

Add new secrets for Lambda function names:
- `LAMBDA_LEADERBOARD_GET`
- `LAMBDA_LEADERBOARD_USER_CONTRIB`
- `LAMBDA_UPDATE_USER_SETTINGS`

## Rollback Plan

See docs/leaderboard-runbook.md for complete rollback procedures.

Quick rollback levels:
1. **Frontend**: Hide UI via environment variable
2. **Backend**: Disable aggregation updates via env var
3. **API**: Remove/disable API Gateway routes
4. **Database**: Clear or drop tables (destructive)

## Future Enhancements (Out of Scope)

This is Phase 1 (admin-only). Future phases may include:
- Public leaderboard access (remove admin restriction)
- Additional metrics (elevation gain, time, etc.)
- Activity type filtering (Run, Ride, etc.)
- Search by display name
- User profile pages
- Social features (following, comments)
- Achievements and badges
- Email notifications for rank changes

## Performance Considerations

- Leaderboard queries use indexed columns for efficiency
- Aggregates pre-computed for fast reads
- Pagination supported (limit/offset)
- Window keys designed for efficient filtering
- No N+1 query problems (JOINs used appropriately)

## Maintenance

### Monitoring
- Check CloudWatch logs for telemetry events
- Monitor aggregate update duration
- Watch for aggregation errors
- Verify data freshness

### Data Cleanup
Consider periodic cleanup of old window data:
```sql
-- Example: Delete aggregates older than 2 years
DELETE FROM leaderboard_agg 
WHERE window = 'week' 
  AND window_key < 'week_' || (CURRENT_DATE - INTERVAL '2 years')::text;
```

## Acknowledgments

Implementation follows RabbitMiles patterns:
- Cookie-based authentication (no token storage)
- RDS Data API (no database drivers)
- Admin authorization via admin_utils
- CORS configuration matching existing endpoints
- Telemetry logging for observability

## Questions?

Contact: tim@rabbitmiles.com

See docs/leaderboard-runbook.md for operational details.
