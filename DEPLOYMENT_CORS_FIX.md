# Deployment Guide: CORS Error Fix

## Overview
This deployment fixes the "Unable to Connect - Network Error" that occurs after Strava authentication. The fix corrects how CORS headers are generated to match the browser's Origin header format.

## What This Fix Does
- Extracts the origin (scheme + host only) from `FRONTEND_URL` for CORS headers
- Adds OPTIONS preflight request handling
- Validates URLs to handle malformed configurations gracefully
- **No environment variable changes required**

## Deployment Steps

### 1. Verify Prerequisites
Ensure you have:
- AWS CLI configured with appropriate permissions
- Access to the Lambda function for the `/me` endpoint

### 2. Package the Lambda Function
```bash
cd backend/me
zip -r function.zip lambda_function.py
```

### 3. Deploy to AWS Lambda
```bash
# Replace YOUR_ME_FUNCTION_NAME with your actual function name
aws lambda update-function-code \
  --function-name YOUR_ME_FUNCTION_NAME \
  --zip-file fileb://function.zip
```

### 4. Verify Deployment
Check the last modified timestamp to confirm deployment:
```bash
aws lambda get-function \
  --function-name YOUR_ME_FUNCTION_NAME \
  --query 'Configuration.LastModified'
```

### 5. Test the Fix
1. Open your browser's Developer Tools (F12)
2. Go to the Network tab
3. Navigate to your application and authenticate with Strava
4. After redirect, look for the request to `/me`
5. Click on the request and check the Response Headers
6. You should see:
   ```
   Access-Control-Allow-Origin: https://timhibbard.github.io
   Access-Control-Allow-Credentials: true
   ```

## Expected Behavior

### Before Fix
- Browser Origin: `https://timhibbard.github.io`
- CORS Allow-Origin: `https://timhibbard.github.io/rabbit-miles` ❌
- Result: CORS error, "Network Error" displayed

### After Fix
- Browser Origin: `https://timhibbard.github.io`
- CORS Allow-Origin: `https://timhibbard.github.io` ✅
- Result: Successful connection, user data loaded

## Environment Variables
**No changes required!** The fix automatically extracts the correct origin from the existing `FRONTEND_URL` environment variable.

### Current Setting (Example)
```bash
FRONTEND_URL=https://timhibbard.github.io/rabbit-miles
```

### What the Lambda Does Now
1. Reads `FRONTEND_URL`: `https://timhibbard.github.io/rabbit-miles`
2. Parses it to extract origin: `https://timhibbard.github.io`
3. Sets CORS header: `Access-Control-Allow-Origin: https://timhibbard.github.io`

## Validation Tests

### Test 1: Check CORS Headers
```bash
curl -i \
  -H "Origin: https://timhibbard.github.io" \
  https://YOUR_API_ENDPOINT/prod/me

# Look for these headers in the response:
# Access-Control-Allow-Origin: https://timhibbard.github.io
# Access-Control-Allow-Credentials: true
```

### Test 2: OPTIONS Preflight
```bash
curl -i -X OPTIONS \
  -H "Origin: https://timhibbard.github.io" \
  -H "Access-Control-Request-Method: GET" \
  https://YOUR_API_ENDPOINT/prod/me

# Should return 200 OK with:
# Access-Control-Allow-Methods: GET, OPTIONS
# Access-Control-Allow-Headers: Content-Type, Cookie
# Access-Control-Max-Age: 86400
```

### Test 3: End-to-End Flow
1. Clear browser cookies
2. Navigate to your application
3. Click "Connect with Strava"
4. Authorize the application
5. Verify you're redirected back successfully
6. Verify Dashboard loads with your user information
7. Verify no console errors

## Troubleshooting

### Still seeing CORS errors
1. **Check Lambda deployment**
   - Verify the function code was updated (check LastModified timestamp)
   - Check CloudWatch Logs for any errors

2. **Verify environment variable**
   ```bash
   aws lambda get-function-configuration \
     --function-name YOUR_ME_FUNCTION_NAME \
     --query 'Environment.Variables.FRONTEND_URL'
   ```
   - Ensure it's set to a valid URL
   - Should be the full app URL (e.g., `https://timhibbard.github.io/rabbit-miles`)

3. **Check API Gateway configuration**
   - Ensure API Gateway is configured to pass through Lambda response headers
   - Verify no conflicting CORS configuration at the API Gateway level

### Lambda errors in CloudWatch
```bash
aws logs tail /aws/lambda/YOUR_ME_FUNCTION_NAME --follow
```

Common issues:
- **Missing FRONTEND_URL**: Lambda will not add CORS headers (returns empty)
- **Malformed FRONTEND_URL**: Lambda validates and returns `None` for invalid URLs
- **Database connection errors**: Unrelated to CORS, check RDS permissions

### OPTIONS requests failing
- Ensure API Gateway HTTP API is configured to route OPTIONS requests to the Lambda
- Check that the Lambda execution role has necessary permissions

## Rollback Plan
If issues occur:

1. **Keep the new code**: The fix is backwards compatible and includes validation
2. **Or revert**: Deploy the previous version of the Lambda function
   ```bash
   # Get previous version
   aws lambda get-function \
     --function-name YOUR_ME_FUNCTION_NAME \
     --query 'Configuration.Version'
   
   # Revert (if versioning is enabled)
   aws lambda update-function-configuration \
     --function-name YOUR_ME_FUNCTION_NAME \
     --version PREVIOUS_VERSION
   ```

## Security Considerations
- ✅ CodeQL scan: No vulnerabilities found
- ✅ CORS uses explicit origin (not wildcard)
- ✅ Credentials properly configured for cookie auth
- ✅ URL validation prevents malformed origins
- ✅ All error responses include CORS headers

## Impact
- **Zero downtime**: Lambda update is atomic
- **Backwards compatible**: No breaking changes
- **No config changes**: Existing environment variables work
- **Immediate effect**: Fix applies to all requests after deployment

## Success Criteria
- [ ] Lambda function deployed successfully
- [ ] `/me` endpoint returns correct CORS headers
- [ ] OPTIONS preflight requests handled correctly
- [ ] OAuth flow completes without errors
- [ ] Dashboard loads with user information
- [ ] No "Unable to Connect" error displayed
- [ ] Browser console shows no CORS errors

## Additional Resources
- [CORS_FIX_EXPLAINED.md](./CORS_FIX_EXPLAINED.md) - Technical explanation
- [CORS Specification](https://fetch.spec.whatwg.org/#http-cors-protocol)
- [AWS Lambda Deployment](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-package.html)
