# CORS Fix - Before and After

## Before Fix (Broken Flow)

```
┌─────────────────────────────────────────────────────────────┐
│ User connects with Strava                                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ OAuth completes, user redirected to:                        │
│ https://timhibbard.github.io/rabbit-miles/?connected=1      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Dashboard.jsx calls fetchMe()                               │
│ GET https://9zke9jame0.execute-api.us-east-1.amazonaws.com │
│     /prod/me                                                 │
│ (includes cookies with credentials)                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Lambda returns 200 OK with JSON body                        │
│ {                                                           │
│   "statusCode": 200,                                        │
│   "headers": {                                              │
│     "Content-Type": "application/json"                      │
│   },                                                        │
│   "body": "{\"athlete_id\": 12345, ...}"                    │
│ }                                                           │
│                                                             │
│ ❌ Missing CORS headers!                                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Browser BLOCKS the response due to CORS policy             │
│ Console error:                                              │
│ "Cross-Origin Request Blocked: The Same Origin Policy      │
│  disallows reading the remote resource..."                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ fetchMe() returns error                                     │
│ Dashboard shows: "Unable to Connect - Network Error"       │
└─────────────────────────────────────────────────────────────┘
```

## After Fix (Working Flow)

```
┌─────────────────────────────────────────────────────────────┐
│ User connects with Strava                                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ OAuth completes, user redirected to:                        │
│ https://timhibbard.github.io/rabbit-miles/?connected=1      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Dashboard.jsx calls fetchMe()                               │
│ GET https://9zke9jame0.execute-api.us-east-1.amazonaws.com │
│     /prod/me                                                 │
│ (includes cookies with credentials)                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Lambda returns 200 OK with JSON body AND CORS headers       │
│ {                                                           │
│   "statusCode": 200,                                        │
│   "headers": {                                              │
│     "Content-Type": "application/json",                     │
│     "Access-Control-Allow-Origin":                          │
│       "https://timhibbard.github.io/rabbit-miles",          │
│     "Access-Control-Allow-Credentials": "true"              │
│   },                                                        │
│   "body": "{\"athlete_id\": 12345, ...}"                    │
│ }                                                           │
│                                                             │
│ ✅ CORS headers present!                                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Browser ALLOWS the response due to matching CORS headers   │
│ - Origin matches: ✅                                         │
│ - Credentials allowed: ✅                                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ fetchMe() succeeds                                          │
│ Dashboard displays user info:                               │
│ - Profile picture                                           │
│ - Display name                                              │
│ - Statistics                                                │
└─────────────────────────────────────────────────────────────┘
```

## Key Changes

### 1. CORS Headers Added

**Headers now included in every response:**
```javascript
{
  "Access-Control-Allow-Origin": "https://timhibbard.github.io/rabbit-miles",
  "Access-Control-Allow-Credentials": "true",
  "Content-Type": "application/json"
}
```

### 2. Why These Headers Matter

- **Access-Control-Allow-Origin**: Tells the browser which origin is allowed to access the resource
- **Access-Control-Allow-Credentials**: Required when using cookies for authentication
- Without these, the browser blocks the response for security reasons

### 3. Error Responses Also Include CORS

**All error responses (401, 404, 500) also include CORS headers:**
```python
return {
    "statusCode": 401,
    "headers": cors_headers,  # ✅ CORS headers included
    "body": json.dumps({"error": "not authenticated"})
}
```

## Technical Implementation

### Code Added to lambda_function.py

```python
# Read frontend URL from environment
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

# Helper function to generate CORS headers
def get_cors_headers():
    headers = {
        "Content-Type": "application/json",
    }
    if FRONTEND_URL:
        headers["Access-Control-Allow-Origin"] = FRONTEND_URL
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers

# Use in handler
def handler(event, context):
    cors_headers = get_cors_headers()
    
    # All returns include cors_headers
    return {
        "statusCode": 200,
        "headers": cors_headers,
        "body": json.dumps({...})
    }
```

## Testing

### How to Verify CORS Headers

1. **Open Developer Tools** (F12)
2. **Go to Network tab**
3. **Navigate to your app**
4. **Click on the /me request**
5. **Check Response Headers**

Should see:
```
Access-Control-Allow-Origin: https://timhibbard.github.io/rabbit-miles
Access-Control-Allow-Credentials: true
Content-Type: application/json
```

### Using curl

```bash
curl -i \
  -H "Cookie: rm_session=YOUR_SESSION_TOKEN" \
  -H "Origin: https://timhibbard.github.io" \
  https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/me
```

Should see the CORS headers in the response.
