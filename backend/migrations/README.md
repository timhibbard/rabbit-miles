# Database Migrations

This directory contains SQL migration scripts for the RabbitMiles backend database.

## Running Migrations

These migrations should be run against the AWS RDS Aurora Serverless PostgreSQL database using the RDS Data API or psql client.

### Using RDS Data API (AWS CLI)

```bash
aws rds-data execute-statement \
  --resource-arn "arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:DATABASE_CLUSTER" \
  --secret-arn "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:SECRET_NAME" \
  --database "postgres" \
  --sql "$(cat backend/migrations/001_create_oauth_states.sql)"
```

### Using psql

If you have direct database access:

```bash
psql -h DATABASE_HOST -U USERNAME -d postgres -f backend/migrations/001_create_oauth_states.sql
```

## Migration List

- `001_create_oauth_states.sql` - Creates the `oauth_states` table for storing temporary OAuth state tokens during the authorization flow
- `002_add_profile_picture.sql` - Adds `profile_picture` column to `users` table
- `003_create_activities_table.sql` - Creates the `activities` table for storing Strava activity data
- `004_add_trail_time_distance.sql` - Adds `time_on_trail` and `distance_on_trail` columns to track trail-specific metrics
- `004_create_webhook_events_table.sql` - Creates the `webhook_events` table for storing incoming Strava webhook events
- `005_add_last_matched_to_activities.sql` - Adds `last_matched` column to `activities` table
- `006_add_athlete_count.sql` - Adds `athlete_count` column to track the number of athletes who participated in group activities
- `007_add_show_on_leaderboards.sql` - Adds `show_on_leaderboards` column to `users` table for leaderboard privacy control
- `008_create_leaderboard_agg_table.sql` - Creates the `leaderboard_agg` table for aggregated leaderboard data
- `009_add_user_timezone.sql` - Adds `timezone` column to `users` table for per-user timezone preference
- `010_add_last_strava_fetch.sql` - Adds `last_strava_fetch` column to `users` table to track the last successful Strava fetch per athlete and enforce a per-user cooldown
- `011_add_last_webhook_received.sql` - Adds `last_webhook_received_at` column to `users` table to track when webhooks last delivered activity updates
- `012_add_email_notifications_to_users.sql` - Adds email notification support to `users` table (email, verification status, preferences, thresholds)
- `013_create_email_notifications_table.sql` - Creates `email_notifications` table to track sent notifications and prevent duplicates
- `014_add_notification_sent_flag.sql` - Adds `notifications_sent` flag to `activities` table to prevent notifications for historical/reprocessed activities
