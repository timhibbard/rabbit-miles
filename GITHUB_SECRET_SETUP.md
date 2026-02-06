# New GitHub Secret Required

## LAMBDA_BACKFILL_ATHLETE_COUNT

This GitHub secret needs to be added to the repository for the deployment workflow to work with the new `backfill_athlete_count` Lambda function.

### Steps to Add the Secret:

1. Go to the repository Settings
2. Navigate to Secrets and variables > Actions
3. Click "New repository secret"
4. Add the following secret:

**Name:** `LAMBDA_BACKFILL_ATHLETE_COUNT`
**Value:** The actual AWS Lambda function name (e.g., `backfill-athlete-count` or `rabbit-miles-backfill-athlete-count`)

### Lambda Function Details:

- **Directory:** `backend/backfill_athlete_count/`
- **Handler:** `lambda_function.handler`
- **Purpose:** Backfills `athlete_count` field for existing activities by fetching data from Strava API
- **Runtime:** Python (same as other Lambda functions)
- **Required Environment Variables:** Same as other backend Lambdas (DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME)

### Deployment:

Once the secret is added, the Lambda will be automatically deployed when changes are pushed to the `main` branch that affect files in `backend/**`.

You can also manually trigger deployment using the GitHub Actions "Deploy Lambda Functions" workflow.
