# iOS Strava App Deep Linking Implementation

## Overview

This document describes the implementation of iOS Strava app deep linking for OAuth authentication. When users on iOS devices have the Strava mobile app installed, they can now authenticate using the native app instead of being redirected to a web browser.

## Benefits

- **Better User Experience**: Native app authentication is faster and more intuitive
- **Seamless Integration**: If already logged into Strava app, no need to log in again
- **Automatic Fallback**: If the app isn't installed, automatically falls back to web OAuth
- **Backward Compatible**: Non-iOS devices continue to use the standard web OAuth flow

## How It Works

### Flow Diagram

```
1. User clicks "Connect with Strava"
   ↓
2. Frontend detects iOS device
   ↓
3. Frontend calls /auth/start?mobile=1
   ↓
4. Backend generates state token, sets cookie, returns OAuth URL
   ↓
5. Frontend constructs strava:// deep link
   ↓
6. Frontend attempts to open Strava app
   ↓
7a. App opens → User authenticates in app → Returns to callback
7b. App doesn't open → After 2.5s, fallback to web OAuth
   ↓
8. OAuth callback flow (unchanged)
```

### Technical Details

#### Frontend Changes

**File: `src/utils/device.js`** (NEW)
- `isIOS()`: Detects iOS devices including iPad running iPadOS 13+
- `openWithFallback()`: Attempts to open a deep link with automatic fallback

**File: `src/pages/ConnectStrava.jsx`** (MODIFIED)
- Detects iOS devices before initiating OAuth
- Calls `/auth/start?mobile=1` for iOS devices
- Constructs `strava://oauth/mobile/authorize` deep link
- Uses visibility change detection to cancel fallback if app opens
- Falls back to web OAuth after 2.5 seconds if app doesn't open

#### Backend Changes

**File: `backend/auth_start/lambda_function.py`** (MODIFIED)
- Added support for `?mobile=1` query parameter
- When mobile=1 is present:
  - Generates state token and stores it (same as web flow)
  - Sets `rm_state` cookie (same as web flow)
  - Returns JSON with OAuth URL instead of redirecting (HTTP 200)
  - Includes CORS headers for cross-origin requests
- When mobile=1 is not present:
  - Standard redirect flow (HTTP 302)

### iOS Detection Logic

The `isIOS()` function uses multiple detection methods:

1. **User Agent Check**: Detects `iPad`, `iPhone`, or `iPod` in user agent
2. **iPadOS 13+ Detection**: Checks for `MacIntel` platform with touch support
   - iPadOS 13+ reports as Mac to support desktop websites
   - But still has touch points (maxTouchPoints > 1)

### Deep Link Format

Standard Strava web OAuth URL:
```
https://www.strava.com/oauth/authorize?client_id=...&response_type=code&...
```

Strava mobile app deep link:
```
strava://oauth/mobile/authorize?client_id=...&response_type=code&...
```

The deep link uses the exact same query parameters as the web OAuth URL.

### Fallback Mechanism

The `openWithFallback()` function provides a robust fallback:

1. **Primary Attempt**: Tries to open the `strava://` deep link
2. **Visibility Detection**: Listens for page visibility changes
   - If page becomes hidden (app opened), cancel fallback timer
3. **Timeout Fallback**: After 2.5 seconds, if page is still visible, redirect to web OAuth
4. **Cleanup**: Removes event listeners after execution

## Security Considerations

- **State Token**: Still generated and validated server-side
- **Cookie Security**: `rm_state` cookie set with same security attributes
- **CORS**: Proper CORS headers ensure only authorized origins can make requests
- **No Client Secrets**: Client secret never exposed to frontend

## Testing

### Manual Testing on iOS

1. Install Strava app on iOS device
2. Navigate to RabbitMiles connect page
3. Click "Connect with Strava"
4. Verify Strava app opens (not browser)
5. Complete OAuth in app
6. Verify redirect back to RabbitMiles

### Testing Without Strava App

1. Remove Strava app from iOS device
2. Navigate to RabbitMiles connect page
3. Click "Connect with Strava"
4. Wait 2.5 seconds
5. Verify browser opens with Strava web OAuth

### Testing on Non-iOS Devices

1. Use Android, Windows, or Mac device
2. Navigate to RabbitMiles connect page
3. Click "Connect with Strava"
4. Verify standard web OAuth flow (immediate browser redirect)

## Deployment

### Frontend

Frontend changes are automatically deployed via GitHub Actions when merged to `main`:
- Vite builds the updated React app
- Static files deployed to GitHub Pages

### Backend

Backend Lambda changes are automatically deployed via GitHub Actions when merged to `main`:
- `backend/auth_start/lambda_function.py` is packaged and deployed
- No environment variable changes needed
- No new AWS resources required

## Monitoring and Logs

### Backend Logs (CloudWatch)

Look for these log messages in the `auth_start` Lambda:

```
LOG - Mobile request detected - will return OAuth URL for deep linking
LOG - Returning OAuth parameters for mobile deep linking
AUTH START LAMBDA - SUCCESS (MOBILE)
```

### Frontend Logs (Browser Console)

When debug mode is enabled:

```
ConnectStrava: Device is iOS: true
ConnectStrava: Fetching mobile OAuth URL from: ...
ConnectStrava: Received OAuth data: ...
ConnectStrava: Mobile deep link: strava://oauth/mobile/authorize?...
ConnectStrava: Attempting to open Strava app with fallback to web
```

## Troubleshooting

### Issue: Deep link doesn't open Strava app

**Possible causes:**
1. Strava app not installed → Expected, fallback should work
2. iOS version too old → Strava app requires iOS 14+
3. Deep link blocked by browser → Unlikely in Safari

**Solution:**
- Verify Strava app is installed and up to date
- Check iOS version (Settings → General → About → Software Version)
- Fallback to web OAuth should work automatically

### Issue: Cookie not set on mobile

**Possible causes:**
1. CORS misconfiguration
2. Safari blocking cross-site cookies

**Solution:**
- Verify CORS headers in response
- Check `Access-Control-Allow-Credentials: true` header
- Verify frontend uses `credentials: 'include'` in fetch

### Issue: Falls back to web immediately

**Possible causes:**
1. Strava app taking longer than 2.5s to open
2. Visibility change event not firing

**Solution:**
- Increase timeout in `openWithFallback()` call
- Check for iOS browser restrictions
- Verify event listeners are working

## Future Enhancements

1. **Android Support**: Implement similar deep linking for Android devices
2. **Adaptive Timeout**: Adjust fallback timeout based on device performance
3. **User Preference**: Allow users to prefer web or app OAuth
4. **Analytics**: Track success rate of app vs web OAuth

## References

- [Strava OAuth Documentation](https://developers.strava.com/docs/authentication/)
- [iOS Universal Links](https://developer.apple.com/ios/universal-links/)
- [Custom URL Schemes](https://developer.apple.com/documentation/xcode/defining-a-custom-url-scheme-for-your-app)
