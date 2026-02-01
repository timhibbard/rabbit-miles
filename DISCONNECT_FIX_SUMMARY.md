# Disconnect Fix - Summary

## Problem
When users clicked the "Disconnect Strava" button on the connect page, they saw a 404 error instead of being disconnected.

## Root Cause
**HTTP Method Mismatch:**
- API Gateway was configured for: `POST /auth/disconnect`
- Frontend was making a request: `GET /auth/disconnect` (via `window.location.href`)
- Result: 404 Not Found

## Solution
Change the API Gateway route from POST to GET to match the frontend implementation.

## What Was Changed
1. **Documentation** (`.github/copilot-instructions.md`): Updated to reflect GET method
2. **Lambda Code Comment** (`backend/auth_disconnect/lambda_function.py`): Clarified GET is the expected method
3. **Deployment Guide** (`DISCONNECT_FIX.md`): Complete instructions for fixing the API Gateway route

## What You Need to Do
After this PR is merged and the Lambda deploys:

### Update API Gateway Route
**Option 1 - AWS Console:**
1. Go to API Gateway in AWS Console
2. Select your HTTP API
3. Find the `POST /auth/disconnect` route
4. Change it to `GET /auth/disconnect`
5. Deploy to prod stage

**Option 2 - AWS CLI:**
```bash
aws apigatewayv2 update-route \
  --api-id <your-api-id> \
  --route-id <route-id> \
  --route-key "GET /auth/disconnect"
```

See `DISCONNECT_FIX.md` for detailed step-by-step instructions.

## Why GET?
- **Consistency**: Matches `/auth/start` and `/auth/callback` endpoints
- **Simplicity**: Works with existing `window.location.href` pattern
- **Security**: Still requires valid session cookie
- **UX**: Simple navigation vs form submission

## Testing
After updating the API Gateway route:
1. Go to your connect page
2. Click "Connect with Strava" and log in
3. Click "Disconnect Strava"
4. Should see disconnected state (no 404)

## Files Changed
- `.github/copilot-instructions.md` - Updated endpoint documentation
- `backend/auth_disconnect/lambda_function.py` - Added method comment
- `DISCONNECT_FIX.md` - New deployment guide (you're reading the summary!)

## Security
✅ CodeQL scan passed with 0 alerts
✅ Session cookie required (prevents CSRF)
✅ Idempotent operation (safe to retry)

---

**Need Help?** See the detailed guide in `DISCONNECT_FIX.md`
