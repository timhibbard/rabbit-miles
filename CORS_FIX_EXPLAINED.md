# CORS Error Fix - Technical Explanation

## Problem
After successfully authenticating with Strava, users saw an "Unable to Connect - Network Error" message. The browser console showed:
```
Origin https://timhibbard.github.io is not allowed by Access-Control-Allow-Origin. Status code: 401
```

## Root Cause
The issue was a mismatch between:
1. **Browser Origin header**: `https://timhibbard.github.io` (scheme + host only)
2. **CORS Allow-Origin header**: `https://timhibbard.github.io/rabbit-miles` (included path)

### Why This Happened
The `FRONTEND_URL` environment variable was set to `https://timhibbard.github.io/rabbit-miles` (the full app URL including the base path), but browsers only send the origin (scheme + host) in the `Origin` header, never including the path.

According to the CORS specification:
- The `Origin` header format is: `<scheme>://<host>[:<port>]`
- The `Access-Control-Allow-Origin` response header must match this exact format
- Paths are NOT included in origins

## Solution
Modified `backend/me/lambda_function.py` to:

1. **Extract the origin from FRONTEND_URL**:
   ```python
   def get_cors_origin():
       """Extract origin (scheme + host) from FRONTEND_URL for CORS headers"""
       if not FRONTEND_URL:
           return None
       parsed = urlparse(FRONTEND_URL)
       # Origin only includes scheme + netloc (no path)
       return f"{parsed.scheme}://{parsed.netloc}"
   ```

2. **Use the extracted origin in CORS headers**:
   ```python
   def get_cors_headers():
       """Return CORS headers for cross-origin requests"""
       headers = {
           "Content-Type": "application/json",
       }
       origin = get_cors_origin()
       if origin:
           headers["Access-Control-Allow-Origin"] = origin
           headers["Access-Control-Allow-Credentials"] = "true"
       return headers
   ```

3. **Handle OPTIONS preflight requests**:
   ```python
   # Handle OPTIONS preflight requests
   if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
       return {
           "statusCode": 200,
           "headers": {
               **cors_headers,
               "Access-Control-Allow-Methods": "GET, OPTIONS",
               "Access-Control-Allow-Headers": "Content-Type, Cookie",
               "Access-Control-Max-Age": "86400"
           },
           "body": ""
       }
   ```

## What Changed
### Before
```python
# Directly used FRONTEND_URL (with path)
if FRONTEND_URL:
    headers["Access-Control-Allow-Origin"] = FRONTEND_URL  # ❌ Includes path
```

### After
```python
# Extract origin first (scheme + host only)
origin = get_cors_origin()  # Returns "https://timhibbard.github.io"
if origin:
    headers["Access-Control-Allow-Origin"] = origin  # ✅ Correct format
```

## Impact
- **FRONTEND_URL** can now be set to the full app URL (e.g., `https://timhibbard.github.io/rabbit-miles`)
- **CORS headers** correctly use just the origin part (e.g., `https://timhibbard.github.io`)
- No change needed to environment variables
- Fix is backwards compatible

## Testing
```bash
# Test with different FRONTEND_URL values
export FRONTEND_URL="https://timhibbard.github.io/rabbit-miles"
# Lambda will correctly return: Access-Control-Allow-Origin: https://timhibbard.github.io

export FRONTEND_URL="https://timhibbard.github.io"
# Lambda will correctly return: Access-Control-Allow-Origin: https://timhibbard.github.io

export FRONTEND_URL="http://localhost:3000/test"
# Lambda will correctly return: Access-Control-Allow-Origin: http://localhost:3000
```

## Deployment
1. **No environment variable changes needed** - existing FRONTEND_URL values work correctly
2. **Deploy updated Lambda function**:
   ```bash
   cd backend/me
   zip -r function.zip lambda_function.py
   aws lambda update-function-code \
     --function-name YOUR_ME_FUNCTION_NAME \
     --zip-file fileb://function.zip
   ```
3. **Verify** - Check browser Network tab shows correct CORS headers

## Technical Details
- **HTTP Method Check**: Uses API Gateway HTTP API v2 event format: `event.get("requestContext", {}).get("http", {}).get("method")`
- **OPTIONS Handling**: Returns 200 with appropriate CORS headers for preflight requests
- **Max-Age**: Set to 86400 seconds (24 hours) to cache preflight responses
- **Allowed Headers**: Explicitly allows `Content-Type` and `Cookie` headers

## References
- [CORS Specification](https://fetch.spec.whatwg.org/#http-cors-protocol)
- [MDN: Origin Header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Origin)
- [MDN: Access-Control-Allow-Origin](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Allow-Origin)
