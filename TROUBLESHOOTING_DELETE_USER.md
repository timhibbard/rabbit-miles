# Troubleshooting: Unable to Delete User (404 Error)

## Problem

When attempting to delete a user from the Admin page, the following error occurs:

```
XMLHttpRequest cannot load https://api.rabbitmiles.com/admin/users/204597277 due to access control checks.
DELETE /admin/users/204597277 endpoint error: "Network Error"
Preflight response is not successful. Status code: 404
```

CloudWatch also shows:
```
Log group '/aws/lambda/rabbitmiles-admin-delete-user' does not exist
```

## Root Cause

The API Gateway route `DELETE /admin/users/{athlete_id}` has not been configured, even though:
- ✅ The Lambda function `admin_delete_user` exists
- ✅ The Lambda is deployed via GitHub Actions
- ✅ The frontend code correctly calls `DELETE /admin/users/{athlete_id}`

**The Lambda function has never been invoked because it's not connected to API Gateway.**

## Solution

You need to create the API Gateway route and connect it to the Lambda function. There are two ways to do this:

### Option 1: Automated Setup (Recommended)

Use the provided setup script:

```bash
cd /path/to/rabbit-miles
./scripts/setup-admin-delete-user-route.sh
```

The script will:
1. Discover your API Gateway HTTP API
2. Find your Lambda function
3. Create or reuse a Lambda integration
4. Create the `DELETE /admin/users/{athlete_id}` route
5. Create the `OPTIONS /admin/users/{athlete_id}` route for CORS
6. Add Lambda invoke permissions

**Prerequisites:**
- AWS CLI installed and configured
- Appropriate IAM permissions to modify API Gateway and Lambda

### Option 2: Manual Setup via AWS Console

#### Step 1: Find Your API Gateway

