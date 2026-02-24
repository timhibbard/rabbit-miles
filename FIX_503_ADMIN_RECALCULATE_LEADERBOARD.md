# Fix for 503 Error on Admin Leaderboard Recalculate

## Problem

The `/admin/leaderboard/recalculate` endpoint returns a 503 error when called from the admin panel.

## Root Cause

The Lambda function `rabbitmiles-admin-recalculate-leaderboard` exists and is deployed, but **the API Gateway route is missing**. This causes API Gateway to return a 503 Service Unavailable error when the endpoint is called.

## Solution

Create the missing API Gateway route using the provided setup script.

### Quick Fix (5 minutes)

1. **Run the setup script:**
   ```bash
   ./scripts/setup-admin-recalculate-leaderboard-route.sh
   ```

2. **Follow the prompts:**
   - Enter your API Gateway ID when prompted
   - The script will auto-detect your Lambda function name

3. **Verify the route was created:**
   ```bash
   ./scripts/verify-api-gateway-routes.sh
   ```

### Manual Setup (if script fails)

If you prefer to set up the route manually via AWS Console:

1. **Open API Gateway** in AWS Console
2. **Navigate to your HTTP API** (rabbitmiles-api)
3. **Create a new route:**
   - Method: `POST`
   - Path: `/admin/leaderboard/recalculate`
   - Integration: Lambda function `rabbitmiles-admin-recalculate-leaderboard`
   - Payload format version: `2.0`
4. **Create OPTIONS route** (for CORS):
   - Method: `OPTIONS`
   - Path: `/admin/leaderboard/recalculate`
   - Integration: Same Lambda function
5. **Add Lambda permissions:**
   ```bash
   aws lambda add-permission \
     --function-name rabbitmiles-admin-recalculate-leaderboard \
     --statement-id apigateway-admin-recalculate-leaderboard \
     --action lambda:InvokeFunction \
     --principal apigateway.amazonaws.com \
     --source-arn "arn:aws:execute-api:REGION:ACCOUNT_ID:API_ID/*/*/admin/leaderboard/recalculate"
   ```

### Testing

After setting up the route, test it works:

```bash
# Get your admin session cookie from browser DevTools
curl -X POST https://api.rabbitmiles.com/admin/leaderboard/recalculate \
  -H "Cookie: rm_session=YOUR_ADMIN_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -v
```

Expected response:
```json
{
  "message": "Leaderboard recalculation completed successfully",
  "activities_processed": 123,
  "athletes_processed": 45,
  "duration_ms": 1234.56
}
```

## Prevention

The `verify-api-gateway-routes.sh` script has been updated to include this route in the expected routes list, so future deployments can be verified automatically.

## Technical Details

- Lambda exists: ✅ (deployed via GitHub Actions)
- API Gateway route: ❌ (missing - fixed by this PR)
- Lambda code: ✅ (no changes needed)

The Lambda function itself is working correctly; it just needs to be connected to API Gateway.
