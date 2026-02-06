# Delete User Lambda Deployment Guide

This guide covers the deployment of the `admin_delete_user` Lambda function that enables admins to delete users and all their associated data.

## ⚠️ Important: API Gateway Route Required

**If you're experiencing 404 errors when trying to delete users**, the API Gateway route is likely missing. See:
- **[TROUBLESHOOTING_DELETE_USER.md](TROUBLESHOOTING_DELETE_USER.md)** - Complete troubleshooting guide with automated setup script
- Quick fix: Run `./scripts/setup-admin-delete-user-route.sh` to automatically configure the route

## New Lambda Function

**admin_delete_user** - Deletes a user and all their activities (admin only)

## Prerequisites

Before deploying, ensure you have:

1. Created the Lambda function in AWS
2. Configured the `ADMIN_ATHLETE_IDS` environment variable on the Lambda
3. Set up the API Gateway route for the delete endpoint
4. Configured IAM permissions for RDS Data API access

## GitHub Actions Setup

### Step 1: Add GitHub Secret

Add this secret to your GitHub repository:

1. Go to: https://github.com/timhibbard/rabbit-miles/settings/secrets/actions
2. Click **New repository secret**
3. Add:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `LAMBDA_ADMIN_DELETE_USER` | Your admin_delete_user Lambda function name | `rabbitmiles-admin-delete-user` or `prod-admin-delete-user` |

### Step 2: Update IAM Policy

Update your GitHub deployment IAM user's policy to include the new Lambda function:

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
        "arn:aws:lambda:*:*:function:rabbitmiles-admin-delete-user"
      ]
    }
  ]
}
```

Or add this ARN to your existing deployment policy.

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

The admin_delete_user Lambda function requires these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_SECRET` | Session token verification secret | `<long-random-string>` |
| `FRONTEND_URL` | Frontend URL for CORS | `https://rabbitmiles.com` |
| `DB_CLUSTER_ARN` | Aurora Serverless cluster ARN | `arn:aws:rds:us-east-1:...` |
| `DB_SECRET_ARN` | Database credentials secret ARN | `arn:aws:secretsmanager:...` |
| `DB_NAME` | Database name | `postgres` |
| `ADMIN_ATHLETE_IDS` | Comma-separated admin athlete IDs | `3519964,12345,67890` |

**Critical**: `ADMIN_ATHLETE_IDS` must be set or the endpoint will reject all requests.

### IAM Permissions for Lambda Function

The admin_delete_user Lambda function needs:

- `rds-data:ExecuteStatement` - To query and delete from the database
- `secretsmanager:GetSecretValue` - To access DB credentials

## API Gateway Setup

⚠️ **This is a critical step!** Without the API Gateway route, you'll get 404 errors.

### Quick Setup (Recommended)

Use the automated setup script:

```bash
cd /path/to/rabbit-miles
./scripts/setup-admin-delete-user-route.sh
```

The script will automatically:
- Find your API Gateway and Lambda function
- Create the DELETE and OPTIONS routes
- Add necessary permissions
- Verify the setup

### Manual Setup

If you prefer manual setup, see [TROUBLESHOOTING_DELETE_USER.md](TROUBLESHOOTING_DELETE_USER.md) for detailed instructions.

### Create Route

Add this route to your API Gateway:

**DELETE /admin/users/{athlete_id}**
- Integration: Lambda proxy to `admin_delete_user`
- Path parameter: `athlete_id`
- Authorization: None (handled by Lambda)
- CORS: Enable with credentials

### Example AWS CLI Command

```bash
# Get your API ID
API_ID="your-api-gateway-id"

# Create DELETE /admin/users/{athlete_id} route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "DELETE /admin/users/{athlete_id}" \
  --target "integrations/your-integration-id"
```

### Verify Setup

After creating the route, verify it exists:

```bash
aws apigatewayv2 get-routes --api-id $API_ID \
  --query 'Items[?contains(RouteKey, `admin/users`)].[RouteKey,RouteId]' \
  --output table
```

You should see:
- `DELETE /admin/users/{athlete_id}`
- `OPTIONS /admin/users/{athlete_id}` (for CORS)
- `GET /admin/users` (from admin_list_users)
- `GET /admin/users/{athlete_id}/activities` (from admin_user_activities)

## Testing

### Test Delete User (Admin)

1. Login with an admin account
2. Navigate to the Admin page
3. Click the delete button (trash icon) next to a test user
4. Confirm the deletion in the dialog
5. Verify:
   - User is removed from the list
   - Success message is displayed
   - Activities are removed from database

### Test API Directly

