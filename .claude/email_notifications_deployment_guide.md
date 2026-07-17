# Email Notifications Deployment Guide

## ✅ Completed Backend Implementation

### Database Migrations (YOU COMPLETED)
- ✅ Migration 012: User email fields
- ✅ Migration 013: Email notifications tracking table
- ✅ Migration 014: notifications_sent flag on activities

### Lambda Functions (I COMPLETED)
- ✅ `verify_email/` - Email verification endpoint
- ✅ `send_email_notification/` - SQS-triggered email sender
- ✅ `handle_email_bounces/` - SNS-triggered bounce handler
- ✅ `update_user_settings/` - Updated to handle email fields
- ✅ `match_activity_trail/` - Updated with ranking detection & notification queueing

### Helper Scripts (I COMPLETED)
- ✅ `backend/scripts/setup_email_infrastructure.sh` - AWS infrastructure setup

---

## 🚀 Deployment Steps

### Phase 1: Deploy Lambda Functions

#### 1. Deploy `verify_email` Lambda

**Function configuration:**
- Runtime: Python 3.x
- Handler: `lambda_function.handler`
- Timeout: 30 seconds
- Memory: 256 MB

**Environment variables:**
```bash
DB_CLUSTER_ARN=arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER
DB_SECRET_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET
DB_NAME=postgres
APP_SECRET=your-app-secret
FRONTEND_URL=https://rabbitmiles.com
FROM_EMAIL=notifications@rabbitmiles.com
```

**IAM permissions needed:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

**API Gateway routes:**
- `POST /verify-email/send` → verify_email Lambda
- `GET /verify-email` → verify_email Lambda

#### 2. Deploy `send_email_notification` Lambda

**Function configuration:**
- Runtime: Python 3.x
- Handler: `lambda_function.handler`
- Timeout: 60 seconds
- Memory: 256 MB

**Environment variables:**
```bash
DB_CLUSTER_ARN=arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER
DB_SECRET_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET
DB_NAME=postgres
APP_SECRET=your-app-secret
FROM_EMAIL=notifications@rabbitmiles.com
FRONTEND_URL=https://rabbitmiles.com
SES_CONFIG_SET=rabbitmiles-notifications
```

**IAM permissions needed:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT:rabbitmiles-email-notifications"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trigger:** SQS queue (configured in Phase 2)

#### 3. Deploy `handle_email_bounces` Lambda

**Function configuration:**
- Runtime: Python 3.x
- Handler: `lambda_function.handler`
- Timeout: 30 seconds
- Memory: 128 MB

**Environment variables:**
```bash
DB_CLUSTER_ARN=arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER
DB_SECRET_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET
DB_NAME=postgres
```

**IAM permissions needed:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:REGION:ACCOUNT:cluster:YOUR_CLUSTER"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:YOUR_SECRET"
    }
  ]
}
```

**Trigger:** SNS topic (configured in Phase 2)

#### 4. Update `update_user_settings` Lambda

**Deploy updated code** from `backend/update_user_settings/lambda_function.py`

No new environment variables or permissions needed.

#### 5. Update `match_activity_trail` Lambda

**Deploy updated code** from `backend/match_activity_trail/lambda_function.py`

**Add environment variables:**
```bash
EMAIL_QUEUE_URL=https://sqs.REGION.amazonaws.com/ACCOUNT/rabbitmiles-email-notifications
FRONTEND_URL=https://rabbitmiles.com
```

**Add IAM permissions:**
```json
{
  "Effect": "Allow",
  "Action": [
    "sqs:SendMessage"
  ],
  "Resource": "arn:aws:sqs:REGION:ACCOUNT:rabbitmiles-email-notifications"
}
```

---

### Phase 2: Set Up AWS Infrastructure

#### Option A: Run Setup Script (Recommended)

```bash
cd backend/scripts
./setup_email_infrastructure.sh
```

**Before running, edit the script and update:**
- `AWS_ACCOUNT_ID`
- `AWS_REGION`

#### Option B: Manual Setup

**1. Create SQS Queue**

```bash
aws sqs create-queue \
  --queue-name rabbitmiles-email-notifications \
  --attributes '{
    "MessageRetentionPeriod": "1209600",
    "VisibilityTimeout": "300"
  }'
```

Save the queue URL.

**2. Create SNS Topic**

```bash
aws sns create-topic --name rabbitmiles-ses-bounces
```

Save the topic ARN.

**3. Create SES Configuration Set**

```bash
aws sesv2 create-configuration-set \
  --configuration-set-name rabbitmiles-notifications
