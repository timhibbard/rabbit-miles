# Domain Migration: Quick Action Checklist

This is a condensed checklist for migrating to rabbitmiles.com. For detailed instructions, see [DOMAIN_MIGRATION_GUIDE.md](DOMAIN_MIGRATION_GUIDE.md).

---

## ✅ Part 1: AWS SSL Certificate (ACM) - us-east-1 Region

1. **Request certificate in ACM Console** (must be us-east-1)
   - Domain: `api.rabbitmiles.com`
   - Validation method: DNS
   - **Save the CNAME record** provided for validation

2. **Add DNS validation CNAME record** (see Part 4)

3. **Wait for certificate validation** (5-30 minutes)

---

## ✅ Part 2: API Gateway Custom Domain

1. **Create custom domain name in API Gateway Console** (us-east-1)
   - Domain: `api.rabbitmiles.com`
   - ACM certificate: Select the validated certificate
   - **Note the API Gateway domain name** (e.g., `d-abc123.execute-api.us-east-1.amazonaws.com`)

2. **Create API mapping**
   - API: Select your API
   - Stage: `prod`
   - Path: (leave empty)

---

## ✅ Part 3: GitHub Pages Custom Domain

1. **Repository already has CNAME file** ✅ (committed in this PR)

2. **Configure in GitHub repository settings**
   - Go to: Settings → Pages
   - Custom domain: `rabbitmiles.com`
   - Click Save
   - Wait for DNS check (see Part 4)
   - **Enable "Enforce HTTPS"** once DNS check passes

3. **Wait for GitHub SSL certificate** (10-15 minutes after DNS)

---

## ✅ Part 4: DNS Configuration

Add these records in your DNS provider:

### Required DNS Records

| Type | Name | Value | Notes |
|------|------|-------|-------|
| **A** | `@` | `185.199.108.153` | GitHub Pages (1 of 4) |
| **A** | `@` | `185.199.109.153` | GitHub Pages (2 of 4) |
| **A** | `@` | `185.199.110.153` | GitHub Pages (3 of 4) |
| **A** | `@` | `185.199.111.153` | GitHub Pages (4 of 4) |
| **CNAME** | `www` | `timhibbard.github.io` | WWW subdomain |
| **CNAME** | `api` | `d-abc123.execute-api.us-east-1.amazonaws.com` | **Use YOUR API Gateway domain** |
| **CNAME** | `_abc123.api` | `_xyz789.acm-validations.aws` | **Use YOUR ACM validation CNAME** |

**Important:**
- Replace `d-abc123.execute-api.us-east-1.amazonaws.com` with the actual API Gateway domain from Part 2
- Replace `_abc123.api` and `_xyz789.acm-validations.aws` with the actual ACM validation CNAME from Part 1
- DNS propagation can take 15 minutes to 24 hours (typically < 1 hour)

---

## ✅ Part 5: Update Lambda Environment Variables

Update **ALL** Lambda functions with these two variables:

```bash
# Quick update script for all functions
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
  
  CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --query 'Environment.Variables' \
    --output json)
  
  UPDATED_ENV=$(echo $CURRENT_ENV | jq '. + {
    "API_BASE_URL": "https://api.rabbitmiles.com",
    "FRONTEND_URL": "https://rabbitmiles.com"
  }')
  
  aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment "Variables=$UPDATED_ENV"
done
```

**Or update manually via AWS Console:**
- `API_BASE_URL`: Change to `https://api.rabbitmiles.com`
- `FRONTEND_URL`: Change to `https://rabbitmiles.com`

---

## ✅ Part 6: Strava API Settings

1. **Go to Strava API Settings**
   - URL: https://www.strava.com/settings/api
   - Select your application

2. **Update these fields:**
   - **Website**: `https://rabbitmiles.com`
   - **Authorization Callback Domain**: `api.rabbitmiles.com`
     - **Important**: Domain only, no `https://`, no path

3. **Click "Update"**

---

