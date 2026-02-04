# Mobile Safari Authentication Flow Diagram

## Before Fix (Cookie-Only) - BROKEN on Mobile Safari

```
┌─────────────┐
│   User      │
│  (Mobile    │
│  Safari)    │
└──────┬──────┘
       │
       │ 1. Click "Connect with Strava"
       │
       ▼
┌────────────────────────────────────────────┐
│  Frontend (GitHub Pages)                   │
│  https://timhibbard.github.io              │
└──────┬─────────────────────────────────────┘
       │
       │ 2. Redirect to /auth/start
       │
       ▼
┌────────────────────────────────────────────┐
│  Backend (API Gateway Lambda)              │
│  https://9zke9jame0.execute-api...         │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  auth_start                          │ │
│  │  - Generate OAuth state              │ │
│  │  - Store in database                 │ │
│  │  - Set rm_state cookie               │ │
│  │  - Redirect to Strava                │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 3. Redirect to Strava OAuth
       │
       ▼
┌────────────────────────────────────────────┐
│  Strava OAuth                              │
│  https://www.strava.com/oauth/authorize    │
└──────┬─────────────────────────────────────┘
       │
       │ 4. User authorizes
       │
       ▼
┌────────────────────────────────────────────┐
│  Backend (API Gateway Lambda)              │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  auth_callback                       │ │
│  │  - Validate state                    │ │
│  │  - Exchange code for tokens          │ │
│  │  - Create user in database           │ │
│  │  - Set rm_session cookie ✓           │ │
│  │  - Redirect to frontend              │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 5. Redirect to /connect?connected=1
       │    Cookie: rm_session=<token>
       │
       ▼
┌────────────────────────────────────────────┐
│  Frontend (GitHub Pages)                   │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  ConnectStrava.jsx                   │ │
│  │  - Check authentication              │ │
│  │  - Call /me endpoint                 │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 6. GET /me
       │    Cookie: rm_session=<token>  ❌ BLOCKED BY ITP
       │
       ▼
┌────────────────────────────────────────────┐
│  Backend (API Gateway Lambda)              │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  me                                  │ │
│  │  - Parse cookies                     │ │
│  │  - No cookie found! ❌               │ │
│  │  - Return 401 Unauthorized           │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 7. 401 Unauthorized ❌
       │
       ▼
┌────────────────────────────────────────────┐
│  Frontend - User sees "Connect" button    │
│  (appears not logged in)                   │
└────────────────────────────────────────────┘
```

## After Fix (Dual Authentication) - WORKS on Mobile Safari

```
┌─────────────┐
│   User      │
│  (Mobile    │
│  Safari)    │
└──────┬──────┘
       │
       │ 1. Click "Connect with Strava"
       │
       ▼
┌────────────────────────────────────────────┐
│  Frontend (GitHub Pages)                   │
│  https://timhibbard.github.io              │
└──────┬─────────────────────────────────────┘
       │
       │ 2. Redirect to /auth/start
       │
       ▼
┌────────────────────────────────────────────┐
│  Backend (API Gateway Lambda)              │
│  https://9zke9jame0.execute-api...         │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  auth_start                          │ │
│  │  - Generate OAuth state              │ │
│  │  - Store in database                 │ │
│  │  - Set rm_state cookie               │ │
│  │  - Redirect to Strava                │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 3. Redirect to Strava OAuth
       │
       ▼
┌────────────────────────────────────────────┐
│  Strava OAuth                              │
│  https://www.strava.com/oauth/authorize    │
└──────┬─────────────────────────────────────┘
       │
       │ 4. User authorizes
       │
       ▼
┌────────────────────────────────────────────┐
│  Backend (API Gateway Lambda)              │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  auth_callback                       │ │
│  │  - Validate state                    │ │
│  │  - Exchange code for tokens          │ │
│  │  - Create user in database           │ │
│  │  - Set rm_session cookie ✓           │ │
│  │  - Add token to URL fragment ✓ NEW  │ │
│  │  - Redirect to frontend              │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 5. Redirect to /connect?connected=1#session=<token>
       │    Cookie: rm_session=<token> (will be blocked)
       │    Fragment: #session=<token> ✓ NEW
       │
       ▼
┌────────────────────────────────────────────┐
│  Frontend (GitHub Pages)                   │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  ConnectStrava.jsx                   │ │
│  │  - Extract token from fragment ✓ NEW│ │
│  │  - Validate token format ✓ NEW      │ │
│  │  - Store in sessionStorage ✓ NEW    │ │
│  │  - Clear URL fragment ✓ NEW         │ │
│  │  - Call /me endpoint                 │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 6. GET /me
       │    Authorization: Bearer <token> ✓ NEW
       │    Cookie: rm_session=<token> (blocked by ITP)
       │
       ▼
┌────────────────────────────────────────────┐
│  Backend (API Gateway Lambda)              │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │  me                                  │ │
│  │  - Check Authorization header ✓ NEW │ │
│  │  - Token found! ✓                    │ │
│  │  - Verify signature ✓                │ │
│  │  - Return user data                  │ │
│  └──────────────────────────────────────┘ │
└──────┬─────────────────────────────────────┘
       │
       │ 7. 200 OK with user data ✓
       │
       ▼
┌────────────────────────────────────────────┐
│  Frontend - User sees Dashboard            │
│  (logged in successfully!) ✓               │
└────────────────────────────────────────────┘
```

