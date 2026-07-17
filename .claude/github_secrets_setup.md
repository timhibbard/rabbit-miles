# GitHub Secrets Setup for Email Notifications

## Overview

The GitHub Actions workflows deploy Lambda functions automatically when code is pushed to `main`. The new email notification Lambdas need additional secrets configured.

---

## Required GitHub Secrets

Go to: **GitHub Repository → Settings → Secrets and variables → Actions → Repository secrets**

### 🔧 Existing Secrets (Already Configured)

These should already be set up:

```bash
AWS_ACCESS_KEY_ID          # AWS IAM access key for deployments
AWS_SECRET_ACCESS_KEY      # AWS IAM secret key for deployments
AWS_REGION                 # AWS region (e.g., us-east-1)
```

---

## 🆕 New Secrets for Email Notifications

Add these three new secrets:

### 1. LAMBDA_VERIFY_EMAIL

**Value:** Your Lambda function name for email verification

**Example:**
```
rabbitmiles-verify-email
```

**How to find it:**
- AWS Console → Lambda → Functions
- Look for the function you created for email verification
- Copy the exact function name

---

### 2. LAMBDA_SEND_EMAIL_NOTIFICATION

**Value:** Your Lambda function name for sending emails

**Example:**
```
rabbitmiles-send-email-notification
```

**How to find it:**
- AWS Console → Lambda → Functions
- Look for the function you created for processing the SQS queue
- Copy the exact function name

---

### 3. LAMBDA_HANDLE_EMAIL_BOUNCES

**Value:** Your Lambda function name for handling bounces

**Example:**
```
rabbitmiles-handle-email-bounces
```

**How to find it:**
- AWS Console → Lambda → Functions
- Look for the function you created for handling SNS bounce notifications
- Copy the exact function name

---

## 📝 Step-by-Step: Adding Secrets

### Via GitHub Web UI

1. Go to your repository: `https://github.com/YOUR_USERNAME/rabbit-miles`
2. Click **Settings** tab
3. Click **Secrets and variables** → **Actions** (left sidebar)
4. Click **New repository secret** button
5. Enter secret name (e.g., `LAMBDA_VERIFY_EMAIL`)
6. Enter secret value (your Lambda function name)
7. Click **Add secret**
8. Repeat for all three secrets

### Via GitHub CLI (Optional)

```bash
# Install GitHub CLI if needed: https://cli.github.com/

# Authenticate
gh auth login

# Add secrets
gh secret set LAMBDA_VERIFY_EMAIL -b "rabbitmiles-verify-email"
gh secret set LAMBDA_SEND_EMAIL_NOTIFICATION -b "rabbitmiles-send-email-notification"
gh secret set LAMBDA_HANDLE_EMAIL_BOUNCES -b "rabbitmiles-handle-email-bounces"
```

---

## 🔍 How GitHub Actions Use These Secrets

The `deploy-lambdas.yml` workflow uses the matrix strategy to deploy multiple Lambdas:

```yaml
- name: verify_email
  secret: LAMBDA_VERIFY_EMAIL
  needs_utils: true
- name: send_email_notification
  secret: LAMBDA_SEND_EMAIL_NOTIFICATION
- name: handle_email_bounces
  secret: LAMBDA_HANDLE_EMAIL_BOUNCES
```

For each Lambda:
1. Checks out code
2. Packages `lambda_function.py` into `function.zip`
3. Includes dependencies (e.g., `admin_utils.py` if `needs_utils: true`)
4. Deploys to AWS Lambda using function name from secret

**Deployment command:**
```bash
aws lambda update-function-code \
  --function-name ${{ secrets.LAMBDA_VERIFY_EMAIL }} \
  --zip-file fileb://backend/verify_email/function.zip
```

---

## ✅ Verification

After adding secrets, trigger a deployment:

### Option 1: Push to Main

```bash
# Make a small change to trigger deployment
git commit --allow-empty -m "Trigger Lambda deployment"
git push origin main
```

### Option 2: Manual Workflow Dispatch

1. Go to **Actions** tab in GitHub
2. Click **Deploy Lambda Functions** workflow
3. Click **Run workflow** dropdown
4. Select `main` branch
5. Click **Run workflow**

### Check Deployment Status

1. **Actions tab** → Click the running workflow
2. Expand each Lambda job to see logs
3. Verify all 3 new Lambdas deploy successfully:
   - ✅ Deploy verify_email Lambda
   - ✅ Deploy send_email_notification Lambda  
   - ✅ Deploy handle_email_bounces Lambda

### Verify in AWS

After GitHub Actions completes:

```bash
# Check Lambda function code was updated (recent LastModified time)
aws lambda get-function --function-name rabbitmiles-verify-email
aws lambda get-function --function-name rabbitmiles-send-email-notification
aws lambda get-function --function-name rabbitmiles-handle-email-bounces
```