## ✅ Part 7: Deploy Updated Code

**Code is already updated in this PR** ✅

Files updated:
- `.env.example` → `https://api.rabbitmiles.com`
- `.github/workflows/deploy.yml` → `https://api.rabbitmiles.com`
- `README.md` → New domain references
- `public/CNAME` → `rabbitmiles.com`
- `ENV_VARS.md` → Updated examples
- `.github/copilot-instructions.md` → Updated defaults

**Action Required:**
1. Merge this PR to `main` branch
2. GitHub Actions will automatically deploy the frontend

---

## ✅ Part 8: Testing & Verification

### 8.1 Test DNS Propagation

```bash
# Test apex domain
dig rabbitmiles.com A

# Test www subdomain
dig www.rabbitmiles.com CNAME

# Test API subdomain
dig api.rabbitmiles.com CNAME
```

### 8.2 Test SSL Certificates

```bash
# Test API SSL
curl -v https://api.rabbitmiles.com/me
# Should NOT show SSL errors (401 unauthorized is OK)

# Test frontend SSL
curl -I https://rabbitmiles.com
# Should return 200 and show SSL certificate
```

### 8.3 Test OAuth Flow

1. Go to `https://rabbitmiles.com`
2. Click "Connect with Strava"
3. Authorize on Strava
4. Should redirect back to `https://rabbitmiles.com`
5. Should be logged in successfully
6. No CORS errors in browser console (F12)

### 8.4 Test API Endpoints

1. After logging in, navigate to Dashboard
2. Click "Refresh Activities"
3. Should fetch activities successfully
4. No network errors

---

## 📋 Verification Checklist

Before considering migration complete:

- [ ] ACM certificate shows "Issued" status
- [ ] API Gateway custom domain created and mapped
- [ ] DNS records added (5 A records + 3 CNAMEs)
- [ ] DNS propagation verified (`dig` commands)
- [ ] GitHub Pages custom domain configured
- [ ] GitHub Pages DNS check passes
- [ ] GitHub Pages "Enforce HTTPS" enabled
- [ ] All Lambda environment variables updated (11 functions)
- [ ] Strava API settings updated
- [ ] Code changes merged to `main`
- [ ] Frontend deployed via GitHub Actions
- [ ] `curl https://api.rabbitmiles.com/me` returns proper response (no SSL errors)
- [ ] `https://rabbitmiles.com` loads with valid SSL
- [ ] OAuth flow works end-to-end
- [ ] Can fetch activities from dashboard
- [ ] No CORS errors in browser console

---

## 🔄 Rollback (if needed)

If something goes wrong:

1. **Revert Lambda variables** (see DOMAIN_MIGRATION_GUIDE.md)
2. **Revert Strava settings** to `9zke9jame0.execute-api.us-east-1.amazonaws.com`
3. **Remove GitHub Pages custom domain** in repository settings
4. **Revert the PR** and redeploy

---

## 📚 Additional Resources

- Full guide: [DOMAIN_MIGRATION_GUIDE.md](DOMAIN_MIGRATION_GUIDE.md)
- Environment variables: [ENV_VARS.md](ENV_VARS.md)
- Troubleshooting: See "Troubleshooting" section in DOMAIN_MIGRATION_GUIDE.md

---

## ⏱️ Estimated Timeline

- **ACM certificate validation**: 5-30 minutes
- **DNS propagation**: 15 minutes - 24 hours (typically < 1 hour)
- **GitHub Pages SSL provisioning**: 10-15 minutes after DNS
- **Lambda updates**: 5-10 minutes
- **Total estimated time**: 30 minutes - 2 hours (excluding DNS propagation)

---

## 🆘 Need Help?

If you encounter issues:
1. Check CloudWatch logs for Lambda errors
2. Verify DNS with `dig` commands
3. Check ACM certificate status
4. Review troubleshooting section in DOMAIN_MIGRATION_GUIDE.md
5. Test with `curl -v` to see detailed connection info
