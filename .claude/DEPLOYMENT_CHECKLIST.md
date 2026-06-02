# 📋 Email Notifications Deployment Checklist

Quick reference for deploying the email notifications feature.

---

## ✅ Pre-Deployment (Already Complete)

- [x] Database migrations 012, 013, 014 run
- [x] Backend Lambda code written
- [x] GitHub Actions workflow updated

---

## 🚀 Deployment Steps

### Step 1: GitHub Secrets (5 minutes)

**Add these 3 secrets** at: `GitHub → Settings → Secrets → Actions`

| Secret Name | Value | Example |
|-------------|-------|---------|
| `LAMBDA_VERIFY_EMAIL` | Your Lambda function name | `rabbitmiles-verify-email` |
| `LAMBDA_SEND_EMAIL_NOTIFICATION` | Your Lambda function name | `rabbitmiles-send-email-notification` |
| `LAMBDA_HANDLE_EMAIL_BOUNCES` | Your Lambda function name | `rabbitmiles-handle-email-bounces` |

📖 **Detailed instructions:** `.claude/github_secrets_setup.md`

---

### Step 2: Create Lambda Functions in AWS (15 minutes)

Create these 3 Lambda functions in AWS Console:

#### A. verify_email

```
Name: rabbitmiles-verify-email
Runtime: Python 3.12
Handler: lambda_function.handler
Memory: 256 MB
Timeout: 30 seconds
```

**Environment variables:**
```
DB_CLUSTER_ARN=arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER
DB_SECRET_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET
DB_NAME=postgres
APP_SECRET=your-app-secret
FRONTEND_URL=https://rabbitmiles.com
FROM_EMAIL=notifications@rabbitmiles.com
```

**IAM Role:** Attach policy with RDS Data API, Secrets Manager, and SES permissions

**API Gateway:** Add routes:
- `POST /verify-email/send`
- `GET /verify-email`

#### B. send_email_notification

```
Name: rabbitmiles-send-email-notification
Runtime: Python 3.12
Handler: lambda_function.handler
Memory: 256 MB
Timeout: 60 seconds
```

**Environment variables:**
```
DB_CLUSTER_ARN=arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER
DB_SECRET_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET
DB_NAME=postgres
APP_SECRET=your-app-secret
FROM_EMAIL=notifications@rabbitmiles.com
FRONTEND_URL=https://rabbitmiles.com
SES_CONFIG_SET=rabbitmiles-notifications
```

**IAM Role:** Attach policy with RDS Data API, Secrets Manager, SQS, and SES permissions

**Trigger:** SQS (configured in Step 3)

#### C. handle_email_bounces

```
Name: rabbitmiles-handle-email-bounces
Runtime: Python 3.12
Handler: lambda_function.handler
Memory: 128 MB
Timeout: 30 seconds
```

**Environment variables:**
```
DB_CLUSTER_ARN=arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER
DB_SECRET_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET
DB_NAME=postgres
```

**IAM Role:** Attach policy with RDS Data API and Secrets Manager permissions

**Trigger:** SNS (configured in Step 3)

---

### Step 3: AWS Infrastructure Setup (10 minutes)

**Run the setup script:**

```bash
cd backend/scripts
./setup_email_infrastructure.sh
```

**What it creates:**
- SQS queue: `rabbitmiles-email-notifications`
- SNS topic: `rabbitmiles-ses-bounces`
- SES configuration set: `rabbitmiles-notifications`

**After script completes:**

1. Configure SQS trigger on `send_email_notification` Lambda:
   - Trigger: SQS
   - Queue: `rabbitmiles-email-notifications`
   - Batch size: 10

2. Subscribe `handle_email_bounces` Lambda to SNS topic (instructions printed by script)

---

### Step 4: Update Existing Lambdas (5 minutes)

#### A. Update match_activity_trail

**Add environment variables:**
```
EMAIL_QUEUE_URL=https://sqs.REGION.amazonaws.com/ACCOUNT/rabbitmiles-email-notifications
FRONTEND_URL=https://rabbitmiles.com
```

**Add IAM permission:** `sqs:SendMessage` on queue ARN

#### B. Verify update_user_settings is deployed

(Already updated in code, GitHub Actions will deploy it)

---

### Step 5: Deploy via GitHub Actions (2 minutes)

