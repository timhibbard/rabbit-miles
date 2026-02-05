# Domain Migration Guide: rabbitmiles.com

This guide walks through migrating RabbitMiles from GitHub Pages default domain to the custom domain `rabbitmiles.com`.

## Overview

- **Frontend**: `https://rabbitmiles.com` (GitHub Pages with custom domain)
- **Backend API**: `https://api.rabbitmiles.com` (API Gateway with custom domain)
- **Current Setup**:
  - Frontend: `https://timhibbard.github.io/rabbit-miles`
  - Backend: `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod`

---

## Prerequisites

- Domain `rabbitmiles.com` registered and accessible in your DNS provider
- AWS CLI configured with appropriate credentials
- GitHub repository admin access
- Strava API application settings access

---

## Part 1: AWS SSL Certificate Setup (ACM)

### Step 1: Request SSL Certificate for API Gateway

1. **Navigate to AWS Certificate Manager (ACM)**
   - **IMPORTANT**: Must be in **us-east-1** region for API Gateway
   - Go to: https://console.aws.amazon.com/acm/home?region=us-east-1

2. **Request a certificate**
   ```bash
   # Using AWS CLI (ensure you're in us-east-1)
   aws acm request-certificate \
     --domain-name api.rabbitmiles.com \
     --validation-method DNS \
     --region us-east-1
   ```

   Or via Console:
   - Click **Request a certificate**
   - Select **Request a public certificate**
   - Enter domain name: `api.rabbitmiles.com`
   - Validation method: **DNS validation**
   - Click **Request**

3. **Get validation CNAME record**
   ```bash
   # Get certificate details
   aws acm describe-certificate \
     --certificate-arn YOUR_CERTIFICATE_ARN \
     --region us-east-1
   ```

   The output will contain a `DomainValidationOptions` section with:
   - `Name`: CNAME record name (e.g., `_abc123.api.rabbitmiles.com`)
   - `Value`: CNAME record value (e.g., `_xyz789.acm-validations.aws`)

4. **Add DNS validation record** (see DNS Configuration section below)

5. **Wait for validation**
   - Can take 5-30 minutes after DNS record is added
   - Certificate status will change from "Pending validation" to "Issued"
   ```bash
   # Check status
   aws acm describe-certificate \
     --certificate-arn YOUR_CERTIFICATE_ARN \
     --region us-east-1 \
     --query 'Certificate.Status'
   ```

---

## Part 2: API Gateway Custom Domain Setup

### Step 1: Create Custom Domain Name

1. **Navigate to API Gateway Console**
   - Go to: https://console.aws.amazon.com/apigateway/main/publish/domain-names?region=us-east-1

2. **Create custom domain name**
   ```bash
   # Using AWS CLI
   aws apigatewayv2 create-domain-name \
     --domain-name api.rabbitmiles.com \
     --domain-name-configurations CertificateArn=YOUR_ACM_CERTIFICATE_ARN \
     --region us-east-1
   ```

   Or via Console:
   - Click **Create**
   - Domain name: `api.rabbitmiles.com`
   - ACM certificate: Select the certificate you created
   - Click **Create domain name**

3. **Note the API Gateway domain name**
   - After creation, you'll see a value like: `d-abc123xyz.execute-api.us-east-1.amazonaws.com`
   - Save this value - you'll need it for DNS configuration

### Step 2: Create API Mapping

Map your API Gateway stage to the custom domain:

```bash
# Find your API ID
aws apigatewayv2 get-apis --region us-east-1

# Create API mapping
aws apigatewayv2 create-api-mapping \
  --domain-name api.rabbitmiles.com \
  --api-id YOUR_API_ID \
  --stage prod \
  --region us-east-1
```

Or via Console:
1. In the custom domain details page, go to **API mappings** tab
2. Click **Configure API mappings**
3. Click **Add new mapping**
4. Select your API
5. Stage: `prod`
6. Path: leave empty (maps to root)
7. Click **Save**

---

## Part 3: DNS Configuration

Add the following DNS records in your domain registrar/DNS provider:

### Required DNS Records

