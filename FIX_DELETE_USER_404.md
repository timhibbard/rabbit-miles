# Fix: Unable to Delete User (404 Error)

## Problem Summary

When trying to delete a user, you're seeing:
- ❌ `404` error in browser console
- ❌ `Preflight response is not successful. Status code: 404`
- ❌ `XMLHttpRequest cannot load https://api.rabbitmiles.com/admin/users/{athlete_id} due to access control checks`

## Root Cause

The API Gateway route for `DELETE /admin/users/{athlete_id}` is **not properly configured for CORS**. 

From the screenshot you provided, the API Gateway trigger shows:
- ✅ Method: `ANY` 
- ✅ Resource path: `/admin/users/{athlete_id}`
- ❌ **CORS: No** ← This is the problem!

When CORS is disabled in API Gateway, the browser's preflight OPTIONS request returns 404 before it can reach your Lambda function, even though your Lambda code correctly handles CORS.

## Solution

You have **two options** to fix this:

---

### Option 1: Automated Fix (Recommended) ⭐

Run the provided setup script to automatically configure the API Gateway route:

```bash
cd /path/to/rabbit-miles
./scripts/setup-admin-delete-user-route.sh
```

**What the script does:**
1. Finds your API Gateway HTTP API
2. Finds your `rabbitmiles-admin-delete-user` Lambda function  
3. Creates or updates the Lambda integration
4. Creates the `DELETE /admin/users/{athlete_id}` route
5. Creates the `OPTIONS /admin/users/{athlete_id}` route (for CORS preflight)
6. Adds Lambda invoke permissions for API Gateway
7. Verifies the setup

**Prerequisites:**
- AWS CLI installed: `aws --version`
- AWS credentials configured: `aws configure`
- IAM permissions to modify API Gateway and Lambda

**Expected Output:**
```
✅ Setup Complete!
API Gateway ID: your-api-id
Route: DELETE /admin/users/{athlete_id}
Lambda Function: rabbitmiles-admin-delete-user
```

---

### Option 2: Manual Fix via AWS Console

If you prefer to fix this manually in the AWS Console:

#### Step 1: Verify Your API Gateway Configuration

1. Go to [API Gateway Console](https://console.aws.amazon.com/apigateway/)
2. Find your RabbitMiles HTTP API (you can identify it by the API name)
3. Click on it to open the configuration
4. Note your API Gateway ID (you'll need it later)

#### Step 2: Check Route Configuration  

1. Click **Routes** in the left sidebar
2. Look for the route: `DELETE /admin/users/{athlete_id}` or `ANY /admin/users/{athlete_id}`

#### Step 3: Enable CORS (Critical!)

The key fix is to **enable CORS** for this route. You have two approaches:

**Approach A: Enable CORS at API Level (Easiest)**

1. In your API Gateway, click **CORS** in the left sidebar
2. Click **Configure**
3. Add these settings:
   - **Access-Control-Allow-Origin**: `https://rabbitmiles.com` (your frontend URL)
   - **Access-Control-Allow-Methods**: `DELETE, GET, OPTIONS`
   - **Access-Control-Allow-Headers**: `Content-Type, Cookie`
   - **Access-Control-Allow-Credentials**: ✅ **Checked** (very important for cookie-based auth!)
4. Click **Save**

**Approach B: Create Separate OPTIONS Route**

If CORS configuration at API level doesn't work, you need explicit OPTIONS route:

1. Click **Routes** → **Create**
2. Configure:
   - Method: `OPTIONS`
   - Resource path: `/admin/users/{athlete_id}`
   - Integration: Point to the same `rabbitmiles-admin-delete-user` Lambda
3. Click **Create**

#### Step 4: Verify Lambda Permissions

The Lambda needs permission for API Gateway to invoke it:

```bash
aws lambda add-permission \
  --function-name rabbitmiles-admin-delete-user \
  --statement-id apigateway-admin-delete-user \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:<YOUR_REGION>:<YOUR_ACCOUNT_ID>:<YOUR_API_GATEWAY_ID>/*/*/admin/users/*"
```

Replace:
- `<YOUR_REGION>` with your AWS region (e.g., `us-east-1`)
- `<YOUR_ACCOUNT_ID>` with your AWS account ID
- `<YOUR_API_GATEWAY_ID>` with your API Gateway ID from Step 1

#### Step 5: Deploy Changes

If you made changes in the API Gateway console:
1. Click **Deployments** in the left sidebar  
2. Click **Deploy API** or it may auto-deploy depending on your stage configuration
3. Wait for deployment to complete

---

## Testing the Fix

After applying the fix, test the delete user functionality:

1. Open your RabbitMiles admin page in browser
2. Open Developer Tools (F12) → Network tab
3. Try to delete a user
4. You should see:
   - ✅ `OPTIONS /admin/users/{athlete_id}` → Status `200 OK`
   - ✅ `DELETE /admin/users/{athlete_id}` → Status `200 OK` (or `404` if user doesn't exist)

### Expected Successful Response

```json
{
  "success": true,
  "deleted": {
    "athlete_id": 123456789,
    "display_name": "Example User",
    "activities_count": 42
  }
}
```

---

## Why This Happened

The Lambda function (`rabbitmiles-admin-delete-user`) was deployed successfully and is configured correctly, **but the API Gateway route was never properly connected to it with CORS support**.

The Lambda code already handles CORS correctly (see `backend/admin_delete_user/lambda_function.py`), but the browser never reaches the Lambda because the API Gateway blocks the preflight OPTIONS request when CORS is disabled.

---

## Verification Checklist

After fixing, verify:

- [ ] Lambda function exists: `rabbitmiles-admin-delete-user`
- [ ] Lambda has correct environment variables (APP_SECRET, FRONTEND_URL, DB_*, ADMIN_ATHLETE_IDS)
- [ ] API Gateway route exists: `DELETE /admin/users/{athlete_id}`
- [ ] API Gateway CORS is enabled with credentials support
- [ ] OPTIONS route exists or CORS is configured at API level
- [ ] Lambda has permission for API Gateway to invoke it
- [ ] Browser preflight OPTIONS request returns 200 OK
- [ ] DELETE request successfully reaches the Lambda

---

## Related Documentation

- **Automated Setup Script**: `./scripts/setup-admin-delete-user-route.sh`
- **Detailed Troubleshooting**: `TROUBLESHOOTING_DELETE_USER.md`
- **Deployment Guide**: `DEPLOYMENT_DELETE_USER.md`
- **Lambda Code**: `backend/admin_delete_user/lambda_function.py`

---

## Still Having Issues?

If you're still getting 404 errors after following these steps:

1. Check CloudWatch Logs:
   ```bash
   aws logs tail /aws/lambda/rabbitmiles-admin-delete-user --follow
   ```
   
2. Verify the route exists:
   ```bash
   aws apigatewayv2 get-routes --api-id <YOUR_API_GATEWAY_ID>
   ```

3. Test with curl (bypass browser CORS):
   ```bash
   curl -X DELETE https://api.rabbitmiles.com/admin/users/123456789 \
     -H "Cookie: rm_session=<YOUR_SESSION_COOKIE>" \
     -v
   ```
   
   **Note:** To get your session cookie value:
   - Open browser DevTools (F12) → Application tab → Cookies
   - Find the cookie named `rm_session`
   - Copy its value

If the curl command works but the browser doesn't, it's definitely a CORS configuration issue.
