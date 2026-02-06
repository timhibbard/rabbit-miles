# Lambda Auto-Deployment Setup

This guide explains how to set up automatic deployment of AWS Lambda functions using GitHub Actions.

## Overview

The repository includes a GitHub Actions workflow that automatically deploys all four Lambda functions whenever changes are pushed to the `backend/` directory on the `main` branch. The workflow uses the AWS CLI to package and deploy Lambda functions.

## Lambda Functions

The following Lambda functions will be auto-deployed:

### Authentication & User Management
1. **auth_start** - Initiates Strava OAuth flow
2. **auth_callback** - Handles OAuth callback from Strava
3. **auth_disconnect** - Disconnects Strava integration
4. **me** - Returns authenticated user information

### Activities & Data
5. **get_activities** - Retrieves user's activities
6. **get_activity_detail** - Gets detailed activity information
7. **fetch_activities** - Fetches activities from Strava API
8. **update_activities** - Updates activity data

### Trail Matching
9. **match_activity_trail** - Matches activities to trails
10. **match_unmatched_activities** - Processes unmatched activities
11. **reset_last_matched** - Resets trail matching state
12. **update_trail_data** - Updates trail information

### Webhooks
13. **webhook** - Handles Strava webhook events
14. **webhook_processor** - Processes webhook events from queue

### Admin (NEW)
15. **admin_list_users** - Lists all users (admin only)
16. **admin_user_activities** - Views user activities (admin only)

**Note**: Admin Lambdas require the `admin_utils.py` dependency, which is automatically included during deployment.

## Prerequisites

Before setting up auto-deployment, ensure you have:

1. AWS Lambda functions already created in your AWS account
2. An IAM user with appropriate permissions for Lambda deployment
3. Access to your GitHub repository settings

## Step 1: Create IAM User for Deployment

Create an IAM user in AWS with the following permissions:

### Required IAM Policy

