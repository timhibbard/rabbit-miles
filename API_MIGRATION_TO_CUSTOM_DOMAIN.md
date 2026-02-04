# API Migration to api.rabbitmiles.com

This guide provides step-by-step instructions for migrating your API from the default AWS API Gateway URL to a custom domain `api.rabbitmiles.com`.

## Overview

**Current API URL:**
```
https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod
```

**New API URL:**
```
https://api.rabbitmiles.com
```

## Benefits of Custom API Domain

- **Professional branding**: Clean, memorable URL
- **SSL/TLS included**: AWS-managed certificate for HTTPS
- **Flexibility**: Can change backend infrastructure without changing API URL
- **CORS simplification**: Same root domain as frontend (rabbitmiles.com)

## Prerequisites

- AWS CLI installed and configured
- Access to AWS Console with permissions for:
  - API Gateway
  - AWS Certificate Manager (ACM)
  - Route 53 or your DNS provider
- Domain rabbitmiles.com already set up

---

## Part 1: Create and Validate SSL Certificate

### Step 1.1: Request Certificate in AWS Certificate Manager

1. **Open AWS Certificate Manager Console**
   - Navigate to: https://console.aws.amazon.com/acm/home?region=us-east-1
   - **Important**: Must be in `us-east-1` region for API Gateway custom domains

2. **Request a Certificate**
   ```bash
   # Using AWS CLI (alternative to console)
   aws acm request-certificate \
     --domain-name api.rabbitmiles.com \
     --validation-method DNS \
     --region us-east-1
   ```

   Or in the console:
   - Click "Request a certificate"
   - Choose "Request a public certificate"
   - Click "Next"

3. **Add Domain Name**
   - Domain name: `api.rabbitmiles.com`
   - Click "Next"

4. **Select Validation Method**
   - Choose **DNS validation** (recommended)
   - Click "Next"

5. **Add Tags (Optional)**
   - Key: `Name`, Value: `rabbitmiles-api`
   - Key: `Environment`, Value: `production`
   - Click "Review"

6. **Review and Confirm**
   - Review your settings
   - Click "Confirm and request"

### Step 1.2: Validate Certificate with DNS

1. **Get Validation Record**
   
   After requesting the certificate, AWS will show a CNAME record you need to add to DNS:
   
   ```
   Name: _xxxxxxxxxxxxx.api.rabbitmiles.com
   Type: CNAME
   Value: _yyyyyyyyyyyyy.acm-validations.aws.
   ```

2. **Add DNS Record**
   
   Add this CNAME record to your DNS provider (Route 53, Cloudflare, etc.):

   **Using Route 53:**
   ```bash
   # Get the validation record details first
   CERT_ARN=$(aws acm list-certificates --region us-east-1 \
     --query 'CertificateSummaryList[?DomainName==`api.rabbitmiles.com`].CertificateArn' \
     --output text)
   
   # Describe the certificate to get validation details
   aws acm describe-certificate \
     --certificate-arn $CERT_ARN \
     --region us-east-1 \
     --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
   
   # Add the record to Route 53 (if using Route 53)
   # Get your hosted zone ID first
   ZONE_ID=$(aws route53 list-hosted-zones \
     --query 'HostedZones[?Name==`rabbitmiles.com.`].Id' \
     --output text | cut -d'/' -f3)
   
   # Create the validation record
   # Replace VALIDATION_NAME and VALIDATION_VALUE with values from describe-certificate
   aws route53 change-resource-record-sets \
     --hosted-zone-id $ZONE_ID \
     --change-batch '{
       "Changes": [{
         "Action": "CREATE",
         "ResourceRecordSet": {
           "Name": "VALIDATION_NAME",
           "Type": "CNAME",
           "TTL": 300,
           "ResourceRecords": [{"Value": "VALIDATION_VALUE"}]
         }
       }]
     }'
   ```

   **Using other DNS providers:**
   - Log into your DNS provider (Cloudflare, GoDaddy, etc.)
   - Add a new CNAME record with the exact name and value from ACM
   - TTL: 300 seconds (5 minutes) or default

