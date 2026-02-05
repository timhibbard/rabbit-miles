# 🎯 OAuth Callback URL Update

## ⚠️ STATUS: REVERTED

**This change has been reverted. See `DEPLOYMENT_CALLBACK_DOMAIN_FIX.md` for the current implementation.**

The OAuth flow now uses the API Gateway domain (`9zke9jame0.execute-api.us-east-1.amazonaws.com`) directly instead of going through the frontend callback page. This simplifies the flow and requires only one domain to be configured in Strava.

## Original Summary (No Longer Active)
This PR updates the Strava OAuth callback flow to use the GitHub Pages frontend URL (`https://timhibbard.github.io/rabbit-miles/callback`) instead of the API Gateway URL. This allows you to configure `timhibbard.github.io` as the **Authorization Callback Domain** in your Strava application settings.

## What's Changed

### Frontend Changes
- ✅ Added new `/callback` route that handles OAuth redirects from Strava
- ✅ Created `OAuthCallback.jsx` page that forwards OAuth params to backend
- ✅ Updated routing in `App.jsx` to include the callback route

### Backend Changes
- ✅ Updated `auth_start` Lambda to redirect Strava to `{FRONTEND_URL}/callback`
- ✅ Added `FRONTEND_URL` environment variable requirement to `auth_start`
- ⚠️ No changes needed to `auth_callback` Lambda (already uses `FRONTEND_URL`)

## 🚨 Actions Required

### 1. Update Strava Application Settings

In your [Strava API application settings](https://www.strava.com/settings/api):

1. **Authorization Callback Domain**: Change from:
   ```
   9zke9jame0.execute-api.us-east-1.amazonaws.com
   ```
   To:
   ```
   timhibbard.github.io
   ```

2. **Save the changes**

### 2. Deploy Updated Lambda Function

The `auth_start` Lambda needs to be redeployed with the updated code:

```bash
cd backend/auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://function.zip
```

### 3. Set FRONTEND_URL Environment Variable

If not already set, add the `FRONTEND_URL` environment variable to `auth_start` Lambda:

```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-start \
  --environment Variables='{
    "DB_CLUSTER_ARN":"<your-cluster-arn>",
    "DB_SECRET_ARN":"<your-secret-arn>",
    "DB_NAME":"postgres",
    "API_BASE_URL":"https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod",
    "FRONTEND_URL":"https://timhibbard.github.io/rabbit-miles",
    "STRAVA_CLIENT_ID":"<your-client-id>"
  }'
```

**Note**: Make sure to include all existing environment variables when updating.

### 4. Deploy Frontend

The frontend changes are already committed. Deploy them to GitHub Pages:

```bash
npm run build
# Then push to GitHub - GitHub Actions will deploy to Pages
```

## 📊 New OAuth Flow

### Before (Old Flow)
```
User clicks "Connect with Strava"
  ↓
Frontend redirects to: API Gateway /auth/start
  ↓
auth_start redirects to: Strava OAuth
  ↓
Strava redirects to: API Gateway /auth/callback ← Uses API Gateway domain
  ↓
auth_callback validates & sets cookie
  ↓
Redirects to: Frontend /connect?connected=1
```

### After (New Flow)
```
User clicks "Connect with Strava"
  ↓
Frontend redirects to: API Gateway /auth/start
  ↓
auth_start redirects to: Strava OAuth
  ↓
Strava redirects to: Frontend /callback ← Uses GitHub Pages domain ✨
  ↓
Frontend forwards to: API Gateway /auth/callback
  ↓
auth_callback validates & sets cookie
  ↓
Redirects to: Frontend /connect?connected=1
```

## ✅ Benefits

1. **Cleaner Strava Configuration**: Use your user-facing domain in Strava settings
2. **Better UX**: Users stay on your branded domain during OAuth
3. **Flexibility**: Frontend handles the callback, giving more control
4. **Consistency**: All user-facing URLs use `timhibbard.github.io`

## 🔍 How to Test

After deployment:

1. **Clear cookies**: Clear browser cookies for both domains
2. **Go to Connect page**: Visit `https://timhibbard.github.io/rabbit-miles/connect`
3. **Click "Connect with Strava"**: Initiates OAuth flow
4. **Authorize on Strava**: Should redirect to Strava authorization page
5. **After authorization**: Should briefly see the callback page with spinner
6. **Final redirect**: Should land on `/connect?connected=1` with user info

### Expected URLs During Flow
1. `https://timhibbard.github.io/rabbit-miles/connect` - Start
2. `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/start` - Initiates OAuth
3. `https://www.strava.com/oauth/authorize?...` - Strava authorization
4. `https://timhibbard.github.io/rabbit-miles/callback?code=XXX&state=YYY` - **New callback**
5. `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback?code=XXX&state=YYY` - Backend validation
6. `https://timhibbard.github.io/rabbit-miles/connect?connected=1` - Success!

## 🐛 Troubleshooting

### Error: "redirect_uri mismatch"
- **Cause**: Strava application not updated with new callback domain
- **Fix**: Update Authorization Callback Domain in Strava settings to `timhibbard.github.io`

### Error: "Invalid OAuth callback"
- **Cause**: Missing `code` or `state` parameters
- **Fix**: Check that Strava is redirecting correctly to `/callback` route

### Lambda still using old redirect_uri
- **Cause**: Lambda not redeployed with new code
- **Fix**: Redeploy `auth_start` Lambda with updated code

### FRONTEND_URL not set
- **Cause**: Environment variable not configured in Lambda
- **Fix**: Set `FRONTEND_URL` in Lambda environment variables

## 🔐 Security Notes

- ✅ State validation still happens in backend
- ✅ Cookie-based auth remains unchanged
- ✅ No tokens exposed in frontend
- ✅ Frontend just forwards OAuth params to backend
- ✅ All security checks happen in `auth_callback` Lambda

## 📝 Additional Notes

- **Backwards Compatibility**: Old flow will break after Strava settings updated
- **No Database Changes**: No schema or data migrations needed
- **Frontend Deployment**: Automatic via GitHub Actions on push to main
- **Lambda Deployment**: Manual via AWS CLI (see steps above)

## ✨ Ready to Deploy

1. ✅ Code changes committed and tested
2. ⏳ Update Strava application settings
3. ⏳ Deploy `auth_start` Lambda
4. ⏳ Verify `FRONTEND_URL` is set in Lambda
5. ⏳ Deploy frontend (push to main)
6. ⏳ Test OAuth flow end-to-end

---

**Issue Resolved**: You can now use `https://timhibbard.github.io` as the Authorization Callback Domain in Strava! 🎉