Create a policy with these permissions:

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
        "arn:aws:lambda:*:*:function:rabbitmiles-auth-start",
        "arn:aws:lambda:*:*:function:rabbitmiles-auth-callback",
        "arn:aws:lambda:*:*:function:rabbitmiles-auth-disconnect",
        "arn:aws:lambda:*:*:function:rabbitmiles-me",
        "arn:aws:lambda:*:*:function:rabbitmiles-get-activities",
        "arn:aws:lambda:*:*:function:rabbitmiles-get-activity-detail",
        "arn:aws:lambda:*:*:function:rabbitmiles-fetch-activities",
        "arn:aws:lambda:*:*:function:rabbitmiles-update-activities",
        "arn:aws:lambda:*:*:function:rabbitmiles-match-activity-trail",
        "arn:aws:lambda:*:*:function:rabbitmiles-match-unmatched-activities",
        "arn:aws:lambda:*:*:function:rabbitmiles-reset-last-matched",
        "arn:aws:lambda:*:*:function:rabbitmiles-update-trail-data",
        "arn:aws:lambda:*:*:function:rabbitmiles-webhook",
        "arn:aws:lambda:*:*:function:rabbitmiles-webhook-processor",
        "arn:aws:lambda:*:*:function:rabbitmiles-admin-list-users",
        "arn:aws:lambda:*:*:function:rabbitmiles-admin-user-activities"
      ]
    }
  ]
}
```

**Note:** Replace the function names in the Resource ARNs with your actual Lambda function names if they differ.

### Create the IAM User

1. Go to AWS IAM Console → Users → Create User
2. Name: `github-lambda-deployer` (or your preferred name)
3. Attach the policy you created above
4. Create access keys:
   - Go to Security Credentials tab
   - Click "Create access key"
   - Select "Application running outside AWS"
   - Save the Access Key ID and Secret Access Key securely

## Step 2: Configure GitHub Secrets

Add the following secrets to your GitHub repository:

### Navigate to Repository Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each of the following:

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | Access key ID from IAM user | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Secret access key from IAM user | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS region where Lambda functions are deployed | `us-east-1` |
| `LAMBDA_AUTH_START_NAME` | Name of auth_start Lambda function | `rabbitmiles-auth-start` |
| `LAMBDA_AUTH_CALLBACK_NAME` | Name of auth_callback Lambda function | `rabbitmiles-auth-callback` |
| `LAMBDA_AUTH_DISCONNECT_NAME` | Name of auth_disconnect Lambda function | `rabbitmiles-auth-disconnect` |
| `LAMBDA_ME_NAME` | Name of me Lambda function | `rabbitmiles-me` |
| `LAMBDA_GET_ACTIVITIES` | Name of get_activities Lambda function | `rabbitmiles-get-activities` |
| `LAMBDA_GET_ACTIVITY_DETAIL` | Name of get_activity_detail Lambda function | `rabbitmiles-get-activity-detail` |
| `LAMBDA_FETCH_ACTIVITIES` | Name of fetch_activities Lambda function | `rabbitmiles-fetch-activities` |
| `LAMBDA_UPDATE_ACTIVITIES` | Name of update_activities Lambda function | `rabbitmiles-update-activities` |
| `LAMBDA_MATCH_ACTIVITY_TRAIL` | Name of match_activity_trail Lambda function | `rabbitmiles-match-activity-trail` |
| `LAMBDA_MATCH_UNMATCHED_ACTIVITIES` | Name of match_unmatched_activities Lambda function | `rabbitmiles-match-unmatched-activities` |
| `LAMBDA_RESET_LAST_MATCHED` | Name of reset_last_matched Lambda function | `rabbitmiles-reset-last-matched` |
| `LAMBDA_UPDATE_TRAIL_DATA` | Name of update_trail_data Lambda function | `rabbitmiles-update-trail-data` |
| `LAMBDA_WEBHOOK` | Name of webhook Lambda function | `rabbitmiles-webhook` |
| `LAMBDA_WEBHOOK_PROCESSOR` | Name of webhook_processor Lambda function | `rabbitmiles-webhook-processor` |
| `LAMBDA_ADMIN_LIST_USERS` | Name of admin_list_users Lambda function | `rabbitmiles-admin-list-users` |
| `LAMBDA_ADMIN_USER_ACTIVITIES` | Name of admin_user_activities Lambda function | `rabbitmiles-admin-user-activities` |

### Adding Secrets

For each secret:
1. Click **New repository secret**
2. Enter the **Name** from the table above
3. Enter the **Value** (your actual value)
4. Click **Add secret**

## Step 3: Lambda Function Configuration

Ensure your Lambda functions are configured with the correct handler:

- **Handler:** `lambda_function.handler`
- **Runtime:** Python 3.12 (or compatible version)

Each Lambda function should have the following environment variables configured (this is separate from GitHub secrets):

### auth_start Lambda
- `DB_CLUSTER_ARN` - RDS cluster ARN
- `DB_SECRET_ARN` - Database credentials secret ARN
- `DB_NAME` - Database name (default: "postgres")
- `API_BASE_URL` - API Gateway base URL
- `STRAVA_CLIENT_ID` - Strava OAuth client ID

### auth_callback Lambda
- `DB_CLUSTER_ARN` - RDS cluster ARN
- `DB_SECRET_ARN` - Database credentials secret ARN
- `DB_NAME` - Database name (default: "postgres")
- `API_BASE_URL` - API Gateway base URL
- `FRONTEND_URL` - Frontend URL
- `APP_SECRET` - Application secret for signing cookies
- `STRAVA_CLIENT_ID` - Strava OAuth client ID
- `STRAVA_CLIENT_SECRET` - Strava OAuth client secret

### auth_disconnect Lambda
- `DB_CLUSTER_ARN` - RDS cluster ARN
- `DB_SECRET_ARN` - Database credentials secret ARN
- `DB_NAME` - Database name (default: "postgres")
- `API_BASE_URL` - API Gateway base URL
- `FRONTEND_URL` - Frontend URL
- `APP_SECRET` - Application secret for signing cookies

### me Lambda
- `DB_CLUSTER_ARN` - RDS cluster ARN
- `DB_SECRET_ARN` - Database credentials secret ARN
- `DB_NAME` - Database name (default: "postgres")
- `APP_SECRET` - Application secret for signing cookies
- `FRONTEND_URL` - Frontend URL

## Step 4: Verify Setup

### Test Manual Deployment

1. Go to **Actions** tab in your GitHub repository
2. Select **Deploy Lambda Functions** workflow
3. Click **Run workflow** → **Run workflow**
4. Monitor the workflow execution

### Automatic Deployment

After setup, the workflow will automatically run when:
- Changes are pushed to the `main` branch
- Files in the `backend/` directory are modified

## Troubleshooting

### Permission Denied Errors

If you see "User is not authorized to perform: lambda:UpdateFunctionCode":
- Verify the IAM policy includes the correct permissions
- Check that the function ARNs in the policy match your actual function names
- Ensure the IAM user has the policy attached

### Function Not Found

If you see "ResourceNotFoundException":
- Verify the Lambda function names in GitHub secrets match the actual function names in AWS
- Ensure the AWS region secret matches where your Lambda functions are deployed

### Invalid Handler

If deployments succeed but functions don't work:
- Verify the handler is set to `lambda_function.handler`
- Check CloudWatch Logs for the Lambda function to see detailed error messages

## Security Best Practices

1. **Never commit AWS credentials** to the repository
2. **Use IAM roles with minimal permissions** - only grant what's needed for deployment
3. **Rotate access keys regularly** - update GitHub secrets when you rotate keys
4. **Monitor CloudTrail** - track who is deploying Lambda functions
5. **Enable MFA** on the IAM user if possible (for manual operations)

## Workflow Details

The deployment workflow (`.github/workflows/deploy-lambdas.yml`) includes:

- **Trigger:** Runs on push to `main` branch when `backend/**` files change, or manually via workflow_dispatch
- **Jobs:** Uses a matrix strategy to deploy all four Lambda functions in parallel
- **Packaging:** Each function directory is zipped using the `zip` command
- **Deployment:** Uses `aws lambda update-function-code` AWS CLI command to deploy
- **Authentication:** Uses AWS credentials configured via GitHub secrets
- **Permissions:** Sets minimal `contents: read` permission for GITHUB_TOKEN following security best practices

### Security Note on Matrix Strategy

The workflow uses a matrix strategy with dynamic secret references (`${{ secrets[matrix.lambda.secret] }}`). While CodeQL may flag this as "excessive-secrets-exposure", this is a false positive. The workflow only accesses the specific secrets defined in the matrix (LAMBDA_AUTH_START_NAME, LAMBDA_AUTH_CALLBACK_NAME, LAMBDA_AUTH_DISCONNECT_NAME, LAMBDA_ME_NAME) and does not expose all repository secrets. This is a standard and secure pattern for matrix-based deployments in GitHub Actions.

## Manual Deployment

If you need to deploy manually outside of GitHub Actions:

```bash
# Package and deploy a single function
cd backend/auth_start
zip -r function.zip lambda_function.py

aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://function.zip \
  --region us-east-1
```

## Rollback

If a deployment causes issues:

1. Go to AWS Lambda Console
2. Select the function
3. Go to **Versions** tab
4. Find the previous version
5. Update the alias to point to the previous version, or:

```bash
# Rollback using AWS CLI
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --s3-bucket your-deployment-bucket \
  --s3-key previous-version.zip \
  --region us-east-1
```

Alternatively, revert the commit in GitHub and push to trigger a new deployment with the old code.

## Next Steps

After setting up auto-deployment:

1. Test the deployment by making a small change to a Lambda function
2. Push to the `main` branch
3. Monitor the GitHub Actions workflow
4. Verify the function works correctly in production

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS CLI Lambda Commands](https://docs.aws.amazon.com/cli/latest/reference/lambda/)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [AWS Configure Credentials Action](https://github.com/aws-actions/configure-aws-credentials)
