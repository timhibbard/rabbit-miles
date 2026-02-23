# EventBridge Schedule Automation Fix

## Problem

The `rabbitmiles-scheduled-activity-update` Lambda function was not running automatically on its configured EventBridge interval. The user had to manually trigger it each time.

**Root Cause:** The EventBridge schedule was not automated. It required manual setup via AWS Console or CLI, which meant:
- The schedule could be misconfigured
- The schedule might not be set up at all
- Changes to the schedule required manual updates

## Solution

Created automated deployment of the EventBridge schedule via GitHub Actions.

### What Was Added

**New Workflow: `.github/workflows/deploy-eventbridge-schedule.yml`**

This workflow automatically:
1. Creates/updates the EventBridge rule `scheduled-activity-update-every-12h`
2. Sets the schedule expression to `rate(12 hours)`
3. Configures the Lambda as the target
4. Grants EventBridge permission to invoke the Lambda
5. Verifies the configuration

**Workflow Triggers:**
- Push to `main` branch when `backend/scheduled_activity_update/**` files change
- Push to `main` branch when the workflow file itself changes
- Manual trigger via `workflow_dispatch`

### Updated Documentation

1. **`backend/scheduled_activity_update/README.md`**
   - Added section explaining automated deployment
   - Kept manual instructions as fallback/reference
   - Listed required GitHub Secrets

2. **`DEPLOYMENT_ACTIVITY_UPDATES.md`**
   - Updated Step 5 to reflect automated deployment
   - Improved troubleshooting section with verification commands
   - Added manual re-run instructions

## Usage

### Automatic Deployment

The EventBridge schedule is automatically deployed when you:
1. Push changes to `main` branch that affect `backend/scheduled_activity_update/`
2. Push changes to the workflow file itself

### Manual Trigger

If you need to manually deploy or update the schedule:

1. Go to GitHub → Actions
2. Select "Deploy EventBridge Schedule" workflow
3. Click "Run workflow"
4. Select branch (usually `main`)
5. Click "Run workflow" button

### Verify Deployment

After deployment, verify the schedule is working:

```bash
# Check if rule exists and is enabled
aws events describe-rule --name scheduled-activity-update-every-12h

# Verify Lambda is configured as target
aws events list-targets-by-rule --rule scheduled-activity-update-every-12h

# Check Lambda has EventBridge permission
aws lambda get-policy --function-name <your-lambda-name>
```

## Required GitHub Secrets

The workflow requires these secrets to be configured in GitHub:
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_REGION` - AWS region (e.g., us-east-1)
- `LAMBDA_SCHEDULED_ACTIVITY_UPDATE` - Lambda function name

## Expected Behavior

After this fix is deployed:

1. **First Time:** The workflow must be run at least once (either automatically via push to main, or manually triggered)
2. **Ongoing:** The Lambda will be invoked automatically every 12 hours
3. **Updates:** Any changes to the Lambda code or workflow will automatically update the schedule

## Monitoring

To verify the schedule is running:

1. **Check EventBridge Metrics** (CloudWatch):
   - Rule: `scheduled-activity-update-every-12h`
   - Metrics: Invocations, FailedInvocations

2. **Check Lambda Logs** (CloudWatch Logs):
   - Log group: `/aws/lambda/<your-lambda-name>`
   - Look for invocations every 12 hours

3. **Check Lambda Metrics** (CloudWatch):
   - Invocations: Should increase every 12 hours
   - Errors: Should be 0
   - Duration: Execution time

## Troubleshooting

### Schedule Not Running

1. Verify the workflow ran successfully:
   - Go to GitHub → Actions → "Deploy EventBridge Schedule"
   - Check latest run for errors

2. Manually trigger the workflow:
   - GitHub → Actions → "Deploy EventBridge Schedule"
   - Click "Run workflow"

3. Check EventBridge rule status:
   ```bash
   aws events describe-rule --name scheduled-activity-update-every-12h
   ```

4. Verify Lambda permissions:
   ```bash
   aws lambda get-policy --function-name <your-lambda-name>
   ```

### Workflow Fails

Common issues:
- **Invalid credentials:** Check AWS secrets are correct
- **Lambda not found:** Ensure `LAMBDA_SCHEDULED_ACTIVITY_UPDATE` secret is set correctly
- **Permission denied:** Ensure AWS credentials have permissions for EventBridge and Lambda

## Architecture

```
GitHub Actions Workflow
        ↓
    AWS EventBridge
        ↓ (every 12 hours)
    Lambda: scheduled_activity_update
        ↓
    RDS Data API (Aurora PostgreSQL)
        ↓
    Update activities from Strava
```

## Security Considerations

- EventBridge uses IAM permissions to invoke Lambda
- No secrets are exposed in the workflow
- Lambda permissions are scoped to specific EventBridge rule ARN
- Workflow only has read permissions on repository contents

## Future Improvements

Potential enhancements:
- Add CloudFormation/Terraform for complete IaC
- Add monitoring alerts for failed invocations
- Make schedule interval configurable via environment variable
- Add integration tests for EventBridge trigger