```bash
# Trigger deployment
git commit --allow-empty -m "Deploy email notification Lambdas"
git push origin main
```

**Monitor:** GitHub → Actions tab → "Deploy Lambda Functions"

**Verify all deploy:**
- ✅ verify_email
- ✅ send_email_notification
- ✅ handle_email_bounces
- ✅ update_user_settings (updated)
- ✅ match_activity_trail (updated)

---

### Step 6: SES Setup (5 minutes + 24 hours approval)

#### A. Verify Domain

1. AWS Console → SES → Verified identities → Create identity
2. Domain: `rabbitmiles.com`
3. Enable DKIM
4. Copy 3 CNAME records
5. Add to DNS (Route 53 or domain registrar)
6. Wait 5-10 minutes for verification

#### B. Request Production Access

1. AWS Console → SES → Account dashboard
2. "Request production access"
3. Fill out form (see deployment guide for details)
4. Wait ~24 hours for approval

#### C. Test in Sandbox (While Waiting)

1. Verify your personal email:
   ```bash
   aws sesv2 create-email-identity --email-identity your@email.com
   ```
2. Click verification link in email
3. Test with your email (see Testing section)

---

## 🧪 Testing

### Quick Test (Sandbox Mode)

```bash
# 1. Set your verified email
curl -X PATCH https://api.rabbitmiles.com/user/settings \
  -H "Cookie: session=YOUR_SESSION" \
  -d '{"email": "your-verified@email.com"}'

# 2. Send verification email
curl -X POST https://api.rabbitmiles.com/verify-email/send \
  -H "Cookie: session=YOUR_SESSION"

# 3. Click link in email

# 4. Enable notifications
curl -X PATCH https://api.rabbitmiles.com/user/settings \
  -H "Cookie: session=YOUR_SESSION" \
  -d '{"email_notifications_enabled": true}'

# 5. Complete a trail activity on Strava
# 6. Check email inbox!
```

### Full Test Checklist

- [ ] Email verification flow works
- [ ] Trail milestone email received (3+ miles)
- [ ] Ranking change email received
- [ ] Duplicate notifications prevented
- [ ] Historical activities don't send emails
- [ ] Bounce handling works
- [ ] Complaint handling works

---

## 📊 Monitoring

### CloudWatch Logs

Check these Lambda logs:
- `/aws/lambda/rabbitmiles-verify-email`
- `/aws/lambda/rabbitmiles-send-email-notification`
- `/aws/lambda/rabbitmiles-handle-email-bounces`
- `/aws/lambda/rabbitmiles-match-activity-trail`

### SQS Queue

Monitor: AWS Console → SQS → `rabbitmiles-email-notifications`
- **Messages available:** Should be near 0
- **Messages in flight:** Active processing
- **Age of oldest message:** Should be < 1 minute

### SES Metrics

Monitor: AWS Console → SES → Reputation metrics
- **Bounce rate:** Target < 2%
- **Complaint rate:** Target < 0.1%

### Database Queries

```sql
-- Check recent notifications
SELECT * FROM email_notifications ORDER BY sent_at DESC LIMIT 10;

-- Check notification counts
SELECT delivery_status, COUNT(*) FROM email_notifications GROUP BY delivery_status;

-- Check users with email enabled
SELECT COUNT(*) FROM users WHERE email_notifications_enabled = true AND email_verified = true;
```

---

## 🚨 Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| No email received | CloudWatch logs → match_activity_trail | Check notifications_sent flag and activity age |
| SQS queue backing up | CloudWatch logs → send_email_notification | Check for Lambda errors or SES throttling |
| Bounces increasing | SES Console → Suppression list | Review bounce reasons, fix email validation |
| GitHub Actions failing | Actions tab → workflow logs | Verify secrets and Lambda function names |

---

## 📚 Full Documentation

- **GitHub Secrets:** `.claude/github_secrets_setup.md`
- **Deployment Guide:** `.claude/email_notifications_deployment_guide.md`
- **Implementation Details:** `.claude/email_notifications_implementation.md`

---

## ✅ Done!

After completing all steps:
- ✅ 3 new Lambdas deployed
- ✅ 2 existing Lambdas updated
- ✅ AWS infrastructure created
- ✅ SES domain verified
- ✅ Email notifications live! 🎉

**Estimated Total Time:** 1-2 hours (+ 24 hours for SES approval)
