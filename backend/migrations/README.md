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

Run migrations in numerical order:

- `000_create_users_table.sql` - Creates the `users` table for storing user information and Strava OAuth tokens
- `001_create_oauth_states.sql` - Creates the `oauth_states` table for storing temporary OAuth state tokens during the authorization flow
- `002_add_profile_picture.sql` - Adds profile_picture column to users table (can be skipped if running 000 first)
