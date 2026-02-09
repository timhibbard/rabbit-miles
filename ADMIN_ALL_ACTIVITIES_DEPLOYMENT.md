# Admin All Activities Lambda - Deployment Guide

## Overview
This Lambda function provides an endpoint for admin users to fetch activities from all athletes (not just a specific user). The endpoint returns the last 50 activities sorted by most recent, with support for pagination.

## Prerequisites
- AWS CLI configured with appropriate credentials
- Access to AWS Lambda console or CLI
- Access to API Gateway console or CLI
- Existing admin infrastructure (admin_utils.py, database tables)
- **GitHub Actions Secret**: After deploying the Lambda, add the secret `LAMBDA_ADMIN_ALL_ACTIVITIES` to GitHub repository settings (see step 6 below)

## Lambda Function Details
- **Name**: `rabbitmiles-admin-all-activities`
- **Runtime**: Python 3.x (match other Lambda functions in the project)
- **Handler**: `lambda_function.handler`
- **Timeout**: 30 seconds (recommended)
- **Memory**: 256 MB (recommended)

## Environment Variables Required
The following environment variables must be set on the Lambda function:

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_CLUSTER_ARN` | ARN of your RDS Aurora cluster | `arn:aws:rds:us-east-1:ACCOUNT:cluster:rabbitmiles` |
| `DB_SECRET_ARN` | ARN of the database credentials secret | `arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:rabbitmiles-db` |
| `DB_NAME` | Database name | `postgres` |
| `APP_SECRET` | Secret used for session cookie validation | (stored in Secrets Manager) |
| `FRONTEND_URL` | Frontend application URL | `https://rabbitmiles.com` |
| `ADMIN_ATHLETE_IDS` | Comma-separated list of admin athlete IDs | `12345,67890` |

## Deployment Steps

### 1. Create the Lambda Function

#### Option A: Using AWS Console
1. Navigate to AWS Lambda console
2. Click "Create function"
3. Choose "Author from scratch"
4. Set function name: `rabbitmiles-admin-all-activities`
5. Select runtime: Python 3.x (match other functions)
6. Create function

#### Option B: Using AWS CLI
```bash
# Create a deployment package
cd backend/admin_all_activities
zip -r ../admin_all_activities.zip lambda_function.py

# Navigate to backend directory to include admin_utils.py
cd ..
zip -r admin_all_activities.zip admin_utils.py

# Create the Lambda function
aws lambda create-function \
  --function-name rabbitmiles-admin-all-activities \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/YOUR_LAMBDA_ROLE \
  --handler lambda_function.handler \
  --zip-file fileb://admin_all_activities.zip \
  --timeout 30 \
  --memory-size 256
```

### 2. Set Environment Variables

Using AWS Console:
1. Go to Configuration > Environment variables
2. Add each variable listed above

Using AWS CLI:
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-admin-all-activities \
  --environment Variables="{
    DB_CLUSTER_ARN=arn:aws:rds:us-east-1:ACCOUNT:cluster:rabbitmiles,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:rabbitmiles-db,
    DB_NAME=postgres,
    APP_SECRET=YOUR_SECRET,
    FRONTEND_URL=https://rabbitmiles.com,
    ADMIN_ATHLETE_IDS=12345,67890
  }"
```

### 3. Grant IAM Permissions

The Lambda execution role needs the following permissions:
- `rds-data:ExecuteStatement` - To query the database
- `secretsmanager:GetSecretValue` - To access database credentials
- Basic Lambda execution permissions (CloudWatch Logs)

Example IAM policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:us-east-1:ACCOUNT:cluster:rabbitmiles"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:rabbitmiles-db*"
    }
  ]
}
```

### 4. Configure API Gateway

Add a new route to your API Gateway:

**Route**: `GET /admin/activities`

**Integration**: Lambda proxy integration with `rabbitmiles-admin-all-activities`

**CORS Configuration**:
- Allow origin: Your frontend URL
- Allow methods: GET, OPTIONS
- Allow headers: Content-Type, Cookie
- Allow credentials: true

#### Using AWS Console:
1. Navigate to API Gateway
2. Select your HTTP API
3. Go to "Routes"
4. Click "Create"
5. Method: GET
6. Path: `/admin/activities`
7. Create and attach integration to the Lambda function

#### Using AWS CLI:
```bash
# Create the integration
aws apigatewayv2 create-integration \
  --api-id YOUR_API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:us-east-1:ACCOUNT:function:rabbitmiles-admin-all-activities \
  --payload-format-version 2.0

# Create the route
aws apigatewayv2 create-route \
  --api-id YOUR_API_ID \
  --route-key "GET /admin/activities" \
  --target integrations/INTEGRATION_ID
```

### 5. Grant API Gateway Permission to Invoke Lambda

```bash
aws lambda add-permission \
  --function-name rabbitmiles-admin-all-activities \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:ACCOUNT:YOUR_API_ID/*/*/admin/activities"
```

### 6. Configure GitHub Actions Secret

To enable automatic deployments via GitHub Actions:

1. Navigate to your GitHub repository: `https://github.com/timhibbard/rabbit-miles`
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the secret:
   - **Name**: `LAMBDA_ADMIN_ALL_ACTIVITIES`
   - **Value**: The exact Lambda function name (e.g., `rabbitmiles-admin-all-activities`)

This allows the GitHub Actions workflow to automatically deploy code updates when changes are pushed to the `main` branch.

**Note**: The workflow file (`.github/workflows/deploy-lambdas.yml`) has already been updated to include this Lambda in the deployment matrix.

### 7. Deploy API Gateway Changes

If using stages:
```bash
aws apigatewayv2 create-deployment \
  --api-id YOUR_API_ID \
  --stage-name prod
```

## Testing

### Test the Lambda Directly
Use the test event in `backend/admin_all_activities/test_lambda.py` as a reference.

### Test via API
```bash
# Using curl (requires valid session cookie)
curl -X GET "https://api.rabbitmiles.com/admin/activities?limit=50&offset=0" \
  --cookie "rm_session=YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json"
```

Expected response:
```json
{
  "activities": [
    {
      "id": 123,
      "athlete_id": 12345,
      "athlete_name": "John Doe",
      "strava_activity_id": 98765,
      "name": "Morning Run",
      "distance": 5000.0,
      "moving_time": 1800,
      "type": "Run",
      "start_date_local": "2026-02-01T08:00:00Z",
      ...
    }
  ],
  "count": 50,
  "total_count": 150,
  "limit": 50,
  "offset": 0
}
```

## Verification

1. Log into the admin panel at `https://rabbitmiles.com/admin`
2. Upon page load, you should see the last 50 activities from all athletes
3. Verify activities are sorted by most recent first
4. Verify the athlete name is displayed for each activity
5. Test pagination by scrolling to the bottom of the activities list

## Rollback

If issues occur:

1. **Remove the API Gateway route**:
   ```bash
   aws apigatewayv2 delete-route \
     --api-id YOUR_API_ID \
     --route-id ROUTE_ID
   ```

2. **Delete the Lambda function**:
   ```bash
   aws lambda delete-function \
     --function-name rabbitmiles-admin-all-activities
   ```

3. The frontend will gracefully fall back to showing "No activities found" when the endpoint is unavailable

## Notes

- No database migrations are required for this feature
- The Lambda uses the existing `activities` and `users` tables
- The function follows the same authentication pattern as other admin endpoints
- Performance: The query uses an index on `start_date_local` for efficient sorting
