# Troubleshooting: Admin Activities Showing Only Your Activities

## Problem

On the Admin page, "All Athletes' Activities (50)" is showing only your activities instead of activities from all users.

![image](https://github.com/user-attachments/assets/36fd6e5a-0268-4148-8889-8bc2961a39d8)

## Quick Diagnosis

**🔍 Key symptom**: If you DON'T see "Athlete: [name]" displayed on each activity (like in the screenshot above), the API Gateway integration is pointing to the wrong Lambda function.

**✅ Route exists (confirmed)**: The route `GET /admin/activities` exists in API Gateway  
**❌ Wrong integration**: The route is calling `get_activities` instead of `admin_all_activities`

### Why This Happens

There are two Lambda functions with similar purposes:
- **`get_activities`**: Returns activities for the logged-in user only (no athlete_name field)
- **`admin_all_activities`**: Returns activities from ALL users (with athlete_name field)

The API Gateway route exists, but it's integrated with the wrong function.

## Root Cause

The `/admin/activities` API Gateway route is pointing to the wrong Lambda function. When the frontend calls `/admin/activities`, the integration calls:

- ❌ `rabbitmiles-get-activities` (filters to your activities only)
instead of:
- ✅ `rabbitmiles-admin-all-activities` (shows all users' activities)

## Quick Fix

### Step 1: Verify the Current Integration

```bash
# Get your API ID from the screenshot or run:
aws apigatewayv2 get-apis --query 'Items[?Name==`rabbitmiles`].ApiId' --output text

# Check which Lambda is being called
# NOTE: Use YOUR actual API ID and integration ID from your AWS console
# The values below (9zke9jame0, vgjpa5n) are from the screenshot - replace if different
aws apigatewayv2 get-integration \
  --api-id 9zke9jame0 \
  --integration-id vgjpa5n \
  --query 'IntegrationUri' \
  --output text
```

**If the output contains `get-activities`**, that's the problem!

### Step 2: Fix the Integration

```bash
# Update the integration to point to the correct Lambda
# NOTE: Replace API_ID, INTEGRATION_ID, and ACCOUNT_ID with your values
aws apigatewayv2 update-integration \
  --api-id 9zke9jame0 \
  --integration-id vgjpa5n \
  --integration-uri "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:rabbitmiles-admin-all-activities"

# Get your AWS account ID if needed:
# aws sts get-caller-identity --query Account --output text
```

### Step 3: Verify the Fix

Refresh the admin page. You should now see:

```
Afternoon Run
Athlete: Tim Hibbard      ← This line should now appear
Type: Run
Distance: 6.35 mi

Dog walk
Athlete: Alyssa Smith     ← Different athletes should appear
Type: Walk
Distance: 1.70 mi
```

## Detailed Diagnosis

### Step 1: Check if the Lambda exists

```bash
aws lambda get-function --function-name rabbitmiles-admin-all-activities
```

**If this fails**, the Lambda was never created. Follow the deployment guide in `ADMIN_ALL_ACTIVITIES_DEPLOYMENT.md`.

### Step 2: Check if the API Gateway route exists

```bash
# First, get your API ID
aws apigatewayv2 get-apis --query 'Items[?Name==`RabbitMiles` || Name==`rabbitmiles`].[ApiId,Name]' --output table

# Then list routes (replace YOUR_API_ID)
aws apigatewayv2 get-routes --api-id YOUR_API_ID --query 'Items[?RouteKey==`GET /admin/activities`]' --output json
```

**If this returns empty `[]`**, the route doesn't exist and needs to be created.

### Step 3: Test the endpoint directly

```bash
# Get your session cookie from the browser (DevTools > Application > Cookies > rm_session)
# Then test the endpoint:
curl -v -X GET "https://api.rabbitmiles.com/admin/activities?limit=10" \
  --cookie "rm_session=YOUR_SESSION_COOKIE" \
  -H "Origin: https://rabbitmiles.com"
```

**Expected**: Activities from multiple users with `athlete_name` field
**If you see**: 404 error → route doesn't exist
**If you see**: Only your activities → route points to wrong Lambda

## Solution

### Option A: Full Deployment (Recommended if Lambda doesn't exist)

Follow the complete deployment guide in `ADMIN_ALL_ACTIVITIES_DEPLOYMENT.md`. This includes:

1. Creating the Lambda function
2. Setting environment variables
3. Configuring IAM permissions  
4. Creating the API Gateway route
5. Setting up the GitHub Actions secret

### Option B: Quick Fix (If Lambda exists but route is missing/wrong)

#### 1. Verify Lambda exists and has correct code

```bash
# Download and check the Lambda code
aws lambda get-function --function-name rabbitmiles-admin-all-activities \
  --query 'Code.Location' --output text | xargs curl -o /tmp/lambda.zip

# Unzip and check the SQL query
unzip -p /tmp/lambda.zip lambda_function.py | grep -A 20 "FROM activities"
```

You should see **NO WHERE clause** filtering by athlete_id:
```python
FROM activities a
LEFT JOIN users u ON a.athlete_id = u.athlete_id
ORDER BY a.start_date_local DESC
LIMIT :limit OFFSET :offset
```

#### 2. Get your API Gateway ID

```bash
aws apigatewayv2 get-apis --query 'Items[?Name==`RabbitMiles` || Name==`rabbitmiles`].[ApiId,Name]' --output table
```

Note the API ID from the output.

#### 3. Create the integration

```bash
# Replace YOUR_API_ID and YOUR_ACCOUNT_ID
aws apigatewayv2 create-integration \
  --api-id YOUR_API_ID \
  --integration-type AWS_PROXY \
  --integration-uri "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:rabbitmiles-admin-all-activities" \
  --payload-format-version 2.0
```

Note the integration ID from the output (e.g., `abc123`).

#### 4. Create the route

```bash
# Replace YOUR_API_ID and INTEGRATION_ID (from step 3)
aws apigatewayv2 create-route \
  --api-id YOUR_API_ID \
  --route-key "GET /admin/activities" \
  --target "integrations/INTEGRATION_ID"
```

#### 5. Grant API Gateway permission to invoke Lambda

```bash
aws lambda add-permission \
  --function-name rabbitmiles-admin-all-activities \
  --statement-id apigateway-invoke-admin-activities \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:YOUR_ACCOUNT_ID:YOUR_API_ID/*/*/admin/activities"
```

#### 6. Deploy the API (if using stages)

```bash
aws apigatewayv2 create-deployment \
  --api-id YOUR_API_ID \
  --stage-name prod
```

### Option C: Fix Incorrect Route

If the route exists but points to the wrong Lambda:

```bash
# 1. Find the current integration
aws apigatewayv2 get-routes --api-id YOUR_API_ID \
  --query 'Items[?RouteKey==`GET /admin/activities`].[RouteId,Target]' \
  --output table

# 2. Get the integration ID from the Target (format: integrations/xyz)

# 3. Update the integration
aws apigatewayv2 update-integration \
  --api-id YOUR_API_ID \
  --integration-id INTEGRATION_ID \
  --integration-uri "arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:rabbitmiles-admin-all-activities"
```

## Verification

After applying the fix:

### 1. Test via curl

```bash
curl -X GET "https://api.rabbitmiles.com/admin/activities?limit=5" \
  --cookie "rm_session=YOUR_SESSION_COOKIE" \
  -H "Origin: https://rabbitmiles.com" | jq '.activities[] | {athlete_name, name}'
```

You should see activities from **different athletes**:
```json
{
  "athlete_name": "Alyssa Smith",
  "name": "Morning Run"
}
{
  "athlete_name": "Blake Smith",  
  "name": "Afternoon Ride"
}
{
  "athlete_name": "Tim Hibbard",
  "name": "Evening Run"
}
```

### 2. Test in browser

1. Go to https://rabbitmiles.com/admin
2. Look at "All Athletes' Activities (50)"
3. You should see activities from multiple users with their names displayed

### 3. Check CloudWatch logs

```bash
# Get recent log events
aws logs tail /aws/lambda/rabbitmiles-admin-all-activities --follow
```

Look for:
```
LOG - Admin 3519964 authenticated successfully
LOG - Fetching activities for all users
LOG - Querying all activities (limit=50, offset=0)
LOG - Found X activities
```

## Still Not Working?

### Check the Lambda code

The SQL query in `backend/admin_all_activities/lambda_function.py` should have **NO WHERE clause**:

```python
sql = """
SELECT 
    a.id,
    a.athlete_id,
    ...
FROM activities a
LEFT JOIN users u ON a.athlete_id = u.athlete_id
ORDER BY a.start_date_local DESC
LIMIT :limit OFFSET :offset
"""
```

If you see `WHERE athlete_id = :aid` or similar, the wrong code was deployed.

### Re-deploy the Lambda

```bash
cd backend/admin_all_activities
zip -r lambda.zip lambda_function.py
cd ..
zip lambda.zip admin_utils.py
aws lambda update-function-code \
  --function-name rabbitmiles-admin-all-activities \
  --zip-file fileb://lambda.zip
```

## Related Documentation

- **Full Deployment Guide**: `ADMIN_ALL_ACTIVITIES_DEPLOYMENT.md`
- **Investigation Report**: `INVESTIGATION_ALL_ATHLETES_ACTIVITIES.md`
- **GitHub Actions Setup**: `GITHUB_ACTIONS_SECRETS.md`

## Prevention

To ensure this endpoint is deployed correctly in the future:

1. **Set the GitHub Actions secret**: `LAMBDA_ADMIN_ALL_ACTIVITIES` with the function name
2. **Verify the secret**: Check repository Settings → Secrets → Actions
3. **Trigger deployment**: Push to main branch or manually trigger the workflow
4. **Monitor the deployment**: Check Actions tab for deployment status
