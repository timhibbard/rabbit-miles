# ACTION REQUIRED: Update Strava Authorization Callback Domain

## Critical Step - Do This First!

Before deploying the Lambda functions, you **MUST** update the Strava application settings to allow the API Gateway domain as the OAuth callback destination.

## Instructions

### Step 1: Log in to Strava

1. Go to https://www.strava.com/settings/api
2. Log in with your Strava account

### Step 2: Locate Your Application

Find the RabbitMiles application in your list of API applications.

### Step 3: Update Authorization Callback Domain

1. Find the field labeled **"Authorization Callback Domain"**
2. Change the value to:
   ```
   9zke9jame0.execute-api.us-east-1.amazonaws.com
   ```
3. **Click Save** or **Update Application**

## Important Notes

⚠️ **This step is CRITICAL**  
If you deploy the Lambda functions without updating this setting first, OAuth will fail with "redirect_uri mismatch" errors.

✅ **Order matters**  
Update Strava settings → Deploy Lambda functions → Test

❌ **Do NOT include**  
- `https://` prefix
- `/prod` or any path
- Port numbers
- Trailing slashes

✅ **Just the domain**  
```
9zke9jame0.execute-api.us-east-1.amazonaws.com
```

## Verification

After saving:
1. Refresh the Strava API settings page
2. Confirm the Authorization Callback Domain shows: `9zke9jame0.execute-api.us-east-1.amazonaws.com`
3. Proceed to Lambda deployment (see DEPLOYMENT_CALLBACK_DOMAIN_FIX.md)

## Why This Is Needed

Strava OAuth requires the callback URL domain to be explicitly whitelisted in the application settings for security. The redirect_uri in the OAuth authorization request must use a domain that is listed in the "Authorization Callback Domain" field.

Our Lambda functions now use:
```
redirect_uri=https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/callback
```

For this to work, the domain `9zke9jame0.execute-api.us-east-1.amazonaws.com` must be in the Authorization Callback Domain setting.

## What If I Don't Do This?

If you deploy the Lambda functions without updating Strava settings first, users will see:
- "redirect_uri mismatch" error from Strava
- Unable to complete OAuth flow
- Cannot authenticate with the application

## Next Steps

After completing this step:
1. See `DEPLOYMENT_CALLBACK_DOMAIN_FIX.md` for Lambda deployment instructions
2. Test the OAuth flow with a new user or in incognito mode
3. Verify CloudWatch logs show the correct redirect_uri

## Questions?

If you encounter any issues:
1. Double-check the domain is exactly: `9zke9jame0.execute-api.us-east-1.amazonaws.com`
2. Ensure there are no typos or extra characters
3. Verify you saved/updated the application settings
4. Check CloudWatch logs for "redirect_uri mismatch" errors
