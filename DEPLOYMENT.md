# OAuth State Validation Fix - Deployment Guide

## Overview
This fix resolves the "invalid state" error in the OAuth callback flow by storing OAuth states in a database table instead of relying solely on cookies.

## Prerequisites
- AWS CLI configured with appropriate credentials
- Access to the RDS cluster and Secrets Manager

## Deployment Steps

### 1. Run the Database Migration

The migration creates the `oauth_states` table required for the new state validation logic.

#### Option A: Using AWS CLI (Recommended)

```bash
# Set your environment variables
export DB_CLUSTER_ARN="arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:YOUR_CLUSTER"
export DB_SECRET_ARN="arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:YOUR_SECRET"
export DB_NAME="postgres"

# Run the migration
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "$DB_NAME" \
  --sql "$(cat backend/migrations/001_create_oauth_states.sql)"
```

#### Option B: Using psql (if you have direct access)

```bash
psql -h YOUR_DATABASE_HOST -U YOUR_USERNAME -d postgres -f backend/migrations/001_create_oauth_states.sql
```

### 2. Update Lambda Environment Variables

Ensure the `auth_start` Lambda function has these environment variables:
- `DB_CLUSTER_ARN` - ARN of your RDS cluster
- `DB_SECRET_ARN` - ARN of your database credentials secret
- `DB_NAME` - Database name (default: "postgres")
- `API_BASE_URL` - Your API Gateway base URL
- `STRAVA_CLIENT_ID` - Your Strava OAuth client ID

The `auth_callback` Lambda already has these variables.

### 3. Deploy Lambda Functions

Deploy the updated Lambda functions:

#### Using AWS CLI
```bash
# Package and deploy auth_start
cd backend/auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_START_FUNCTION_NAME \
  --zip-file fileb://function.zip

# Package and deploy auth_callback  
cd ../auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION_NAME \
  --zip-file fileb://function.zip
```

#### Using Infrastructure as Code
If you're using Terraform, CloudFormation, or SAM, update your deployment configuration to include the new Lambda code and redeploy.

### 4. Verify the Fix

1. Navigate to your frontend application
2. Click "Connect with Strava"
3. Authorize the application on Strava
4. Verify you are successfully redirected back without the "invalid state" error

## Rollback Plan

If you need to rollback:

1. Deploy the previous version of the Lambda functions
2. The migration is backwards compatible - the table can remain in the database
3. The old code will fall back to cookie-based validation

## Optional: Set Up Periodic Cleanup

The `oauth_states` table will accumulate old entries over time. Consider setting up a scheduled cleanup job:

```sql
-- Clean up expired states (run this periodically)
DELETE FROM oauth_states WHERE expires_at < EXTRACT(EPOCH FROM NOW());
```

You can create a Lambda function triggered by CloudWatch Events (EventBridge) to run this query daily.

## Troubleshooting

### "Table does not exist" error
- Ensure the migration has been run successfully
- Check CloudWatch Logs for the Lambda function to see detailed error messages

### OAuth still failing with "invalid state"
- Verify the Lambda functions have been deployed with the new code
- Check that the environment variables are set correctly
- Review CloudWatch Logs for database connection errors

### Database connection errors
- Verify the Lambda execution role has permissions to access RDS Data API
- Ensure `DB_CLUSTER_ARN` and `DB_SECRET_ARN` are correct
- Check that the database security group allows connections from Lambda

## Security Considerations

- OAuth states expire after 10 minutes
- States are single-use (deleted after validation)
- Backward compatibility with cookie-based validation is maintained
- No sensitive data is stored in the states table (only random tokens)
