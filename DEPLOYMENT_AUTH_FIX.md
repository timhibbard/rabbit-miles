# Deployment Instructions for Authentication Fix

## Overview

This fix addresses authentication failures across all browsers (Desktop, Mobile, Chrome, Safari) by removing the incompatible `Partitioned` cookie attribute from all authentication Lambda functions.

## Files Changed

1. `backend/auth_callback/lambda_function.py` - Session cookie setting
2. `backend/auth_start/lambda_function.py` - OAuth state cookie setting
3. `backend/auth_disconnect/lambda_function.py` - Cookie clearing

## Prerequisites

- AWS CLI configured with appropriate credentials
- Access to Lambda functions in AWS account
- Function names for the three auth Lambdas

## Deployment Steps

### Step 1: Navigate to Backend Directory

```bash
cd backend
```

### Step 2: Deploy auth_start Lambda

```bash
cd auth_start
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-start \
  --zip-file fileb://function.zip
cd ..
```

**Expected output:**
```json
{
    "FunctionName": "rabbitmiles-auth-start",
    "LastModified": "2024-...",
    "RevisionId": "...",
    "State": "Active"
}
```

### Step 3: Deploy auth_callback Lambda

```bash
cd auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-callback \
  --zip-file fileb://function.zip
cd ..
```

### Step 4: Deploy auth_disconnect Lambda

```bash
cd auth_disconnect
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-auth-disconnect \
  --zip-file fileb://function.zip
cd ..
```

## Verification Steps

### 1. Check Lambda Deployment

Verify each Lambda was updated:

```bash
aws lambda get-function --function-name rabbitmiles-auth-start --query 'Configuration.[FunctionName,LastModified,State]'
aws lambda get-function --function-name rabbitmiles-auth-callback --query 'Configuration.[FunctionName,LastModified,State]'
aws lambda get-function --function-name rabbitmiles-auth-disconnect --query 'Configuration.[FunctionName,LastModified,State]'
```

### 2. Monitor CloudWatch Logs

Open CloudWatch log streams to watch for activity:

```bash
# Watch auth_callback logs
aws logs tail /aws/lambda/rabbitmiles-auth-callback --follow
```

### 3. Test Authentication Flow

#### Desktop Browser Test (Chrome/Safari/Firefox)
1. Open browser in private/incognito mode
2. Navigate to: `https://timhibbard.github.io/rabbit-miles`
3. Click "Connect with Strava"
4. Authorize on Strava
5. **Expected**: Redirected to dashboard with profile visible
6. **Check**: Activities should load
7. **Test disconnect**: Click disconnect and verify it works

#### Mobile Safari Test (iPhone/iPad) - CRITICAL
1. Open Safari on iOS device
2. Clear cookies: Settings → Safari → Clear History and Website Data
3. Navigate to: `https://timhibbard.github.io/rabbit-miles`
4. Click "Connect with Strava"
5. Authorize on Strava
6. **Expected**: Redirected to dashboard with profile visible
7. **Previously**: Stayed on connect page (this should now be fixed)
8. **Test disconnect**: Should work now

### 4. Verify Cookies in Browser DevTools

After successful login:
1. Open DevTools (F12)
2. Go to Application → Cookies
3. Check for `rm_session` cookie on API domain
4. Verify attributes:
   - ✅ HttpOnly: true
   - ✅ Secure: true
   - ✅ SameSite: None
   - ✅ Path: /prod (or appropriate path)
   - ❌ **NO** Partitioned attribute

## Troubleshooting

### If Authentication Still Fails

1. **Check CloudWatch logs** for errors:
   ```bash
   aws logs tail /aws/lambda/rabbitmiles-auth-callback --follow
   ```
   Look for:
   - "Created session token for athlete_id: XXXXX"
   - "Successfully upserted user XXXXX to database"
   - Any error messages

2. **Verify environment variables** are set correctly:
   ```bash
   aws lambda get-function-configuration --function-name rabbitmiles-auth-callback \
     --query 'Environment.Variables'
   ```
   Required variables:
   - DB_CLUSTER_ARN
   - DB_SECRET_ARN
   - DB_NAME
   - API_BASE_URL
   - FRONTEND_URL
   - APP_SECRET
   - STRAVA_CLIENT_ID
   - STRAVA_CLIENT_SECRET

3. **Check browser console** for errors:
   - Open DevTools → Console
   - Look for 401 errors or cookie-related issues

4. **Test with curl** to isolate frontend vs backend issues:
   ```bash
   # Test /me endpoint (should return 401 without cookie)
   curl -i https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/me
   ```

### Common Issues

**Issue**: 401 Unauthorized on /me endpoint
- **Cause**: Cookie not being sent or invalid
- **Fix**: Clear browser cookies and re-authenticate

**Issue**: 500 Internal Server Error
- **Cause**: Database connection or configuration issue
- **Fix**: Check CloudWatch logs for specific error

**Issue**: Redirect loop
- **Cause**: Cookie domain mismatch
- **Fix**: Verify FRONTEND_URL environment variable

## Rollback Procedure

If the fix doesn't work or causes new issues:

```bash
# List previous versions
aws lambda list-versions-by-function --function-name rabbitmiles-auth-start

# Revert to previous version (replace N with version number)
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-start \
  --revert-to-version N

aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-callback \
  --revert-to-version N

aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-disconnect \
  --revert-to-version N
```

## Success Criteria

✅ Users can connect with Strava on all browsers  
✅ Dashboard loads with user profile after OAuth  
✅ Activities are displayed correctly  
✅ Disconnect functionality works  
✅ Mobile Safari authentication works (iPhone/iPad)  
✅ No console errors or 401 responses  
✅ Cookies set without `Partitioned` attribute  

## Notes

- **No database changes** required - this is purely a Lambda code update
- **No frontend changes** required - all changes are backend only
- **Immediate effect** - changes take effect as soon as Lambdas are deployed
- **Safe to deploy** - code review and security scan completed with no issues

## Support

If issues persist after deployment:
1. Review `FIX_SUMMARY_PARTITIONED_COOKIE.md` for detailed analysis
2. Check `TROUBLESHOOTING_AUTH.md` for authentication debugging
3. Verify all environment variables are correctly set
4. Monitor CloudWatch logs during testing
5. Test on multiple browsers and devices

## Timeline

- **Development**: Completed
- **Code Review**: ✅ Passed (no issues)
- **Security Scan**: ✅ Passed (no vulnerabilities)
- **Testing**: Manual testing required after deployment
- **Deployment**: Ready to deploy
