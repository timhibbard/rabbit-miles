# Lambda Auto-Deployment Setup

This guide explains how to set up automatic deployment of AWS Lambda functions using GitHub Actions.

## Overview

The repository includes a GitHub Actions workflow that automatically deploys all four Lambda functions whenever changes are pushed to the `backend/` directory on the `main` branch. The workflow uses the official AWS Lambda Deploy Action.

## Lambda Functions

The following Lambda functions will be auto-deployed:

1. **auth_start** - Initiates Strava OAuth flow
2. **auth_callback** - Handles OAuth callback from Strava
3. **auth_disconnect** - Disconnects Strava integration
4. **me** - Returns authenticated user information

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
        "arn:aws:lambda:*:*:function:rabbitmiles-me"
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
- **Jobs:** One job per Lambda function (runs in parallel)
- **Runtime:** Python 3.12
- **Handler:** `lambda_function.handler`
- **Packaging:** AWS Lambda Deploy Action automatically packages each function directory

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

- [AWS Lambda Deploy Action Documentation](https://github.com/marketplace/actions/aws-lambda-deploy)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
