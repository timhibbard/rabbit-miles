# Deployment Guide: Authorization Header Removal Fix

## Overview

This deployment updates both frontend and backend to fix the CORS issue preventing new users from connecting to Strava. The changes remove the Authorization header fallback mechanism and ensure strict cookie-based authentication.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js and npm installed for frontend build
- Access to Lambda function deployment (via AWS Console or CLI)

## Deployment Steps

### Step 1: Deploy Backend Changes

Update two Lambda functions with the new code:

#### Option A: Deploy via AWS Console

1. **Update `rabbitmiles-me` Lambda:**
   ```bash
   cd backend/me
   zip -r lambda.zip lambda_function.py
   ```
   - Go to AWS Lambda Console
   - Select `rabbitmiles-me` function
   - Click "Upload from" → ".zip file"
   - Upload `lambda.zip`
   - Click "Deploy"

2. **Update `rabbitmiles-auth-callback` Lambda:**
   ```bash
   cd backend/auth_callback
   zip -r lambda.zip lambda_function.py
   ```
   - Go to AWS Lambda Console
   - Select `rabbitmiles-auth-callback` function
   - Click "Upload from" → ".zip file"
   - Upload `lambda.zip`
   - Click "Deploy"

#### Option B: Deploy via AWS CLI

1. **Update `rabbitmiles-me` Lambda:**
   ```bash
   cd backend/me
   zip -r lambda.zip lambda_function.py
   aws lambda update-function-code \
     --function-name rabbitmiles-me \
     --zip-file fileb://lambda.zip \
     --region us-east-1
   ```

2. **Update `rabbitmiles-auth-callback` Lambda:**
   ```bash
   cd backend/auth_callback
   zip -r lambda.zip lambda_function.py
   aws lambda update-function-code \
     --function-name rabbitmiles-auth-callback \
     --zip-file fileb://lambda.zip \
     --region us-east-1
   ```

### Step 2: Deploy Frontend Changes

1. **Build the frontend:**
   ```bash
   npm run build
   ```

2. **Deploy to GitHub Pages:**
   ```bash
   # The dist/ folder contains the built files
   # Commit and push to trigger GitHub Pages deployment
   git add dist/
   git commit -m "Deploy frontend with authorization header fix"
   git push origin main
   ```

   Or if using a separate gh-pages branch:
   ```bash
   # Deploy dist/ contents to gh-pages branch
   npm run deploy  # if configured in package.json
   ```

### Step 3: Verify Deployment

#### Backend Verification

1. **Check Lambda versions:**
   ```bash
   aws lambda get-function --function-name rabbitmiles-me --region us-east-1
   aws lambda get-function --function-name rabbitmiles-auth-callback --region us-east-1
   ```

2. **Check CloudWatch Logs:**
   ```bash
   aws logs tail /aws/lambda/rabbitmiles-me --follow --region us-east-1
   ```

#### Frontend Verification

1. **Clear browser cache and cookies**
   - Open DevTools (F12)
   - Right-click the refresh button
   - Select "Empty Cache and Hard Reload"

2. **Verify build artifacts:**
   - Check that `dist/` folder contains new build with updated hashes
   - Verify GitHub Pages is serving the new version

## Testing Checklist

### Test Case 1: New User Connection
- [ ] Clear all cookies for the site
- [ ] Visit the connect page
- [ ] Click "Connect with Strava"
- [ ] Authorize on Strava
- [ ] Verify redirect back to frontend works
- [ ] Verify you see "You're Connected!" message
- [ ] Check browser console for errors (should be clean)
- [ ] Check CloudWatch logs for `/me` Lambda
  - Should see: `Debug - cookie names in array: rm_session`
  - Should see: `Found session token`
  - Should see: `Verified session for athlete_id: {id}`
  - Should NOT see: `Warning: Authorization header detected`

### Test Case 2: Existing User Still Works
- [ ] User who was already connected can access dashboard
- [ ] User data loads correctly
- [ ] Activities are displayed
- [ ] No console errors

### Test Case 3: Disconnect and Reconnect
- [ ] Existing user can disconnect
- [ ] Cookies are cleared (check Application tab in DevTools)
- [ ] User can reconnect successfully
- [ ] Dashboard loads correctly after reconnect

### Test Case 4: Cookie Debugging
Enable debug mode by adding `?debug=1` to the URL:
- [ ] Visit `https://timhibbard.github.io/rabbit-miles/connect?debug=1`
- [ ] Should see debug banner at top
- [ ] Console should show detailed API request/response logs
- [ ] Should NOT see "Added Authorization header from sessionStorage"
- [ ] Should see "With Credentials: true"

## Rollback Plan

If issues are encountered:

### Backend Rollback
1. Use AWS Lambda Console to restore previous version:
   - Go to Lambda function
   - Click "Versions" tab
   - Select previous version
   - Click "Actions" → "Publish new version"

### Frontend Rollback
1. Revert the commit:
   ```bash
   git revert HEAD
   git push origin main
   ```

## Monitoring

### Key Metrics to Watch

1. **CloudWatch Logs for `/me` Lambda:**
   - Filter for: `"No session cookie found"`
   - Should decrease for legitimate users
   - May still appear for unauthorized access attempts

2. **CloudWatch Logs for `/auth/callback` Lambda:**
   - Filter for: `"Successfully upserted user"`
   - Should increase with successful new user connections

3. **Error Rates:**
   - 401 errors should decrease
   - 500 errors should remain at zero

### Sample CloudWatch Insights Queries

**Count authentication attempts:**
```
fields @timestamp, @message
| filter @message like /Found session token|No session cookie found/
| stats count() by @message
```

**Track new user connections:**
```
fields @timestamp, @message
| filter @message like /Successfully upserted user/
| stats count() by bin(1h)
```

## Common Issues and Solutions

### Issue: CORS errors still appearing
**Symptom:** Browser shows CORS policy errors
**Solution:** 
- Verify API Gateway CORS settings include:
  - `Access-Control-Allow-Origin`: Frontend URL
  - `Access-Control-Allow-Credentials`: true
- Check that OPTIONS method is enabled on routes

### Issue: Cookies not being set
**Symptom:** Lambda logs show "No session cookie found" for all requests
**Solution:**
- Verify `SameSite=None` is set (required for cross-site cookies)
- Verify `Secure` flag is set (required with SameSite=None)
- Check that frontend uses HTTPS (required for Secure cookies)
- Verify `COOKIE_PATH` matches API Gateway stage path

### Issue: Existing users can't access dashboard
**Symptom:** Users who were connected before the update get 401 errors
**Solution:**
- This is expected - old session tokens in sessionStorage are no longer used
- Users need to disconnect and reconnect
- Or wait for existing cookies to be used (if they have them)

## Post-Deployment Communication

Notify users that:
1. Some users may need to reconnect their Strava account
2. The fix improves security by removing token storage
3. Authentication is now more reliable across all browsers

## Success Criteria

✅ New users can successfully connect to Strava without errors
✅ Existing users maintain their connections
✅ No CORS errors in browser console
✅ CloudWatch logs show proper cookie detection
✅ No Authorization header warnings in logs

## Support

For issues during deployment:
- Check CloudWatch Logs: `/aws/lambda/rabbitmiles-me` and `/aws/lambda/rabbitmiles-auth-callback`
- Review browser console for frontend errors
- Check Network tab in DevTools to inspect request/response headers
- Enable debug mode with `?debug=1` for detailed logging