1. Go to [API Gateway Console](https://console.aws.amazon.com/apigateway/)
2. Click on your RabbitMiles HTTP API (e.g., "rabbitmiles-api" or similar)
3. Note the API ID (shown in the details)

#### Step 2: Create Lambda Integration (if needed)

1. In your API, click **Integrations** in the left sidebar
2. Check if an integration for `rabbitmiles-admin-delete-user` exists
3. If not, create one:
   - Click **Create**
   - Integration type: **Lambda function**
   - Lambda function: Select `rabbitmiles-admin-delete-user`
   - Payload format version: **2.0**
   - Click **Create**
4. Note the Integration ID

#### Step 3: Create DELETE Route

1. Click **Routes** in the left sidebar
2. Click **Create**
3. Configure:
   - Method: **DELETE**
   - Resource path: `/admin/users/{athlete_id}`
   - Integration: Select the integration from Step 2
4. Click **Create**

#### Step 4: Create OPTIONS Route (for CORS)

1. Click **Create** again
2. Configure:
   - Method: **OPTIONS**
   - Resource path: `/admin/users/{athlete_id}`
   - Integration: Select the same integration
3. Click **Create**

#### Step 5: Add Lambda Permission

The Lambda function needs permission for API Gateway to invoke it. Run this AWS CLI command:

```bash
# Replace these values
API_GATEWAY_ID="your-api-gateway-id"
LAMBDA_FUNCTION_NAME="rabbitmiles-admin-delete-user"
AWS_REGION="us-east-1"
ACCOUNT_ID="your-account-id"

aws lambda add-permission \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --statement-id apigateway-delete-admin-user \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_GATEWAY_ID/*/*/admin/users/*"
```

Or add it via the Lambda console:
1. Go to [Lambda Console](https://console.aws.amazon.com/lambda/)
2. Click on `rabbitmiles-admin-delete-user`
3. Go to **Configuration** → **Permissions**
4. Scroll to **Resource-based policy statements**
5. Click **Add permissions**
6. Configure:
   - Service: **API Gateway**
   - Source ARN: `arn:aws:execute-api:REGION:ACCOUNT:API_ID/*/*/admin/users/*`

### Option 3: Manual Setup via AWS CLI

```bash
# Set your values
export API_GATEWAY_ID="your-api-gateway-id"
export LAMBDA_FUNCTION_NAME="rabbitmiles-admin-delete-user"
export AWS_REGION="us-east-1"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --query 'Configuration.FunctionArn' \
  --output text)

# Create or get integration
INTEGRATION_ID=$(aws apigatewayv2 get-integrations \
  --api-id "$API_GATEWAY_ID" \
  --query "Items[?IntegrationUri==\`$LAMBDA_ARN\`].IntegrationId" \
  --output text)

if [ -z "$INTEGRATION_ID" ]; then
  INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id "$API_GATEWAY_ID" \
    --integration-type AWS_PROXY \
    --integration-uri "$LAMBDA_ARN" \
    --payload-format-version "2.0" \
    --query 'IntegrationId' \
    --output text)
  echo "Created integration: $INTEGRATION_ID"
fi

# Create DELETE route
aws apigatewayv2 create-route \
  --api-id "$API_GATEWAY_ID" \
  --route-key "DELETE /admin/users/{athlete_id}" \
  --target "integrations/$INTEGRATION_ID"

# Create OPTIONS route for CORS
aws apigatewayv2 create-route \
  --api-id "$API_GATEWAY_ID" \
  --route-key "OPTIONS /admin/users/{athlete_id}" \
  --target "integrations/$INTEGRATION_ID"

# Add Lambda permission
aws lambda add-permission \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --statement-id apigateway-delete-admin-user-$(date +%s) \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_GATEWAY_ID/*/*/admin/users/*"

echo "✅ Setup complete!"
```

## Verification

After setting up the route, verify it works:

### 1. Check Route Exists

```bash
aws apigatewayv2 get-routes \
  --api-id "$API_GATEWAY_ID" \
  --query 'Items[?starts_with(RouteKey, `DELETE /admin/users`) || starts_with(RouteKey, `OPTIONS /admin/users`)].[RouteKey,RouteId,Target]' \
  --output table
```

Expected output:
```
-----------------------------------------------------------
|                        GetRoutes                         |
+-----------------------------------------+----------------+
|  DELETE /admin/users/{athlete_id}      |  route-id      |
|  OPTIONS /admin/users/{athlete_id}     |  route-id      |
+-----------------------------------------+----------------+
```

### 2. Test with curl

```bash
# Test with your admin session cookie
curl -X DELETE https://api.rabbitmiles.com/admin/users/99999999 \
  -H "Cookie: rm_session=your-admin-session-cookie" \
  -v
```

Expected responses:
- **404** with `{"error": "user not found"}` if user doesn't exist (good - endpoint is working!)
- **401** with `{"error": "not authenticated"}` if session is invalid
- **403** with `{"error": "forbidden"}` if user is not an admin
- **200** with `{"success": true, "deleted": {...}}` if deletion succeeds

### 3. Test in Browser

1. Login with an admin account
2. Go to the Admin page
3. Click the delete button (trash icon) next to a test user
4. Confirm deletion
5. User should be removed from the list

### 4. Check CloudWatch Logs

After the first successful request, CloudWatch Logs should show:

```bash
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/rabbitmiles-admin-delete-user"
```

You should now see the log group exists.

## Common Issues

### Issue: "Route already exists"

**Symptom:** Script or CLI command fails saying route exists

**Solution:**
```bash
# List existing routes
aws apigatewayv2 get-routes --api-id "$API_GATEWAY_ID" \
  --query 'Items[?RouteKey==`DELETE /admin/users/{athlete_id}`]'

# Delete the existing route
aws apigatewayv2 delete-route \
  --api-id "$API_GATEWAY_ID" \
  --route-id "route-id-from-above"

# Then create it again
```

### Issue: "Lambda permission already exists"

**Symptom:** Permission add fails with "ResourceConflictException"

**Solution:** This is safe to ignore. The permission already exists.

### Issue: Still getting 404 after setup

**Possible causes:**

1. **Wrong API Gateway:** Verify you're using the correct API ID
   ```bash
   aws apigatewayv2 get-apis --query 'Items[?ProtocolType==`HTTP`].[ApiId,Name,ApiEndpoint]'
   ```

2. **Wrong Lambda function name:** Verify the function exists
   ```bash
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `admin-delete-user`)].FunctionName'
   ```

3. **Cache:** Clear browser cache and try again

4. **Custom domain:** If using a custom domain, ensure it's properly mapped to the API Gateway stage

### Issue: CORS error

**Symptom:** "Preflight response is not successful"

**Solution:** Ensure the OPTIONS route exists and the Lambda handles OPTIONS requests:

```bash
# Verify OPTIONS route exists
aws apigatewayv2 get-routes --api-id "$API_GATEWAY_ID" \
  --query 'Items[?RouteKey==`OPTIONS /admin/users/{athlete_id}`]'
```

The Lambda function already handles OPTIONS requests (returns proper CORS headers), so just ensure the route exists.

## Prevention

To prevent this issue in the future:

1. **Document all API Gateway routes** in a central location
2. **Create infrastructure-as-code** (e.g., Terraform, CloudFormation) instead of manual setup
3. **Add route verification** to deployment scripts or CI/CD
4. **Create a checklist** for new Lambda functions that require API Gateway routes

## Related Documentation

- [DEPLOYMENT_DELETE_USER.md](DEPLOYMENT_DELETE_USER.md) - Original deployment guide
- [ADMIN_LAMBDA_DEPLOYMENT.md](ADMIN_LAMBDA_DEPLOYMENT.md) - Admin Lambda setup guide
- Backend Lambda: [backend/admin_delete_user/lambda_function.py](backend/admin_delete_user/lambda_function.py)
- Frontend API: [src/utils/api.js](src/utils/api.js) - `deleteUser()` function

## Timeline

- Lambda function created: Sometime during initial admin feature development
- Added to GitHub Actions: ✅ Present in `.github/workflows/deploy-lambdas.yml`
- API Gateway route: ❌ **Never created** (root cause of this issue)
- Fixed: When you run this guide!