```

**4. Add Event Destination to SES**

```bash
aws sesv2 create-configuration-set-event-destination \
  --configuration-set-name rabbitmiles-notifications \
  --event-destination-name bounce-complaints \
  --event-destination '{
    "Enabled": true,
    "MatchingEventTypes": ["BOUNCE", "COMPLAINT"],
    "SnsDestination": {
      "TopicArn": "arn:aws:sns:REGION:ACCOUNT:rabbitmiles-ses-bounces"
    }
  }'
```

**5. Subscribe Lambda to SNS**

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:rabbitmiles-ses-bounces \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:REGION:ACCOUNT:function:rabbitmiles-handle-email-bounces

aws lambda add-permission \
  --function-name rabbitmiles-handle-email-bounces \
  --statement-id AllowSNSInvoke \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn arn:aws:sns:REGION:ACCOUNT:rabbitmiles-ses-bounces
```

**6. Configure SQS Trigger on Lambda**

In AWS Console or via CLI:
- Go to `send_email_notification` Lambda
- Add trigger: SQS
- Select queue: `rabbitmiles-email-notifications`
- Batch size: 10
- Batch window: 0 seconds

---

### Phase 3: Set Up SES

#### 1. Verify Domain

**AWS Console → SES → Verified identities → Create identity**

1. Select "Domain"
2. Enter: `rabbitmiles.com`
3. Choose "Easy DKIM"
4. Copy the DNS records

**Add DNS records to your domain:**
- 3 CNAME records for DKIM signing
- Optionally: SPF and DMARC records

**Wait for verification** (usually 5-10 minutes)

#### 2. Verify Sender Email (Sandbox Testing)

While in sandbox mode, verify your test email:

```bash
aws sesv2 create-email-identity \
  --email-identity your-test-email@example.com
```

Check email and click verification link.

#### 3. Request Production Access

**AWS Console → SES → Account dashboard → Request production access**

Fill out form:
- **Mail type:** Transactional
- **Website URL:** https://rabbitmiles.com
- **Use case:** Trail running app activity notifications and leaderboard updates
- **Describe:** We send opt-in notifications to users when they complete trail running activities with significant trail mileage (3+ miles) or when their leaderboard ranking improves. Users must verify their email before receiving notifications and can unsubscribe anytime.
- **Compliance:** We follow CAN-SPAM and users must opt-in
- **Bounce handling:** Automated bounce and complaint handling via Lambda functions

**Typical approval time:** 24 hours

---

## 🧪 Testing

### Phase 1: Sandbox Testing (Before Production Access)

#### Test 1: Email Verification Flow

```bash
# 1. Set email address via API
curl -X PATCH https://api.rabbitmiles.com/user/settings \
  -H "Cookie: session=YOUR_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"email": "your-verified-test-email@example.com"}'

# 2. Send verification email
curl -X POST https://api.rabbitmiles.com/verify-email/send \
  -H "Cookie: session=YOUR_SESSION"

# 3. Check email inbox for verification link
# 4. Click link or manually visit:
curl "https://api.rabbitmiles.com/verify-email?token=TOKEN_FROM_EMAIL"

# 5. Verify email_verified=true in database
```

#### Test 2: Trail Milestone Notification (Manual Trigger)

```bash
# 1. Enable notifications
curl -X PATCH https://api.rabbitmiles.com/user/settings \
  -H "Cookie: session=YOUR_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"email_notifications_enabled": true, "send_trail_milestone": true}'

# 2. Create test activity with fresh created_at
# (Use Strava webhook or manually insert into DB with recent created_at)

# 3. Trigger match_activity_trail
aws lambda invoke \
  --function-name rabbitmiles-match-activity-trail \
  --payload '{"activity_id": YOUR_TEST_ACTIVITY_ID}' \
  response.json

# 4. Check SQS queue for message
aws sqs receive-message \
  --queue-url https://sqs.REGION.amazonaws.com/ACCOUNT/rabbitmiles-email-notifications

# 5. Wait ~10 seconds for Lambda to process (if message visible)
# 6. Check test email inbox
```

#### Test 3: Ranking Change Notification

```bash
# Similar to Test 2, but:
# - Activity must improve user's leaderboard rank
# - Enable send_ranking_change preference
# - Verify ranking change email received
```

#### Test 4: Duplicate Prevention

```bash
# 1. Trigger same activity twice
aws lambda invoke \
  --function-name rabbitmiles-match-activity-trail \
  --payload '{"activity_id": SAME_ACTIVITY_ID}' \
  response.json

# 2. Verify only ONE email sent (check email_notifications table)
```

#### Test 5: Historical Activity (Should NOT Send)

```bash
# 1. Find activity with old created_at (> 10 minutes)
# 2. Set notifications_sent = false manually
UPDATE activities SET notifications_sent = false WHERE id = OLD_ACTIVITY_ID;

# 3. Trigger match_activity_trail
# 4. Verify NO email sent (age check should fail)
```

### Phase 2: Production Testing (After SES Production Access)

#### Test 1: Real User Workflow

