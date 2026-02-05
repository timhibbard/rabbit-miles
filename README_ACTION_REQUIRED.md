# ACTION REQUIRED: Fix CORS Error

## The Problem
Your application frontend successfully migrated to `https://rabbitmiles.com`, but users are getting this error when viewing activities:

```
Access to XMLHttpRequest at 'https://api.rabbitmiles.com/activities/363' from origin 'https://rabbitmiles.com' 
has been blocked by CORS policy: The 'Access-Control-Allow-Origin' header has a value 
'https://timhibbard.github.io' that is not equal to the supplied origin.
```

## Why This Happens
Your Lambda functions use the `FRONTEND_URL` environment variable to set CORS headers. They're currently configured with the old domain, so they return:
- `Access-Control-Allow-Origin: https://timhibbard.github.io`

But your frontend now sends:
- `Origin: https://rabbitmiles.com`

The browser sees these don't match and blocks the request.

## The Solution
Update the `FRONTEND_URL` environment variable in your Lambda functions.

### ⚡ Quick Fix (5 minutes)

**Step 1:** Make sure you have the AWS CLI configured with credentials that can update Lambda functions.

```bash
aws sts get-caller-identity  # Verify your AWS access
```

**Step 2:** Install `jq` if you don't have it (for JSON processing):
```bash
# Mac
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Or check if already installed
jq --version
```

**Step 3:** Run the update script:
```bash
cd scripts
./update-lambda-frontend-url.sh
```

**Step 4:** Verify it worked:
```bash
# This should return: Access-Control-Allow-Origin: https://rabbitmiles.com
curl -i -H "Origin: https://rabbitmiles.com" https://api.rabbitmiles.com/me
```

**Step 5:** Test in your browser - visit any activity page and the error should be gone!

### 📋 What the Script Does
Updates `FRONTEND_URL` in these 8 Lambda functions:
- rabbitmiles-auth-start
- rabbitmiles-auth-callback
- rabbitmiles-auth-disconnect
- rabbitmiles-me
- rabbitmiles-get-activities
- rabbitmiles-get-activity-detail ← **This is the one failing**
- rabbitmiles-fetch-activities
- rabbitmiles-reset-last-matched

It preserves all other environment variables (DB credentials, secrets, etc.) and only changes `FRONTEND_URL`.

### 🔧 Alternative: Manual Fix
If you prefer not to run the script, you can update each Lambda manually through the AWS Console:

1. Go to AWS Lambda Console
2. For each function listed above:
   - Click the function name
   - Go to **Configuration** → **Environment variables**
   - Click **Edit**
   - Change `FRONTEND_URL` value to: `https://rabbitmiles.com`
   - Click **Save**

### 📚 More Information
- **Quick reference**: [QUICKFIX_CORS.md](./QUICKFIX_CORS.md)
- **Detailed docs**: [CORS_DOMAIN_FIX.md](./CORS_DOMAIN_FIX.md)
- **Technical details**: [FIX_SUMMARY_ACTIVITY_CORS.md](./FIX_SUMMARY_ACTIVITY_CORS.md)

### ❓ Questions?
This PR only provides the fix script and documentation. No code changes are needed - the Lambda functions already handle CORS correctly. You just need to run the script to update the configuration in AWS.