| Type | Name | Value | TTL | Priority |
|------|------|-------|-----|----------|
| **CNAME** | `api` | `d-abc123xyz.execute-api.us-east-1.amazonaws.com` | 300 | - |
| **CNAME** | `www` | `timhibbard.github.io` | 3600 | - |
| **A** | `@` | `185.199.108.153` | 3600 | - |
| **A** | `@` | `185.199.109.153` | 3600 | - |
| **A** | `@` | `185.199.110.153` | 3600 | - |
| **A** | `@` | `185.199.111.153` | 3600 | - |
| **CNAME** | `_abc123.api` | `_xyz789.acm-validations.aws` | 300 | - |

**Notes:**
- Replace `d-abc123xyz.execute-api.us-east-1.amazonaws.com` with your actual API Gateway domain
- Replace `_abc123.api` and `_xyz789.acm-validations.aws` with your actual ACM validation CNAME
- The four A records for `@` are GitHub Pages IPs for apex domain support
- Some DNS providers may require `@` to be replaced with your domain name or left blank

### DNS Configuration Examples

#### Cloudflare
```
Type: CNAME, Name: api, Content: d-abc123xyz.execute-api.us-east-1.amazonaws.com, Proxy: OFF
Type: CNAME, Name: www, Content: timhibbard.github.io, Proxy: OFF
Type: A, Name: @, Content: 185.199.108.153
Type: A, Name: @, Content: 185.199.109.153
Type: A, Name: @, Content: 185.199.110.153
Type: A, Name: @, Content: 185.199.111.153
Type: CNAME, Name: _abc123.api, Content: _xyz789.acm-validations.aws
```

#### Route 53
```bash
# Create hosted zone (if not exists)
aws route53 create-hosted-zone --name rabbitmiles.com --caller-reference $(date +%s)

# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones-by-name --dns-name rabbitmiles.com --query 'HostedZones[0].Id' --output text)

# Create records (use a JSON file for complex records)
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID --change-batch file://dns-records.json
```

---

## Part 4: GitHub Pages Custom Domain Setup

### Step 1: Add CNAME File

Create a file named `CNAME` in the `public/` directory:

```bash
echo "rabbitmiles.com" > public/CNAME
git add public/CNAME
git commit -m "Add CNAME file for custom domain"
git push
```

**Important**: The build process must copy this file to the root of the deployed site.

### Step 2: Configure GitHub Repository Settings

1. Go to repository settings: https://github.com/timhibbard/rabbit-miles/settings/pages
2. Under **Custom domain**, enter: `rabbitmiles.com`
3. Click **Save**
4. Wait for DNS check to pass (may take a few minutes)
5. Once DNS check passes, check **Enforce HTTPS**

### Step 3: Wait for GitHub Pages SSL Certificate

- GitHub will automatically provision a Let's Encrypt SSL certificate
- This can take up to 24 hours but usually completes in 10-15 minutes
- Once complete, `https://rabbitmiles.com` will be accessible

---

## Part 5: Update Lambda Environment Variables

Update environment variables for all Lambda functions:

### Functions to Update

1. `rabbitmiles-auth-start`
2. `rabbitmiles-auth-callback`
3. `rabbitmiles-auth-disconnect`
4. `rabbitmiles-me`
5. `rabbitmiles-get-activities`
6. `rabbitmiles-fetch-activities`
7. `rabbitmiles-webhook`
8. `rabbitmiles-update-activities`
9. `rabbitmiles-match-activity-trail`
10. `rabbitmiles-reset-last-matched`
11. `rabbitmiles-update-trail-data`

### Environment Variables to Update

| Variable | Old Value | New Value |
|----------|-----------|-----------|
| `API_BASE_URL` | `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod` | `https://api.rabbitmiles.com` |
| `FRONTEND_URL` | `https://timhibbard.github.io/rabbit-miles` | `https://rabbitmiles.com` |

### Update Commands

