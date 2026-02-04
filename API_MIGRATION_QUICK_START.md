# Quick Start: API Domain Migration

This is a quick reference guide for migrating your API to `api.rabbitmiles.com`. For complete details, see [API_MIGRATION_TO_CUSTOM_DOMAIN.md](API_MIGRATION_TO_CUSTOM_DOMAIN.md).

## Prerequisites
- AWS CLI configured
- Access to AWS Console
- Control over DNS for rabbitmiles.com

## Quick Steps (30-60 minutes)

### 1. Request SSL Certificate (5 minutes)
```bash
# Request certificate in us-east-1
aws acm request-certificate \
  --domain-name api.rabbitmiles.com \
  --validation-method DNS \
  --region us-east-1
```

### 2. Add DNS Validation Record (10-30 minutes)
- Get validation CNAME from ACM console
- Add to your DNS provider
- Wait for certificate status to be "Issued"

### 3. Create Custom Domain in API Gateway (5 minutes)
```bash
# Get certificate ARN
CERT_ARN=$(aws acm list-certificates --region us-east-1 \
  --query 'CertificateSummaryList[?DomainName==`api.rabbitmiles.com`].CertificateArn' \
  --output text)

# Create custom domain
aws apigatewayv2 create-domain-name \
  --domain-name api.rabbitmiles.com \
  --domain-name-configurations CertificateArn=$CERT_ARN \
  --region us-east-1
```

### 4. Create API Mapping (2 minutes)
```bash
# Get API ID
API_ID="9zke9jame0"  # Your API ID

# Map to root (no /prod path - RECOMMENDED)
aws apigatewayv2 create-api-mapping \
  --domain-name api.rabbitmiles.com \
  --api-id $API_ID \
  --stage prod \
  --region us-east-1
```

### 5. Add DNS CNAME Record (5-30 minutes)
```bash
# Get API Gateway domain
APIGW_DOMAIN=$(aws apigatewayv2 get-domain-name \
  --domain-name api.rabbitmiles.com \
  --region us-east-1 \
  --query 'DomainNameConfigurations[0].ApiGatewayDomainName' \
  --output text)

# Add CNAME: api.rabbitmiles.com -> $APIGW_DOMAIN
# (Use Route 53 or your DNS provider)
```

### 6. Update Lambda Environment Variables (5 minutes)
```bash
NEW_API_BASE_URL="https://api.rabbitmiles.com"

# Update auth-start
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-start \
  --environment "Variables={
    API_BASE_URL=$NEW_API_BASE_URL,
    DB_CLUSTER_ARN=<existing>,
    DB_SECRET_ARN=<existing>,
    DB_NAME=postgres,
    STRAVA_CLIENT_ID=<existing>
  }" \
  --region us-east-1

# Repeat for: auth-callback, webhook
```

### 7. Update Frontend (2 minutes)
Update GitHub Actions secret `VITE_API_BASE_URL` to:
```
https://api.rabbitmiles.com
```

Then redeploy frontend.

### 8. Test (5 minutes)
```bash
# Test SSL
curl -I https://api.rabbitmiles.com/me

# Test OAuth flow
# Visit https://rabbitmiles.com and click "Connect with Strava"
```

## Key Decisions

### Remove /prod Path? (RECOMMENDED: Yes)
- **Yes** (recommended): Cleaner URLs, simpler cookies
  - API: `https://api.rabbitmiles.com/auth/start`
  - Lambda API_BASE_URL: `https://api.rabbitmiles.com`
  - API Mapping: No path key

- **No**: Keep existing structure
  - API: `https://api.rabbitmiles.com/prod/auth/start`
  - Lambda API_BASE_URL: `https://api.rabbitmiles.com/prod`
  - API Mapping: Path key = `prod`

## Rollback
If issues occur, update GitHub Actions secret back to:
```
https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod
```

And revert Lambda `API_BASE_URL` variables.

## Cost
**$0** - All AWS services used are free

## Full Documentation
See [API_MIGRATION_TO_CUSTOM_DOMAIN.md](API_MIGRATION_TO_CUSTOM_DOMAIN.md) for:
- Detailed explanations
- Console-based instructions
- Troubleshooting guide
- Cookie path considerations
- Testing procedures
- Webhook updates
