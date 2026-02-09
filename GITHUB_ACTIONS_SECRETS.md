# GitHub Actions Secrets for Trail Matching Lambdas

## New Secrets Required

After deploying the trail matching Lambda functions to AWS, you need to add the following secrets to your GitHub repository settings:

### How to Add Secrets

1. Go to your GitHub repository: https://github.com/timhibbard/rabbit-miles
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret below

### Required Secrets

#### LAMBDA_MATCH_ACTIVITY_TRAIL
- **Description**: The AWS Lambda function name for the match_activity_trail function
- **Example value**: `match_activity_trail` or `prod-match-activity-trail`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda

#### LAMBDA_MATCH_UNMATCHED_ACTIVITIES
- **Description**: The AWS Lambda function name for the match_unmatched_activities function
- **Example value**: `match_unmatched_activities` or `prod-match-unmatched-activities`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda

#### LAMBDA_ADMIN_LIST_USERS
- **Description**: The AWS Lambda function name for the admin_list_users function
- **Example value**: `admin_list_users` or `prod-admin-list-users`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda
- **Note**: This Lambda requires the admin_utils.py dependency (automatically included in deployment)

#### LAMBDA_ADMIN_USER_ACTIVITIES
- **Description**: The AWS Lambda function name for the admin_user_activities function
- **Example value**: `admin_user_activities` or `prod-admin-user-activities`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda
- **Note**: This Lambda requires the admin_utils.py dependency (automatically included in deployment)

#### LAMBDA_ADMIN_DELETE_USER
- **Description**: The AWS Lambda function name for the admin_delete_user function
- **Example value**: `admin_delete_user` or `prod-admin-delete-user`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda
- **Note**: This Lambda requires the admin_utils.py dependency (automatically included in deployment)

#### LAMBDA_ADMIN_BACKFILL_ACTIVITIES
- **Description**: The AWS Lambda function name for the admin_backfill_activities function
- **Example value**: `admin_backfill_activities` or `prod-admin-backfill-activities`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda
- **Note**: This Lambda requires the admin_utils.py dependency (automatically included in deployment)

#### LAMBDA_ADMIN_ALL_ACTIVITIES
- **Description**: The AWS Lambda function name for the admin_all_activities function
- **Example value**: `admin_all_activities` or `prod-admin-all-activities`
- **Used by**: GitHub Actions workflow to deploy code updates to this Lambda
- **Note**: This Lambda requires the admin_utils.py dependency (automatically included in deployment)

## Deployment Flow

Once these secrets are configured:

1. Push changes to the `main` branch that affect `backend/**` files
2. GitHub Actions will automatically:
   - Package each Lambda function (creates `function.zip`)
   - For admin Lambdas: Include `admin_utils.py` dependency in the package
   - Deploy to AWS using `aws lambda update-function-code`
   - Deploy runs in parallel for all Lambda functions

3. The workflow can also be triggered manually via the **Actions** tab → **Deploy Lambda Functions** → **Run workflow**

**Note for Admin Lambdas**: The `admin_list_users` and `admin_user_activities` Lambdas depend on the shared `admin_utils.py` module. The deployment workflow automatically includes this file in their deployment packages.

## Verifying Secrets

To verify the secrets are configured correctly:

1. Go to **Actions** tab in GitHub
2. Click on **Deploy Lambda Functions** workflow
3. Click **Run workflow** → **Run workflow**
4. If secrets are missing, the deployment will fail with an error like:
   ```
   Error: Could not find Lambda function with name: <empty>
   ```

## Full List of Lambda Secrets

For reference, here's the complete list of Lambda secrets used in the workflow:

- `LAMBDA_AUTH_START_NAME`
- `LAMBDA_AUTH_CALLBACK_NAME`
- `LAMBDA_AUTH_DISCONNECT_NAME`
- `LAMBDA_ME_NAME`
- `LAMBDA_GET_ACTIVITIES`
- `LAMBDA_GET_ACTIVITY_DETAIL`
- `LAMBDA_FETCH_ACTIVITIES`
- `LAMBDA_WEBHOOK`
- `LAMBDA_WEBHOOK_PROCESSOR`
- `LAMBDA_RESET_LAST_MATCHED`
- `LAMBDA_UPDATE_TRAIL_DATA`
- `LAMBDA_UPDATE_ACTIVITIES`
- `LAMBDA_MATCH_ACTIVITY_TRAIL`
- `LAMBDA_MATCH_UNMATCHED_ACTIVITIES`
- **`LAMBDA_ADMIN_LIST_USERS`** ← Admin endpoint
- **`LAMBDA_ADMIN_USER_ACTIVITIES`** ← Admin endpoint
- **`LAMBDA_ADMIN_DELETE_USER`** ← Admin endpoint
- **`LAMBDA_ADMIN_BACKFILL_ACTIVITIES`** ← Admin endpoint
- **`LAMBDA_ADMIN_ALL_ACTIVITIES`** ← NEW (Admin endpoint)
- `LAMBDA_BACKFILL_ATHLETE_COUNT`

## Additional AWS Secrets

The workflow also requires these AWS secrets (should already be configured):

- `AWS_ACCESS_KEY_ID` - AWS access key for deployment
- `AWS_SECRET_ACCESS_KEY` - AWS secret key for deployment
- `AWS_REGION` - AWS region (e.g., `us-east-1`)

## Troubleshooting

### Secret Not Found Error
If you see an error like:
```
Error: Secret LAMBDA_MATCH_ACTIVITY_TRAIL not found
```

Solution: Add the secret in GitHub repository settings as described above.

### Lambda Function Not Found Error
If you see:
```
Error: Could not find Lambda function with name: match_activity_trail
```

Solution: Either:
1. The Lambda function doesn't exist in AWS yet - deploy it first using the deployment guide
2. The secret value is incorrect - check the exact Lambda function name in AWS Console

### Permission Denied Error
If you see:
```
Error: User is not authorized to perform: lambda:UpdateFunctionCode
```

Solution: The AWS credentials need the `lambda:UpdateFunctionCode` permission for all Lambda functions.

## Next Steps

1. Deploy the Lambda functions to AWS (see `TRAIL_MATCHING_DEPLOYMENT.md`)
2. Add the two new secrets to GitHub repository settings
3. Push changes to `main` branch or manually trigger the workflow
4. Verify successful deployment in the Actions tab
