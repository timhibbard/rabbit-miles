# Why SameSite=None is Required for RabbitMiles Authentication

## Architecture Overview

RabbitMiles uses a cross-origin architecture:
- **Frontend**: `https://timhibbard.github.io/rabbit-miles` (GitHub Pages)
- **Backend API**: `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod` (AWS API Gateway)

These are different origins (different eTLD+1 domains), so browsers consider them **cross-site**.

## Cookie-Based Authentication Flow

1. User clicks "Connect with Strava" on frontend
2. Frontend redirects to backend `/auth/start`
3. Backend sets `rm_state` cookie and redirects to Strava
4. User authorizes on Strava
5. Strava redirects to backend `/auth/callback`
6. Backend sets `rm_session` cookie and redirects to frontend
7. Frontend calls `/me` API endpoint with cookies
8. Backend validates `rm_session` cookie and returns user data

## Why SameSite=None is Required

### SameSite Cookie Policies

- **`SameSite=Strict`**: Cookie is ONLY sent in same-site contexts
- **`SameSite=Lax`**: Cookie is sent:
  - ✅ In same-site requests
  - ✅ In top-level navigation (e.g., clicking a link, OAuth redirects)
  - ❌ **NOT in cross-site XHR/fetch/AJAX requests**
- **`SameSite=None`**: Cookie is sent in ALL contexts (requires `Secure` flag)

### The Problem with SameSite=Lax

When the frontend on `timhibbard.github.io` makes an XHR/fetch request to the API on `9zke9jame0.execute-api.us-east-1.amazonaws.com`:

1. Browser detects this is a **cross-site request**
2. With `SameSite=Lax`, browser **does NOT include** the `rm_session` cookie
3. Backend `/me` endpoint receives request **without cookie**
4. Backend returns 401 Unauthorized
5. User appears not logged in, even though they completed OAuth

### OAuth Redirect Works, but API Calls Don't

- **OAuth callback redirect**: Top-level navigation, so `SameSite=Lax` cookie IS sent ✅
- **Frontend API calls** (fetchMe, fetchActivities): Cross-site XHR, so `SameSite=Lax` cookie is NOT sent ❌

This creates a confusing situation where:
- User successfully completes OAuth
- Backend sets the session cookie
- But frontend API calls can't authenticate

## Solution: Use SameSite=None

For cookie-based authentication in a cross-origin architecture, `SameSite=None` is **required** to allow cookies in cross-site fetch/XHR requests.

### Security Considerations

`SameSite=None` is secure when combined with:

1. **`Secure` flag**: Cookie only sent over HTTPS (we use this) ✅
2. **`HttpOnly` flag**: Cookie not accessible via JavaScript (we use this) ✅
3. **CORS policy**: Backend only accepts requests from trusted frontend origin ✅
4. **Signed cookies**: Session tokens are cryptographically signed (we use HMAC) ✅
5. **Short expiration**: Cookies expire after 30 days ✅

### Mobile Safari Compatibility

Modern mobile Safari (iOS 13+) fully supports `SameSite=None` when combined with the `Secure` flag. The key requirements are:

- HTTPS on both frontend and backend ✅
- Properly formatted cookie string ✅
- `Secure` flag present ✅

Mobile Safari's Intelligent Tracking Prevention (ITP) may limit cookie lifetime for cross-site contexts, but it does NOT block `SameSite=None` cookies entirely.

## Alternative Architectures (Not Applicable Here)

If we wanted to avoid `SameSite=None`, we would need:

1. **Same-site architecture**: Deploy frontend and backend on the same domain
   - Example: `app.rabbitmiles.com` (frontend) and `api.rabbitmiles.com` (backend)
   - Both share the same eTLD+1: `rabbitmiles.com`
   - Then `SameSite=Lax` would work

2. **Token-based auth** instead of cookies
   - Store tokens in JavaScript (less secure - vulnerable to XSS)
   - Or use Web Storage API (also vulnerable to XSS)
   - Not recommended for security reasons

## Conclusion

For RabbitMiles' current architecture (GitHub Pages + API Gateway), **`SameSite=None` is the correct and secure choice** for cookie-based authentication.

The previous change to `SameSite=Lax` in PR #103 broke authentication because it prevented cross-site API requests from including the session cookie.

## References

- [MDN: SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
- [Chrome SameSite cookie policy](https://www.chromium.org/updates/same-site/)
- [WebKit ITP documentation](https://webkit.org/tracking-prevention/)
