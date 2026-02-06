# Admin Lambda Deployment Guide

This guide covers the deployment of the admin Lambda functions that were added to enable admin tooling.

## New Lambda Functions

Two new Lambda functions have been added for admin functionality:

1. **admin_list_users** - Lists all users in the system (admin only)
2. **admin_user_activities** - Views activities for any user (admin only)

## Prerequisites

Before deploying, ensure you have:

1. Created the Lambda functions in AWS
2. Configured the `ADMIN_ATHLETE_IDS` environment variable on all relevant Lambdas
3. Set up API Gateway routes for the admin endpoints

## GitHub Actions Setup

### Step 1: Add GitHub Secrets

Add these two new secrets to your GitHub repository:

1. Go to: https://github.com/timhibbard/rabbit-miles/settings/secrets/actions
2. Click **New repository secret**
3. Add each of the following:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `LAMBDA_ADMIN_LIST_USERS` | Your admin_list_users Lambda function name | `rabbitmiles-admin-list-users` or `prod-admin-list-users` |
| `LAMBDA_ADMIN_USER_ACTIVITIES` | Your admin_user_activities Lambda function name | `rabbitmiles-admin-user-activities` or `prod-admin-user-activities` |

### Step 2: Update IAM Policy

Update your GitHub deployment IAM user's policy to include the new Lambda functions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:rabbitmiles-admin-list-users",
        "arn:aws:lambda:*:*:function:rabbitmiles-admin-user-activities"
      ]
    }
  ]
}
```

Or add these ARNs to your existing deployment policy.

## Deployment

The GitHub Actions workflow will automatically:

1. Package the Lambda function code
2. Include the `admin_utils.py` dependency (automatically)
3. Deploy to AWS when you push changes to `main` branch

### Manual Deployment

To manually trigger deployment:

1. Go to **Actions** tab in GitHub
2. Click **Deploy Lambda Functions**
3. Click **Run workflow** → **Run workflow**

## Lambda Configuration

### Required Environment Variables

Both admin Lambda functions require these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_SECRET` | Session token verification secret | `<long-random-string>` |
| `FRONTEND_URL` | Frontend URL for CORS | `https://rabbitmiles.com` |
| `DB_CLUSTER_ARN` | Aurora Serverless cluster ARN | `arn:aws:rds:us-east-1:...` |
| `DB_SECRET_ARN` | Database credentials secret ARN | `arn:aws:secretsmanager:...` |
| `DB_NAME` | Database name | `postgres` |
| `ADMIN_ATHLETE_IDS` | Comma-separated admin athlete IDs | `3519964,12345,67890` |

**Critical**: `ADMIN_ATHLETE_IDS` must be set or the endpoints will reject all requests.

### IAM Permissions for Lambda Functions

The admin Lambda functions need:

- `rds-data:ExecuteStatement` - To query the database
- `secretsmanager:GetSecretValue` - To access DB credentials

## API Gateway Setup

### Create Routes

Add these routes to your API Gateway:

1. **GET /admin/users**
   - Integration: Lambda proxy to `admin_list_users`
   - Authorization: None (handled by Lambda)
   - CORS: Enable with credentials

2. **GET /admin/users/{athlete_id}/activities**
   - Integration: Lambda proxy to `admin_user_activities`
   - Path parameter: `athlete_id`
   - Authorization: None (handled by Lambda)
   - CORS: Enable with credentials

### Example AWS CLI Commands

```bash
# Get your API ID
API_ID="your-api-gateway-id"

# Create /admin/users route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /admin/users" \
  --target "integrations/your-integration-id"

# Create /admin/users/{athlete_id}/activities route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /admin/users/{athlete_id}/activities" \
  --target "integrations/your-integration-id"
```

## Testing

### Test Admin Access

1. Get an admin athlete_id from your `ADMIN_ATHLETE_IDS` list
2. Login to the app with that Strava account
3. Navigate to the Admin page (should appear in navigation)
4. Verify you can see the users list
5. Click on a user to see their activities

### Test Non-Admin Access

1. Login with a non-admin account
2. Admin link should NOT appear in navigation
3. Try accessing `/admin` directly - should see "Access denied" message
4. Test API directly - should get 403 response:

```bash
curl -X GET https://api.rabbitmiles.com/admin/users \
  -H "Cookie: rm_session=your-session-cookie" \
  -v
# Should return 403 Forbidden
```

## Troubleshooting

### Lambda Function Not Found

**Error**: `Could not find Lambda function with name: rabbitmiles-admin-list-users`

**Solution**: 
- Check the GitHub secret value matches your actual Lambda function name
- Verify the Lambda function exists in AWS

### Access Denied (403)

**Error**: User gets 403 when accessing admin endpoints

**Solution**:
- Verify `ADMIN_ATHLETE_IDS` environment variable is set on the Lambda
- Check that the user's athlete_id is in the allowlist
- Check CloudWatch logs for audit entries

### No Admin Link in Navigation

**Solution**:
- Check that `/me` endpoint returns `is_admin: true`
- Verify `ADMIN_ATHLETE_IDS` is set on the `me` Lambda
- Clear browser cache and reload

## Security Notes

1. **Never commit** the `ADMIN_ATHLETE_IDS` values to the repository
2. Keep the admin athlete_id list minimal - only trusted administrators
3. Review CloudWatch logs regularly for admin action audit entries
4. Admin endpoints include `Cache-Control: no-store` headers
5. Access/refresh tokens are never exposed in admin API responses

## Monitoring

### CloudWatch Logs

Admin actions are logged with this format:

```json
{
  "timestamp": "2026-02-06 14:20:00 UTC",
  "admin_athlete_id": 3519964,
  "endpoint": "/admin/users",
  "action": "list_users",
  "details": {}
}
```

Search CloudWatch logs for `AUDIT -` to find all admin actions.

### Metrics to Monitor

1. Admin endpoint invocation count
2. Failed authorization attempts (403s)
3. Error rates on admin endpoints
4. Response times for user/activity queries

## Additional Resources

- [Admin Feature Documentation](README.md#admin-features)
- [Environment Variables Reference](ENV_VARS.md)
- [GitHub Actions Secrets Guide](GITHUB_ACTIONS_SECRETS.md)
- [Lambda Deployment Guide](LAMBDA_DEPLOYMENT.md)