```bash
# Test with admin session cookie
curl -X DELETE https://api.rabbitmiles.com/admin/users/12345 \
  -H "Cookie: rm_session=your-admin-session-cookie" \
  -v

# Expected response (200):
{
  "success": true,
  "deleted": {
    "athlete_id": 12345,
    "display_name": "Test User",
    "activities_count": 42
  }
}
```

### Test Non-Admin Access

```bash
# Test with non-admin session cookie
curl -X DELETE https://api.rabbitmiles.com/admin/users/12345 \
  -H "Cookie: rm_session=your-non-admin-session-cookie" \
  -v

# Expected response (403):
{
  "error": "forbidden"
}
```

### Test Unauthenticated Access

```bash
# Test without session cookie
curl -X DELETE https://api.rabbitmiles.com/admin/users/12345 \
  -v

# Expected response (401):
{
  "error": "not authenticated"
}
```

## Database Behavior

The delete operation performs these steps in order:

1. **Verify user exists** - Returns 404 if user not found
2. **Delete activities** - Removes all activities for the user from `activities` table
3. **Delete user** - Removes the user record from `users` table

**Note**: The database schema has `ON DELETE CASCADE` on the foreign key from `activities.athlete_id` to `users.athlete_id`, but we explicitly delete activities first for logging and audit purposes.

## Security Features

1. **Admin-only access** - Only users in `ADMIN_ATHLETE_IDS` can delete users
2. **Audit logging** - All delete attempts are logged with `AUDIT` prefix
3. **Confirmation dialog** - Frontend requires confirmation before deletion
4. **No cascade to self** - Admins can delete other users (implementation prevents self-deletion if needed)
5. **Session verification** - Uses signed, time-limited session tokens

## Audit Logging

All delete operations are logged to CloudWatch with this format:

```json
{
  "timestamp": "2026-02-06 17:00:00 UTC",
  "admin_athlete_id": 3519964,
  "endpoint": "/admin/users/12345",
  "action": "delete_success",
  "details": {
    "target_athlete_id": 12345,
    "display_name": "Test User",
    "activities_deleted": 42,
    "users_deleted": 1
  }
}
```

Search CloudWatch logs for `AUDIT -` to find all admin actions including deletions.

## Troubleshooting

### 404 Error When Deleting Users

**Error**: `Preflight response is not successful. Status code: 404`

**Solution**: The API Gateway route is missing. See **[TROUBLESHOOTING_DELETE_USER.md](TROUBLESHOOTING_DELETE_USER.md)** for:
- Automated setup script
- Step-by-step manual instructions
- Verification commands
- Common issues and solutions

Quick fix:
```bash
./scripts/setup-admin-delete-user-route.sh
```

### Lambda Function Not Found

**Error**: `Could not find Lambda function with name: rabbitmiles-admin-delete-user`

**Solution**: 
- Check the GitHub secret value matches your actual Lambda function name
- Verify the Lambda function exists in AWS

### Access Denied (403)

**Error**: User gets 403 when calling delete endpoint

**Solution**:
- Verify `ADMIN_ATHLETE_IDS` environment variable is set on the Lambda
- Check that the user's athlete_id is in the allowlist
- Check CloudWatch logs for audit entries

### User Not Found (404)

**Error**: Delete returns 404

**Solution**:
- Verify the athlete_id exists in the database
- Check that the correct athlete_id is being sent in the path

### Internal Server Error (500)

**Solution**:
- Check CloudWatch logs for the Lambda function
- Verify all environment variables are set correctly
- Ensure RDS Data API permissions are configured

## Forward Compatibility

This implementation is designed to be forward compatible for user self-deletion:

1. **Parameterized athlete_id** - Can easily be adapted to use the session's athlete_id instead of path parameter
2. **Audit logging** - Already tracks who performed the deletion
3. **Confirmation required** - Frontend already has confirmation dialog
4. **Complete data removal** - Removes all user data as required by privacy regulations

To enable user self-deletion in the future:
1. Create a new endpoint like `DELETE /me` 
2. Use the session's athlete_id instead of path parameter
3. Add additional confirmation (e.g., password re-entry)
4. Keep the same deletion logic from this Lambda

## Monitoring

### CloudWatch Metrics to Monitor

1. Delete endpoint invocation count
2. Failed authorization attempts (403s)
3. Error rates on delete endpoint
4. Number of users/activities deleted per operation

### CloudWatch Alarms to Consider

1. Alert on high delete volume (potential abuse)
2. Alert on repeated 403s (unauthorized access attempts)
3. Alert on 500 errors (system issues)

## Additional Resources

- [Admin Feature Documentation](README.md#admin-features)
- [Admin Lambda Deployment Guide](ADMIN_LAMBDA_DEPLOYMENT.md)
- [Environment Variables Reference](ENV_VARS.md)
- [Database Schema](DATABASE_SCHEMA.md)