3. **Wait for Validation**
   - ACM will automatically detect the DNS record
   - Validation usually takes 5-30 minutes
   - Certificate status will change from "Pending validation" to "Issued"

   Check status:
   ```bash
   aws acm describe-certificate \
     --certificate-arn $CERT_ARN \
     --region us-east-1 \
     --query 'Certificate.Status'
   ```

---

## Part 2: Create Custom Domain in API Gateway

### Step 2.1: Create Custom Domain Name

1. **Open API Gateway Console**
   - Navigate to: https://console.aws.amazon.com/apigateway/home?region=us-east-1
   - Select "Custom domain names" from the left menu

2. **Create Custom Domain**

   **Using AWS CLI:**
   ```bash
   # Get your certificate ARN
   CERT_ARN=$(aws acm list-certificates --region us-east-1 \
     --query 'CertificateSummaryList[?DomainName==`api.rabbitmiles.com`].CertificateArn' \
     --output text)
   
   # Create custom domain
   aws apigatewayv2 create-domain-name \
     --domain-name api.rabbitmiles.com \
     --domain-name-configurations CertificateArn=$CERT_ARN \
     --region us-east-1
   ```

   **Using AWS Console:**
   - Click "Create"
   - Domain name: `api.rabbitmiles.com`
   - TLS version: `TLS 1.2` (recommended)
   - Certificate: Select your `api.rabbitmiles.com` certificate from dropdown
   - Click "Create domain name"

3. **Note the API Gateway Domain Name**
   
   After creation, AWS will provide a domain name like:
   ```
   d-xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
   ```
   
   You'll need this for DNS configuration.

   Get it via CLI:
   ```bash
   aws apigatewayv2 get-domain-name \
     --domain-name api.rabbitmiles.com \
     --region us-east-1 \
     --query 'DomainNameConfigurations[0].ApiGatewayDomainName' \
     --output text
   ```

### Step 2.2: Create API Mapping

1. **Get Your API ID and Stage**
   ```bash
   # List your APIs to find the RabbitMiles API
   aws apigatewayv2 get-apis --region us-east-1
   
   # Look for your API, note the ApiId
   # The stage is typically "prod" or "$default"
   API_ID="9zke9jame0"  # Replace with your actual API ID
   STAGE="prod"          # Replace if different
   ```

2. **Create API Mapping**

   This maps your custom domain to your API Gateway API and stage:

   ```bash
   aws apigatewayv2 create-api-mapping \
     --domain-name api.rabbitmiles.com \
     --api-id $API_ID \
     --stage $STAGE \
     --region us-east-1
   ```

   **Important Notes:**
   - If you want paths like `/prod` to be removed, leave the `api-mapping-key` empty
   - Your API will be accessible at `https://api.rabbitmiles.com/` (without `/prod`)
   - To keep `/prod` path, add: `--api-mapping-key prod`

   **Using AWS Console:**
   - Go to Custom Domain Names → api.rabbitmiles.com
   - Click "API mappings" tab
   - Click "Configure API mappings"
   - Click "Add new mapping"
   - API: Select your RabbitMiles API
   - Stage: Select `prod` (or your stage name)
   - Path: Leave empty to map to root, or enter `prod` to keep `/prod` path
   - Click "Save"

---

## Part 3: Configure DNS

### Step 3.1: Create DNS CNAME Record

Point `api.rabbitmiles.com` to your API Gateway domain:

**Using Route 53:**
```bash
# Get your API Gateway domain name
APIGW_DOMAIN=$(aws apigatewayv2 get-domain-name \
  --domain-name api.rabbitmiles.com \
  --region us-east-1 \
  --query 'DomainNameConfigurations[0].ApiGatewayDomainName' \
  --output text)

# Get your hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones \
  --query 'HostedZones[?Name==`rabbitmiles.com.`].Id' \
  --output text | cut -d'/' -f3)

# Create CNAME record
aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"CREATE\",
      \"ResourceRecordSet\": {
        \"Name\": \"api.rabbitmiles.com\",
        \"Type\": \"CNAME\",
        \"TTL\": 300,
        \"ResourceRecords\": [{\"Value\": \"$APIGW_DOMAIN\"}]
      }
    }]
  }"
```

**Using Other DNS Providers:**

Add a CNAME record:
```
Name: api
Type: CNAME
Value: d-xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
TTL: 300 (or your provider's default)
```

