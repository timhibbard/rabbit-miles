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