## Key Differences

### Before Fix
- ❌ Cookie set but blocked by Mobile Safari ITP on API requests
- ❌ Frontend has no alternative auth method
- ❌ Backend only checks cookies
- ❌ Result: 401 Unauthorized

### After Fix
- ✅ Cookie still set (works on desktop)
- ✅ Token also in URL fragment (works on mobile)
- ✅ Frontend extracts token and sends in Authorization header
- ✅ Backend checks Authorization header first, then cookie
- ✅ Result: Authentication succeeds on both desktop and mobile

## Desktop Browsers (Chrome, Firefox, Safari)

Desktop browsers accept the cookie and continue to use cookie-based auth:

```
GET /me
Cookie: rm_session=<token> ✓ (works on desktop)
Authorization: Bearer <token> ✓ (also sent but not needed)

Backend checks:
1. Authorization header? Yes → Use it ✓
2. Cookie? Yes → Use it ✓
Either works! ✓
```

## Mobile Safari

Mobile Safari blocks the cookie but Authorization header works:

```
GET /me
Cookie: rm_session=<token> ❌ (blocked by ITP)
Authorization: Bearer <token> ✓ (works!)

Backend checks:
1. Authorization header? Yes → Use it ✓
Result: Authentication succeeds ✓
```

## Security Flow

```
┌──────────────────────────────────────────┐
│  Token Creation (Backend)                │
│                                          │
│  payload = {                             │
│    "aid": athlete_id,                    │
│    "exp": timestamp + 30 days            │
│  }                                       │
│                                          │
│  base64 = base64url(json(payload))       │
│  signature = hmac_sha256(APP_SECRET,     │
│                          base64)         │
│  token = base64 + "." + signature        │
│                                          │
│  Example:                                │
│  eyJhaWQiOjEyMzQ1LCJleHAiOjE3MDk2...    │
│  .a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4d...  │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Token Delivery                          │
│                                          │
│  1. Set Cookie (for desktop)             │
│     Set-Cookie: rm_session=<token>;      │
│                 HttpOnly; Secure;        │
│                 SameSite=None            │
│                                          │
│  2. URL Fragment (for mobile)            │
│     /connect?connected=1#session=<token> │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Frontend Validation                     │
│                                          │
│  1. Extract from fragment                │
│  2. Validate format:                     │
│     ^[A-Za-z0-9_-]{20,}\.[a-f0-9]{64}$  │
│  3. Store in sessionStorage              │
│  4. Clear fragment immediately           │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Token Verification (Backend)            │
│                                          │
│  1. Split token: base64 + signature      │
│  2. Recompute signature with APP_SECRET  │
│  3. Compare signatures (constant-time)   │
│  4. Check expiration                     │
│  5. Return athlete_id if valid           │
└──────────────────────────────────────────┘
```

## Why URL Fragment is Secure

```
URL Structure:
https://example.com/path?query=value#fragment

Server sees:
https://example.com/path?query=value
                                      ↑ Fragment never sent to server!

Browser history:
When using replaceState() immediately, fragment not saved

Analytics/Logs:
Fragment never appears in server logs or analytics

Bookmarks:
Cleared before user can bookmark

Network monitoring:
Fragment visible in browser DevTools but not to network proxies
```

## Token Validation Example

```javascript
// Frontend validation
const MIN_TOKEN_BASE64_LENGTH = 20;
const SIGNATURE_HEX_LENGTH = 64;
const tokenPattern = new RegExp(
  `^[A-Za-z0-9_-]{${MIN_TOKEN_BASE64_LENGTH},}\\.` +
  `[a-f0-9]{${SIGNATURE_HEX_LENGTH}}$`
);

// Valid token examples:
✅ "eyJhaWQiOjEyMzQ1LCJleHAiOjE3MDk2MDAwMDB9.a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5"

// Invalid token examples:
❌ "short.a3f2b8c9d1..." (too short)
❌ "valid_base64.invalid_signature" (wrong signature format)
❌ "no_signature_part"
❌ "" (empty)
❌ "Bearer xyz" (wrong format)
```

## Browser Compatibility

| Browser | Cookie Auth | Authorization Header Auth |
|---------|-------------|---------------------------|
| Chrome Desktop | ✅ Works | ✅ Works (sent but not needed) |
| Firefox Desktop | ✅ Works | ✅ Works (sent but not needed) |
| Safari Desktop | ✅ Works | ✅ Works (sent but not needed) |
| Edge Desktop | ✅ Works | ✅ Works (sent but not needed) |
| Mobile Safari | ❌ Blocked by ITP | ✅ Works |
| Chrome Mobile | ✅ Works | ✅ Works (sent but not needed) |
| Firefox Mobile | ✅ Works | ✅ Works (sent but not needed) |

All browsers are now supported! ✅