---

## 🚨 Troubleshooting

### "Function not found" Error

**Symptom:** GitHub Actions fails with `ResourceNotFoundException`

**Fix:**
1. Verify Lambda function exists in AWS Console
2. Check secret value matches exact function name (case-sensitive)
3. Verify AWS credentials have permission to update Lambda

### "Access Denied" Error

**Symptom:** GitHub Actions fails with `AccessDeniedException`

**Fix:** IAM user needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction"
      ],
      "Resource": [
        "arn:aws:lambda:REGION:ACCOUNT:function:rabbitmiles-*"
      ]
    }
  ]
}
```

### Deployment Succeeds but Lambda Not Updated

**Symptom:** GitHub Actions succeeds but Lambda still has old code

**Fix:**
1. Check if secret points to correct function
2. Verify function name doesn't have typos
3. Try manual deployment to confirm:
   ```bash
   cd backend/verify_email
   zip -r function.zip lambda_function.py
   aws lambda update-function-code \
     --function-name rabbitmiles-verify-email \
     --zip-file fileb://function.zip
   ```

---

## 📋 Complete Secrets Checklist

Before deploying, verify all these secrets are set:

**AWS Credentials:**
- ✅ `AWS_ACCESS_KEY_ID`
- ✅ `AWS_SECRET_ACCESS_KEY`
- ✅ `AWS_REGION`

**Existing Lambda Functions:**
- ✅ `LAMBDA_AUTH_START_NAME`
- ✅ `LAMBDA_AUTH_CALLBACK_NAME`
- ✅ `LAMBDA_AUTH_DISCONNECT_NAME`
- ✅ `LAMBDA_ME_NAME`
- ✅ `LAMBDA_GET_ACTIVITIES`
- ✅ `LAMBDA_GET_ACTIVITY_DETAIL`
- ✅ `LAMBDA_FETCH_ACTIVITIES`
- ✅ `LAMBDA_WEBHOOK`
- ✅ `LAMBDA_WEBHOOK_PROCESSOR`
- ✅ `LAMBDA_RESET_LAST_MATCHED`
- ✅ `LAMBDA_UPDATE_TRAIL_DATA`
- ✅ `LAMBDA_UPDATE_ACTIVITIES`
- ✅ `LAMBDA_MATCH_ACTIVITY_TRAIL`
- ✅ `LAMBDA_MATCH_UNMATCHED_ACTIVITIES`
- ✅ `LAMBDA_ADMIN_LIST_USERS`
- ✅ `LAMBDA_ADMIN_USER_ACTIVITIES`
- ✅ `LAMBDA_ADMIN_DELETE_USER`
- ✅ `LAMBDA_ADMIN_BACKFILL_ACTIVITIES`
- ✅ `LAMBDA_ADMIN_ALL_ACTIVITIES`
- ✅ `LAMBDA_BACKFILL_ATHLETE_COUNT`
- ✅ `LAMBDA_SCHEDULED_ACTIVITY_UPDATE`
- ✅ `LAMBDA_ADMIN_UPDATE_ACTIVITIES`
- ✅ `LAMBDA_USER_UPDATE_ACTIVITIES`
- ✅ `LAMBDA_STATS_PERIOD_SUMMARY`
- ✅ `LAMBDA_LEADERBOARD_GET`
- ✅ `LAMBDA_LEADERBOARD_USER_CONTRIB`
- ✅ `LAMBDA_UPDATE_USER_SETTINGS`
- ✅ `LAMBDA_ADMIN_RECALCULATE_LEADERBOARD`

**New Lambda Functions (ADD THESE):**
- 🆕 `LAMBDA_VERIFY_EMAIL`
- 🆕 `LAMBDA_SEND_EMAIL_NOTIFICATION`
- 🆕 `LAMBDA_HANDLE_EMAIL_BOUNCES`

**Frontend:**
- ✅ `VITE_API_BASE_URL` (optional, defaults to `https://api.rabbitmiles.com`)
- ✅ `VITE_GA_MEASUREMENT_ID` (optional, for Google Analytics)

---

## 🎯 Next Steps After Adding Secrets

1. ✅ Add 3 new secrets to GitHub
2. ✅ Push updated workflow to main (already done)
3. ✅ Verify deployment succeeds in Actions tab
4. ✅ Verify Lambdas updated in AWS Console
5. ✅ Continue with AWS infrastructure setup (SQS, SNS, SES)
6. ✅ Test email notification flow

---

## 📚 Related Documentation

- **Deployment Guide:** `.claude/email_notifications_deployment_guide.md`
- **Implementation Details:** `.claude/email_notifications_implementation.md`
- **GitHub Actions Workflow:** `.github/workflows/deploy-lambdas.yml`