### Step 3.2: Wait for DNS Propagation

- DNS propagation typically takes 5-60 minutes
- You can check DNS resolution:

```bash
# Check if DNS is resolving
dig api.rabbitmiles.com

# Or using nslookup
nslookup api.rabbitmiles.com

# Test the endpoint (should get HTTPS response)
curl -I https://api.rabbitmiles.com/me
```

---

## Part 4: Update Lambda Environment Variables

All Lambda functions that use `API_BASE_URL` need to be updated:

### Step 4.1: Update Lambda Functions

**Functions to Update:**
- `rabbitmiles-auth-start`
- `rabbitmiles-auth-callback`
- `rabbitmiles-webhook`

**Update Script:**

```bash
# Define the new API base URL
# Note: If you mapped to root (no path), don't include /prod
NEW_API_BASE_URL="https://api.rabbitmiles.com"

# If you kept the /prod path in API mapping:
# NEW_API_BASE_URL="https://api.rabbitmiles.com/prod"

# Update auth-start
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-start \
  --environment "Variables={
    API_BASE_URL=$NEW_API_BASE_URL,
    DB_CLUSTER_ARN=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-start --query 'Environment.Variables.DB_CLUSTER_ARN' --output text),
    DB_SECRET_ARN=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-start --query 'Environment.Variables.DB_SECRET_ARN' --output text),
    DB_NAME=postgres,
    STRAVA_CLIENT_ID=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-start --query 'Environment.Variables.STRAVA_CLIENT_ID' --output text)
  }" \
  --region us-east-1

# Update auth-callback
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-callback \
  --environment "Variables={
    API_BASE_URL=$NEW_API_BASE_URL,
    FRONTEND_URL=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --query 'Environment.Variables.FRONTEND_URL' --output text),
    DB_CLUSTER_ARN=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --query 'Environment.Variables.DB_CLUSTER_ARN' --output text),
    DB_SECRET_ARN=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --query 'Environment.Variables.DB_SECRET_ARN' --output text),
    DB_NAME=postgres,
    APP_SECRET=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --query 'Environment.Variables.APP_SECRET' --output text),
    STRAVA_CLIENT_ID=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --query 'Environment.Variables.STRAVA_CLIENT_ID' --output text),
    STRAVA_CLIENT_SECRET=$(aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --query 'Environment.Variables.STRAVA_CLIENT_SECRET' --output text)
  }" \
  --region us-east-1

# Update webhook (if using webhooks)
aws lambda update-function-configuration \
  --function-name rabbitmiles-webhook \
  --environment "Variables={
    API_BASE_URL=$NEW_API_BASE_URL,
    $(aws lambda get-function-configuration --function-name rabbitmiles-webhook --query 'Environment.Variables' --output text | grep -v API_BASE_URL)
  }" \
  --region us-east-1
```

**Manual Update (Using AWS Console):**

For each Lambda function:
1. Open Lambda console: https://console.aws.amazon.com/lambda/home?region=us-east-1
2. Select the function
3. Go to "Configuration" → "Environment variables"
4. Click "Edit"
5. Update `API_BASE_URL` from:
   - Old: `https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod`
   - New: `https://api.rabbitmiles.com` (or `https://api.rabbitmiles.com/prod` if you kept path)
6. Click "Save"

### Step 4.2: Verify Lambda Updates

```bash
# Check auth-start
aws lambda get-function-configuration \
  --function-name rabbitmiles-auth-start \
  --query 'Environment.Variables.API_BASE_URL' \
  --region us-east-1

# Check auth-callback
aws lambda get-function-configuration \
  --function-name rabbitmiles-auth-callback \
  --query 'Environment.Variables.API_BASE_URL' \
  --region us-east-1
```

---

## Part 5: Update Frontend Configuration

### Step 5.1: Update GitHub Actions Secret

1. **Go to Repository Settings**
   - Navigate to: https://github.com/timhibbard/rabbit-miles/settings/secrets/actions

2. **Update VITE_API_BASE_URL Secret**
   - Click on `VITE_API_BASE_URL` secret
   - Click "Update secret"
   - New value: `https://api.rabbitmiles.com`
   - Click "Update secret"

### Step 5.2: Update .env.example