1. Real user completes activity on Strava
2. Webhook fires → webhook_processor → match_activity_trail
3. Notification queued if eligible
4. Email sent to real user

**Monitor:**
- CloudWatch logs for all Lambda functions
- SQS queue depth (should be near 0)
- SES bounce rate (should be < 2%)
- SES complaint rate (should be < 0.1%)

#### Test 2: Bounce Handling

1. Send email to invalid address (e.g., bounce@simulator.amazonses.com)
2. Verify hard bounce → email_verified set to false
3. Verify user can't enable notifications until re-verified

#### Test 3: Complaint Handling

1. Send email to complaint@simulator.amazonses.com
2. Verify complaint → email_notifications_enabled set to false
3. Verify no more emails sent to that user

---

## 📊 Monitoring

### CloudWatch Alarms (Set These Up)

```bash
# Email send failure rate > 5%
aws cloudwatch put-metric-alarm \
  --alarm-name rabbitmiles-email-send-failure-rate \
  --alarm-description "Email send failure rate exceeds 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=rabbitmiles-send-email-notification

# SQS queue depth > 100
aws cloudwatch put-metric-alarm \
  --alarm-name rabbitmiles-email-queue-backlog \
  --alarm-description "Email queue has > 100 messages" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --statistic Average \
  --period 300 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=QueueName,Value=rabbitmiles-email-notifications
```

### Metrics to Track

**SES Metrics (Console → SES → Reputation metrics):**
- Bounce rate (target: < 2%)
- Complaint rate (target: < 0.1%)
- Send rate (emails per hour)

**Lambda Metrics:**
- `send_email_notification` invocations
- `send_email_notification` errors
- `send_email_notification` duration

**SQS Metrics:**
- `ApproximateNumberOfMessagesVisible` (queue depth)
- `NumberOfMessagesReceived`
- `NumberOfMessagesDeleted`

**Database Queries:**
```sql
-- Notification delivery status breakdown
SELECT delivery_status, COUNT(*) 
FROM email_notifications 
GROUP BY delivery_status;

-- Recent notifications
SELECT n.*, u.email 
FROM email_notifications n
JOIN users u ON u.athlete_id = n.athlete_id
ORDER BY sent_at DESC 
LIMIT 20;

-- Users with bounced emails
SELECT u.athlete_id, u.email, u.email_verified 
FROM users u 
WHERE email_verified = false 
  AND email IS NOT NULL;
```

---

## 🎯 Rollout Strategy

### Week 1: Sandbox Testing
- Deploy all Lambda functions
- Test with verified emails only
- Fix any bugs

### Week 2: Request Production Access
- Submit SES production access request
- Wait for approval
- Set up domain verification

### Week 3: Limited Rollout
- Enable for 10 test users (allowlist in code if needed)
- Monitor closely for issues
- Verify bounce/complaint handling works

### Week 4: Full Rollout
- Remove allowlist
- Enable for all users
- Monitor metrics
- Celebrate! 🎉

---

## 🐛 Troubleshooting

### No Email Received

**Check:**
1. Email verified? `SELECT email_verified FROM users WHERE athlete_id = X`
2. Notifications enabled? `SELECT email_notifications_enabled FROM users WHERE athlete_id = X`
3. Activity fresh? `SELECT created_at, notifications_sent FROM activities WHERE id = X`
4. SQS message queued? Check CloudWatch logs for `match_activity_trail`
5. Lambda invoked? Check CloudWatch logs for `send_email_notification`
6. SES error? Check CloudWatch logs for SES API errors

### Emails Going to Spam

**Fix:**
1. Verify DKIM, SPF, DMARC records
2. Use mail-tester.com to check email score
3. Reduce send rate if needed
4. Improve email content (less spammy language)

### High Bounce Rate

**Fix:**
1. Check email validation logic
2. Review bounce reasons in SNS notifications
3. Consider double opt-in (verify email before allowing signup)

### SQS Queue Backing Up

**Fix:**
1. Check `send_email_notification` Lambda errors
2. Increase Lambda concurrency if needed
3. Check SES rate limits

---

## 📝 TODO: Frontend (Not Yet Implemented)

**Task 10: Settings Page**
- Email input field
- "Verify Email" button
- Email verification status indicator
- Notification preferences checkboxes
- Min trail distance slider

**Task 11: Verification Page**
- Route: `/verify-email?token=...`
- Parse token, call API, show success/error

---

## 💰 Cost Estimate

**Monthly costs for 1,000 active users:**

- **SES:** FREE (first 62,000 emails from Lambda)
- **SQS:** FREE (first 1M requests)
- **Lambda:** Negligible (covered by free tier)
- **Total:** $0-5/month

**At scale (10,000 users):**
- ~40,000 emails/month
- Still FREE (under 62,000 limit)