```bash
# Update all Lambda functions with new domain
for FUNCTION_NAME in \
  rabbitmiles-auth-start \
  rabbitmiles-auth-callback \
  rabbitmiles-auth-disconnect \
  rabbitmiles-me \
  rabbitmiles-get-activities \
  rabbitmiles-fetch-activities \
  rabbitmiles-webhook \
  rabbitmiles-update-activities \
  rabbitmiles-match-activity-trail \
  rabbitmiles-reset-last-matched \
  rabbitmiles-update-trail-data
do
  echo "Updating $FUNCTION_NAME..."
  
  # Get current environment variables
  CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --query 'Environment.Variables' \
    --output json)
  
  # Update with new values (replace API_BASE_URL and FRONTEND_URL)
  UPDATED_ENV=$(echo $CURRENT_ENV | jq '. + {
    "API_BASE_URL": "https://api.rabbitmiles.com",
    "FRONTEND_URL": "https://rabbitmiles.com"
  }')
  
  # Apply the update
  aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment "Variables=$UPDATED_ENV"
done
```

Or update individually via Console:
1. Go to Lambda console
2. Select the function
3. Go to **Configuration** → **Environment variables**
4. Click **Edit**
5. Update `API_BASE_URL` and `FRONTEND_URL`
6. Click **Save**

---

## Part 6: Update Strava API Settings

### Step 1: Log into Strava API Settings

1. Go to: https://www.strava.com/settings/api
2. Select your application

### Step 2: Update Settings

Update the following fields:

| Field | Current Value | New Value |
|-------|---------------|-----------|
| **Website** | `https://timhibbard.github.io/rabbit-miles` | `https://rabbitmiles.com` |
| **Authorization Callback Domain** | `9zke9jame0.execute-api.us-east-1.amazonaws.com` | `api.rabbitmiles.com` |

**Important Notes:**
- The Authorization Callback Domain should be **ONLY** `api.rabbitmiles.com` (no protocol, no path)
- Strava will automatically allow callbacks to `https://api.rabbitmiles.com/auth/callback`
- Do not include `/prod` or any other path segments in the callback domain

### Step 3: Verify Callback URL

The full callback URL will be:
```
https://api.rabbitmiles.com/auth/callback
```

Strava will accept this because:
- Domain matches: `api.rabbitmiles.com`
- Path is allowed for the domain
- Protocol is HTTPS (required)

---

## Part 7: Update Repository Configuration

### Update .env.example

```bash
# Update the API base URL
sed -i 's|https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod|https://api.rabbitmiles.com|g' .env.example
```

### Update GitHub Actions Workflow

Update `.github/workflows/deploy.yml`:

```yaml
# Change line 37 from:
VITE_API_BASE_URL: https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod

# To:
VITE_API_BASE_URL: https://api.rabbitmiles.com
```

### Update README

Update any domain references in README.md to use the new domain.

---

## Part 8: Deployment Order

Follow this sequence to minimize downtime:

1. ✅ **Set up DNS records** (can propagate while you work)
2. ✅ **Request and validate ACM certificate** (takes time)
3. ✅ **Create API Gateway custom domain** (once cert is validated)
4. ✅ **Wait for DNS propagation** (15 min - 24 hours, typically < 1 hour)
5. ✅ **Add CNAME file to repository**
6. ✅ **Configure GitHub Pages custom domain**
7. ✅ **Wait for GitHub Pages SSL certificate** (10-15 minutes)
8. ✅ **Update Lambda environment variables**
9. ✅ **Update Strava API settings**
10. ✅ **Update repository config files and deploy**
11. ✅ **Test the application**

---

## Part 9: Testing & Verification

### Test API Gateway Custom Domain

```bash
# Test API is accessible via custom domain
curl -v https://api.rabbitmiles.com/me

# Should receive 401 (not authenticated) or user data if you have a valid session
# Important: Should NOT receive SSL/certificate errors
```

### Test Frontend Custom Domain

1. Visit `https://rabbitmiles.com`
2. Verify:
   - Page loads correctly
   - SSL certificate is valid (lock icon in browser)
   - No mixed content warnings

### Test OAuth Flow

1. Go to `https://rabbitmiles.com`
2. Click "Connect with Strava"
3. Verify:
   - Redirects to Strava authorization page
   - After authorizing, redirects back to `https://rabbitmiles.com`
   - You are successfully logged in
   - No CORS errors in browser console

### Test API Calls

1. Log in to the application
2. Navigate to Dashboard
3. Click "Refresh Activities"
4. Verify:
   - Activities are fetched successfully
   - No network errors
   - No CORS errors in console