Update the example file to reflect the new API URL (this is documentation only):

```env
# Backend API Base URL
# Production: https://api.rabbitmiles.com
# Development: Use your local API or a development API Gateway endpoint
VITE_API_BASE_URL=https://api.rabbitmiles.com
```

### Step 5.3: Redeploy Frontend

After updating the GitHub Actions secret:

```bash
# Trigger a new deployment by pushing to main
# Or manually trigger the workflow from GitHub Actions tab
```

The next deployment will use the new API URL.

---

## Part 6: Update Strava Webhook Configuration (If Using Webhooks)

If you're using Strava webhooks, update the callback URL:

### Step 6.1: Update Webhook Subscription

```bash
# First, get your current webhook subscription ID
SUBSCRIPTION_ID=$(curl -G https://www.strava.com/api/v3/push_subscriptions \
  -d client_id=YOUR_STRAVA_CLIENT_ID \
  -d client_secret=YOUR_STRAVA_CLIENT_SECRET \
  | jq -r '.[0].id')

# Delete old subscription
curl -X DELETE https://www.strava.com/api/v3/push_subscriptions/$SUBSCRIPTION_ID \
  -d client_id=YOUR_STRAVA_CLIENT_ID \
  -d client_secret=YOUR_STRAVA_CLIENT_SECRET

# Create new subscription with updated URL
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -d client_id=YOUR_STRAVA_CLIENT_ID \
  -d client_secret=YOUR_STRAVA_CLIENT_SECRET \
  -d callback_url=https://api.rabbitmiles.com/strava/webhook \
  -d verify_token=YOUR_VERIFY_TOKEN
```

---

## Part 7: Testing and Verification

### Step 7.1: Test SSL Certificate

```bash
# Check SSL certificate
openssl s_client -connect api.rabbitmiles.com:443 -servername api.rabbitmiles.com < /dev/null

# Verify certificate details
curl -vI https://api.rabbitmiles.com/me 2>&1 | grep -A 20 "Server certificate"
```

Expected output should show:
- Certificate for `api.rabbitmiles.com`
- Issued by Amazon
- Valid dates

### Step 7.2: Test API Endpoints

```bash
# Test /me endpoint (should return 401 without auth)
curl -i https://api.rabbitmiles.com/me

# Test CORS headers
curl -i -H "Origin: https://rabbitmiles.com" https://api.rabbitmiles.com/me

# Test OAuth start (should redirect to Strava)
curl -i https://api.rabbitmiles.com/auth/start
```

Expected results:
- All requests return HTTPS responses
- CORS headers include `Access-Control-Allow-Origin: https://rabbitmiles.com`
- OAuth flow redirects properly

### Step 7.3: Test Full OAuth Flow

1. **Open the application**
   ```
   https://rabbitmiles.com
   ```

2. **Click "Connect with Strava"**
   - Should redirect to `https://api.rabbitmiles.com/auth/start`
   - Then to Strava authorization
   - Then back to `https://rabbitmiles.com/connect?connected=1`

3. **Verify in Browser DevTools**
   - Network tab should show requests to `api.rabbitmiles.com`
   - All requests should use HTTPS
   - Cookies should be set properly

### Step 7.4: Monitor CloudWatch Logs

```bash
# Check auth-start logs
aws logs tail /aws/lambda/rabbitmiles-auth-start --follow --region us-east-1

# Check auth-callback logs
aws logs tail /aws/lambda/rabbitmiles-auth-callback --follow --region us-east-1
```

Look for any errors related to the new API URL.

---

## Part 8: Cookie Path Considerations

### Important: Cookie Path Update

The Lambda functions use `COOKIE_PATH` extracted from `API_BASE_URL`:

**Before (with /prod path):**
```python
API_BASE_URL = "https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod"
COOKIE_PATH = "/prod"  # Extracted from URL
```

**After (if mapping to root):**
```python
API_BASE_URL = "https://api.rabbitmiles.com"
COOKIE_PATH = "/"  # No path in URL
```

### Decision Point: Keep /prod or Remove?

**Option A: Remove /prod Path (Recommended)**
- API mapping: No path key
- API_BASE_URL: `https://api.rabbitmiles.com`
- Cookies: Path = `/`
- Endpoints: `https://api.rabbitmiles.com/auth/start`

