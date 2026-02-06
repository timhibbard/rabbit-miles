# Quick Fix: Unable to Delete User (404 Error)

## Problem Summary

When clicking the delete button in the Admin panel, you get:
- 404 error
- "Preflight response is not successful"
- "Network Error"

## Root Cause

The API Gateway route `DELETE /admin/users/{athlete_id}` has not been configured. The Lambda function exists and is deployed, but it's not connected to your API Gateway.

## Solution (5 minutes)

### Option 1: Automated Setup (Recommended) ✨

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone https://github.com/timhibbard/rabbit-miles.git
   cd rabbit-miles
   ```

2. **Run the setup script**:
   ```bash
   ./scripts/setup-admin-delete-user-route.sh
   ```

3. **Follow the prompts**:
   - The script will find your API Gateway
   - It will discover your Lambda function
   - It will create the necessary routes
   - That's it! ✅

### Option 2: Manual Setup via AWS Console (10 minutes)

See [TROUBLESHOOTING_DELETE_USER.md](TROUBLESHOOTING_DELETE_USER.md) for detailed step-by-step instructions.

### Option 3: Quick AWS CLI Commands (2 minutes)

```bash
# Set these values
export API_GATEWAY_ID="your-api-id"     # Find in API Gateway console
export LAMBDA_NAME="rabbitmiles-admin-delete-user"
export AWS_REGION="us-east-1"

# Get setup
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
LAMBDA_ARN=$(aws lambda get-function --function-name "$LAMBDA_NAME" --query 'Configuration.FunctionArn' --output text)

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id "$API_GATEWAY_ID" \
  --integration-type AWS_PROXY \
  --integration-uri "$LAMBDA_ARN" \
  --payload-format-version "2.0" \
  --query 'IntegrationId' --output text)

# Create routes
aws apigatewayv2 create-route \
  --api-id "$API_GATEWAY_ID" \
  --route-key "DELETE /admin/users/{athlete_id}" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id "$API_GATEWAY_ID" \
  --route-key "OPTIONS /admin/users/{athlete_id}" \
  --target "integrations/$INTEGRATION_ID"

# Add permission
aws lambda add-permission \
  --function-name "$LAMBDA_NAME" \
  --statement-id apigateway-delete-admin-user \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_GATEWAY_ID/*/*/admin/users/*"

echo "✅ Done!"
```

## Verify It Works

1. **In your browser**:
   - Login as an admin
   - Go to the Admin page
   - Click the delete button (trash icon)
   - User should be deleted successfully! 🎉

2. **With curl**:
   ```bash
   curl -X DELETE https://api.rabbitmiles.com/admin/users/99999999 \
     -H "Cookie: rm_session=your-admin-cookie" \
     -v
   ```
   
   You should get a proper response (404 for non-existent user, not a CORS error)

## Optional: Verify All Routes

After fixing, you can verify all your API Gateway routes are correctly configured:

```bash
./scripts/verify-api-gateway-routes.sh
```

This will check all Lambda functions and ensure they have corresponding API Gateway routes.

## Need More Help?

- **Detailed troubleshooting**: [TROUBLESHOOTING_DELETE_USER.md](TROUBLESHOOTING_DELETE_USER.md)
- **Deployment guide**: [DEPLOYMENT_DELETE_USER.md](DEPLOYMENT_DELETE_USER.md)
- **Admin setup**: [ADMIN_LAMBDA_DEPLOYMENT.md](ADMIN_LAMBDA_DEPLOYMENT.md)

## Why Did This Happen?

The Lambda function was created and deployed, but the manual step of creating the API Gateway route was missed. This is a common issue when infrastructure is managed manually instead of using Infrastructure-as-Code (IaC).

## Prevention

To prevent this in the future:

1. **Run the verification script** after deploying new Lambda functions:
   ```bash
   ./scripts/verify-api-gateway-routes.sh
   ```

2. **Use the provided setup scripts** for new endpoints

3. **Consider Infrastructure-as-Code** (Terraform, CloudFormation) for your infrastructure in the future