---

## Part 10: Rollback Plan

If issues occur, you can rollback:

### Rollback Lambda Environment Variables

```bash
# Restore old values
for FUNCTION_NAME in rabbitmiles-auth-start rabbitmiles-auth-callback rabbitmiles-auth-disconnect rabbitmiles-me; do
  aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment Variables="{
      API_BASE_URL=https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod,
      FRONTEND_URL=https://timhibbard.github.io/rabbit-miles
    }"
done
```

### Rollback Strava API Settings

1. Go to https://www.strava.com/settings/api
2. Change Authorization Callback Domain back to: `9zke9jame0.execute-api.us-east-1.amazonaws.com`

### Rollback GitHub Pages

1. Remove custom domain from repository settings
2. Delete `public/CNAME` file
3. Redeploy

---

## Troubleshooting

### SSL Certificate Not Validating

**Issue**: ACM certificate stuck in "Pending validation"

**Solution**:
1. Verify DNS CNAME record is added correctly
2. Check DNS propagation: `dig _abc123.api.rabbitmiles.com CNAME`
3. Wait up to 30 minutes after adding DNS record
4. Ensure there are no conflicting CAA records

### API Gateway Custom Domain Not Working

**Issue**: `curl https://api.rabbitmiles.com/me` times out or fails

**Solution**:
1. Verify API mapping is created
2. Check DNS CNAME record points to correct API Gateway domain
3. Wait for DNS propagation: `dig api.rabbitmiles.com CNAME`
4. Verify ACM certificate is "Issued" status
5. Check API Gateway stage is deployed

### GitHub Pages Custom Domain Not Working

**Issue**: Domain doesn't load or shows 404

**Solution**:
1. Verify `CNAME` file exists in deployed site root
2. Check A records point to correct GitHub IPs
3. Wait for DNS propagation: `dig rabbitmiles.com A`
4. Ensure GitHub Pages DNS check passes in repository settings
5. Check GitHub Pages build logs for deployment issues

### CORS Errors After Migration

**Issue**: Browser shows CORS errors when calling API

**Solution**:
1. Verify Lambda environment variable `FRONTEND_URL` is updated to `https://rabbitmiles.com`
2. Check Lambda functions include correct CORS headers
3. Ensure API Gateway CORS configuration allows `https://rabbitmiles.com`
4. Clear browser cache and cookies

### Strava OAuth Not Working

**Issue**: OAuth fails with "redirect_uri mismatch"

**Solution**:
1. Verify Strava Authorization Callback Domain is exactly `api.rabbitmiles.com`
2. Check Lambda `API_BASE_URL` is `https://api.rabbitmiles.com`
3. Test the full callback URL: `https://api.rabbitmiles.com/auth/callback`
4. Ensure no trailing slashes in configuration

---

## Post-Migration Checklist

- [ ] ACM certificate shows "Issued" status
- [ ] API Gateway custom domain is created and mapped
- [ ] DNS records are added and propagated
- [ ] `curl https://api.rabbitmiles.com/me` returns proper response (not SSL error)
- [ ] GitHub Pages custom domain is configured
- [ ] `https://rabbitmiles.com` loads correctly with valid SSL
- [ ] All Lambda environment variables are updated
- [ ] Strava API settings are updated
- [ ] OAuth flow works end-to-end
- [ ] No CORS errors in browser console
- [ ] Activities can be fetched and displayed
- [ ] Repository configuration files are updated
- [ ] Documentation is updated

---

## Additional Resources

- [AWS ACM Documentation](https://docs.aws.amazon.com/acm/)
- [API Gateway Custom Domain Names](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-custom-domains.html)
- [GitHub Pages Custom Domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)
- [Strava API Settings](https://developers.strava.com/docs/authentication/)
- [DNS Record Types](https://en.wikipedia.org/wiki/List_of_DNS_record_types)

---

## Support

If you encounter issues not covered in this guide:
1. Check CloudWatch Logs for Lambda functions
2. Review API Gateway execution logs
3. Check browser console for frontend errors
4. Verify DNS propagation with online tools
5. Test API endpoints with curl to isolate frontend vs backend issues