**Option B: Keep /prod Path**
- API mapping: Path key = `prod`
- API_BASE_URL: `https://api.rabbitmiles.com/prod`
- Cookies: Path = `/prod`
- Endpoints: `https://api.rabbitmiles.com/prod/auth/start`

**Recommendation:** Option A (remove /prod) for cleaner URLs and simpler cookie handling.

If you choose Option A, ensure:
- API mapping has no path key (maps to root)
- Lambda `API_BASE_URL` = `https://api.rabbitmiles.com` (no /prod)
- Frontend `VITE_API_BASE_URL` = `https://api.rabbitmiles.com`

---

## Rollback Plan

If issues occur, you can quickly rollback:

### Step 1: Revert Frontend
```bash
# Update GitHub Actions secret back to old URL
# VITE_API_BASE_URL = https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod

# Redeploy frontend
```

### Step 2: Revert Lambda Environment Variables
```bash
OLD_API_BASE_URL="https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod"

aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-start \
  --environment Variables="{API_BASE_URL=$OLD_API_BASE_URL,...}" \
  --region us-east-1
```

### Step 3: Keep Custom Domain for Future
- Leave the custom domain and certificate in place
- You can retry the migration later without repeating Steps 1-3

---

## Summary Checklist

### AWS Configuration
- [ ] Certificate created in ACM (us-east-1 region)
- [ ] Certificate validated via DNS
- [ ] Custom domain created in API Gateway
- [ ] API mapping configured (decide on path)
- [ ] DNS CNAME record added for api.rabbitmiles.com
- [ ] DNS propagation complete (test with `dig` or `nslookup`)

### Lambda Updates
- [ ] auth-start: API_BASE_URL updated
- [ ] auth-callback: API_BASE_URL updated
- [ ] webhook: API_BASE_URL updated (if applicable)
- [ ] All other lambdas: API_BASE_URL updated if used

### Frontend Updates
- [ ] GitHub Actions secret VITE_API_BASE_URL updated
- [ ] Frontend redeployed with new API URL
- [ ] .env.example updated (documentation)

### Testing
- [ ] SSL certificate validated
- [ ] API endpoints respond via custom domain
- [ ] CORS headers correct
- [ ] OAuth flow works end-to-end
- [ ] Cookies set with correct path
- [ ] No errors in CloudWatch logs

### Optional
- [ ] Strava webhook URL updated (if using webhooks)
- [ ] Documentation updated
- [ ] Old API Gateway URL kept as backup

---

## Cost Implications

**Custom Domain Name:**
- AWS API Gateway custom domain: **$0** (no additional charge)
- AWS Certificate Manager (ACM): **$0** (free for public certificates)
- DNS CNAME record: **$0** (included with Route 53 hosted zone)

**Total additional monthly cost:** $0

The custom domain is free to use with API Gateway and ACM certificates are free for public domains.

---

## Troubleshooting

### Issue: Certificate validation pending
**Solution:** Verify DNS CNAME record is added correctly. Use `dig` to check:
```bash
dig _xxxxx.api.rabbitmiles.com CNAME
```

### Issue: 403 Forbidden from API
**Solution:** Check API mapping is configured correctly. API must be mapped to the custom domain.

### Issue: Cookies not working
**Solution:** Verify `API_BASE_URL` in Lambdas matches the custom domain and includes correct path (or no path if mapping to root).

### Issue: CORS errors
**Solution:** Ensure `FRONTEND_URL` in Lambdas is set to `https://rabbitmiles.com` (no path).

### Issue: SSL certificate error
**Solution:** Ensure certificate is in us-east-1 region and is validated.

---

## Additional Resources

- [AWS API Gateway Custom Domain Names](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-custom-domains.html)
- [AWS Certificate Manager](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html)
- [DNS Validation for ACM](https://docs.aws.amazon.com/acm/latest/userguide/dns-validation.html)

---

## Questions?

If you encounter issues:
1. Check CloudWatch Logs for Lambda functions
2. Verify DNS resolution with `dig api.rabbitmiles.com`
3. Test SSL with `openssl s_client`
4. Check API Gateway access logs
5. Verify environment variables in Lambda console
