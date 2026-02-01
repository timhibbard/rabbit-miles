# Fix for /auth/disconnect 404 Error

## Issue
The disconnect button on the connect page returns a 404 "Not Found" error.

## Root Cause
The API Gateway route for `/auth/disconnect` was configured as `POST`, but the frontend makes a `GET` request using `window.location.href`.

## Solution
Change the API Gateway route from `POST` to `GET` to match the frontend implementation and be consistent with other auth endpoints.

## Deployment Steps

### 1. Update API Gateway Route

#### Using AWS Console:
1. Navigate to **API Gateway** in the AWS Console
2. Select your HTTP API (e.g., `rabbitmiles-api`)
3. Go to **Routes**
4. Find the route: `POST /auth/disconnect`
5. Click on the route to edit it
6. Change the method from `POST` to `GET`
7. Save the changes
8. Deploy the API to the appropriate stage (e.g., `prod`)

#### Using AWS CLI:
```bash
# First, find the API ID and route ID
export API_ID="your-api-gateway-id"  # e.g., 9zke9jame0
export ROUTE_ID="your-route-id"

# Update the route to use GET method
aws apigatewayv2 update-route \
  --api-id $API_ID \
  --route-id $ROUTE_ID \
  --route-key "GET /auth/disconnect"
```

To find your API ID and route ID:
```bash
# List APIs
aws apigatewayv2 get-apis

# List routes for your API
aws apigatewayv2 get-routes --api-id $API_ID
```

### 2. Verify the Fix

1. Navigate to https://timhibbard.github.io/rabbit-miles/connect
2. Log in with Strava (if not already logged in)
3. Click the "Disconnect Strava" button
4. Verify you are redirected back to the frontend without a 404 error
5. Check that you are shown as disconnected

## Expected Behavior After Fix
- User clicks "Disconnect Strava" button
- Browser navigates to `GET /auth/disconnect`
- Backend Lambda:
  - Validates session cookie
  - Clears Strava tokens from database
  - Clears session cookie
  - Redirects to frontend with `?connected=0`
- Frontend shows disconnected state

## Why GET Instead of POST?
1. **Consistency**: Other auth endpoints (`/auth/start`, `/auth/callback`) use GET
2. **User Experience**: Simple navigation (not a form submission)
3. **Idempotency**: Disconnect operation is safe to retry
4. **Frontend Pattern**: Using `window.location.href` is simpler and matches existing patterns

## Rollback
If you need to revert:
```bash
aws apigatewayv2 update-route \
  --api-id $API_ID \
  --route-id $ROUTE_ID \
  --route-key "POST /auth/disconnect"
```

The Lambda function works with both GET and POST methods, so rolling back only affects the frontend behavior.
