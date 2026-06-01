# Email Notifications for Trail Milestones and Ranking Changes

## Overview
Send email notifications to users when:
1. Their latest activity has **3+ new miles on the trail** (cumulative trail distance for that activity)
2. Their **ranking changed** on the weekly, monthly, or yearly leaderboard for that activity type

## Database Schema Changes

### Migration: Add Email Support to Users Table
```sql
-- Add email fields to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS email TEXT,
ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS send_trail_milestone BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN IF NOT EXISTS send_ranking_change BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN IF NOT EXISTS min_trail_distance_miles DECIMAL(5, 2) NOT NULL DEFAULT 3.0;

-- Add index for email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;

-- Add index for notification queries
CREATE INDEX IF NOT EXISTS idx_users_email_notifications 
ON users(email_notifications_enabled, email_verified) 
WHERE email_notifications_enabled = true AND email_verified = true;

-- Add comments
COMMENT ON COLUMN users.email IS 'User email address for notifications';
COMMENT ON COLUMN users.email_notifications_enabled IS 'Master switch for email notifications';
COMMENT ON COLUMN users.email_verified IS 'Whether email has been verified (via verification link)';
COMMENT ON COLUMN users.send_trail_milestone IS 'Send email when activity has significant trail miles';
COMMENT ON COLUMN users.send_ranking_change IS 'Send email when leaderboard ranking changes';
COMMENT ON COLUMN users.min_trail_distance_miles IS 'Minimum trail miles to trigger notification (default 3.0)';
```

### Migration: Create Email Notifications Tracking Table
```sql
-- Create table to track sent email notifications
CREATE TABLE IF NOT EXISTS email_notifications (
    id BIGSERIAL PRIMARY KEY,
    athlete_id BIGINT NOT NULL REFERENCES users(athlete_id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    notification_type TEXT NOT NULL CHECK (notification_type IN ('trail_milestone', 'ranking_change')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'sent', 'failed', 'bounced')),
    metadata JSONB,  -- Store details like old_rank, new_rank, trail_distance, window, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_email_notifications_athlete_id ON email_notifications(athlete_id);
CREATE INDEX IF NOT EXISTS idx_email_notifications_activity_id ON email_notifications(activity_id);
CREATE INDEX IF NOT EXISTS idx_email_notifications_sent_at ON email_notifications(sent_at);
CREATE INDEX IF NOT EXISTS idx_email_notifications_status ON email_notifications(delivery_status);

-- Prevent duplicate notifications for same activity
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_notifications_unique_activity 
ON email_notifications(athlete_id, activity_id, notification_type) 
WHERE activity_id IS NOT NULL;

-- Add comments
COMMENT ON TABLE email_notifications IS 'Tracks sent email notifications to prevent duplicates and monitor delivery';
COMMENT ON COLUMN email_notifications.notification_type IS 'Type of notification: trail_milestone or ranking_change';
COMMENT ON COLUMN email_notifications.delivery_status IS 'Email delivery status tracked via SES callbacks';
COMMENT ON COLUMN email_notifications.metadata IS 'Additional context (e.g., {"old_rank": 5, "new_rank": 3, "window": "week", "trail_distance_miles": 4.2})';
```

## User Settings API Changes

### Update `/user/settings` Endpoint
Add support for email-related fields in `backend/update_user_settings/lambda_function.py`:

**New accepted fields:**
- `email` (string, max 255 chars, validated email format)
- `email_notifications_enabled` (boolean)
- `send_trail_milestone` (boolean)
- `send_ranking_change` (boolean)
- `min_trail_distance_miles` (decimal, 0.1-100.0 range)

**Validation:**
- Email must be valid format (use regex or email-validator library)
- Setting `email_notifications_enabled = true` requires verified email
- When email changes, set `email_verified = false` and trigger verification flow

## Email Verification Flow

### 1. Create Email Verification Lambda
**Function:** `backend/verify_email/lambda_function.py`

**Flow:**
1. When user updates email, generate verification token:
   ```python
   token = hmac.new(APP_SECRET, f"{athlete_id}:{email}:{timestamp}".encode(), hashlib.sha256).hexdigest()
   ```
2. Store token temporarily (DynamoDB with TTL or RDS table)
3. Send verification email via SES with link: `https://rabbitmiles.com/verify-email?token={token}`
4. When user clicks link, verify token and set `email_verified = true`

### 2. Verification Email Template
Subject: "Verify your RabbitMiles email address"

Content:
```
Hi {display_name},

Please verify your email address to receive notifications from RabbitMiles.

[Verify Email Button] → https://rabbitmiles.com/verify-email?token={token}

This link expires in 24 hours.

If you didn't request this, you can safely ignore this email.

🐰 RabbitMiles
```

## AWS SES Configuration

### Step 1: Set Up AWS SES

#### 1.1 Move SES out of Sandbox Mode
SES starts in sandbox mode (limited to verified emails). To send to any user:

```bash
# Request production access via AWS Console or CLI
aws sesv2 put-account-details \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://rabbitmiles.com \
  --use-case-description "Transactional emails for trail running app: activity notifications and leaderboard updates" \
  --additional-contact-email-addresses your-email@example.com \
  --contact-language EN
```

Or via AWS Console:
1. Go to SES → Account dashboard
2. Click "Request production access"
3. Fill out form explaining use case
4. Usually approved within 24 hours

#### 1.2 Verify Domain (Recommended) or Email Address

**Option A: Verify Domain (Best Practice)**
```bash
# Via AWS Console:
# 1. SES → Configuration → Verified identities → Create identity
# 2. Select "Domain" and enter: rabbitmiles.com
# 3. Choose "Easy DKIM" (recommended)
# 4. Add the 3 CNAME records to your DNS (Route 53 or domain registrar)

# DNS Records to add (SES will provide exact values):
# - DKIM records (3x CNAME for email signing)
# - Optional: SPF record (TXT) - if not already set
#   v=spf1 include:amazonses.com ~all
# - Optional: DMARC record (TXT)
#   _dmarc.rabbitmiles.com TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@rabbitmiles.com"
```

**Option B: Verify Individual Email (Testing)**
```bash
aws sesv2 create-email-identity --email-identity notifications@rabbitmiles.com
# Check email inbox and click verification link
```

#### 1.3 Configure Sending Email Address
Create a "from" address:
- **Production:** `notifications@rabbitmiles.com` or `noreply@rabbitmiles.com`
- **Friendly name:** "RabbitMiles Notifications"

#### 1.4 Set Up Configuration Set (for tracking)
```bash
aws sesv2 create-configuration-set --configuration-set-name rabbitmiles-notifications

# Add event destinations for bounce/complaint handling
aws sesv2 create-configuration-set-event-destination \
  --configuration-set-name rabbitmiles-notifications \
  --event-destination-name bounce-complaints \
  --event-destination '{
    "Enabled": true,
    "MatchingEventTypes": ["BOUNCE", "COMPLAINT"],
    "SnsDestination": {
      "TopicArn": "arn:aws:sns:us-east-1:ACCOUNT_ID:ses-bounces-complaints"
    }
  }'
```

### Step 2: Create Email Templates in SES

#### Template 1: Trail Milestone
```bash
aws sesv2 create-email-template \
  --template-name trail-milestone \
  --template-content '{
    "Subject": "🎉 {{trail_distance_miles}} new miles on {{trail_name}}!",
    "Html": "<html><body><h1>Great job, {{display_name}}!</h1><p>You just covered <strong>{{trail_distance_miles}} miles</strong> on <strong>{{trail_name}}</strong>!</p><p>Activity: {{activity_name}}</p><p><a href=\"{{activity_url}}\">View Activity</a></p><hr><p><small><a href=\"{{unsubscribe_url}}\">Unsubscribe</a> | <a href=\"{{settings_url}}\">Email Preferences</a></small></p></body></html>",
    "Text": "Great job, {{display_name}}! You just covered {{trail_distance_miles}} miles on {{trail_name}}!\n\nActivity: {{activity_name}}\n\nView Activity: {{activity_url}}\n\nUnsubscribe: {{unsubscribe_url}}\nEmail Preferences: {{settings_url}}"
  }'
```

#### Template 2: Ranking Change
```bash
aws sesv2 create-email-template \
  --template-name ranking-change \
  --template-content '{
    "Subject": "🏆 You'\''re now #{{new_rank}} on the {{window}} {{activity_type}} leaderboard!",
    "Html": "<html><body><h1>Congratulations, {{display_name}}!</h1><p>Your ranking improved from <strong>#{{old_rank}}</strong> to <strong>#{{new_rank}}</strong> on the <strong>{{window}} {{activity_type}} leaderboard</strong>!</p><p>Activity that moved you up: {{activity_name}} ({{trail_distance_miles}} miles on trails)</p><p><a href=\"{{leaderboard_url}}\">View Leaderboard</a></p><hr><p><small><a href=\"{{unsubscribe_url}}\">Unsubscribe</a> | <a href=\"{{settings_url}}\">Email Preferences</a></small></p></body></html>",
    "Text": "Congratulations, {{display_name}}! Your ranking improved from #{{old_rank}} to #{{new_rank}} on the {{window}} {{activity_type}} leaderboard!\n\nActivity that moved you up: {{activity_name}} ({{trail_distance_miles}} miles on trails)\n\nView Leaderboard: {{leaderboard_url}}\n\nUnsubscribe: {{unsubscribe_url}}\nEmail Preferences: {{settings_url}}"
  }'
```

### Step 3: Create IAM Policy for Lambda

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendTemplatedEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

Attach to Lambda execution role:
```bash
aws iam attach-role-policy \
  --role-name lambda-email-sender-role \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/SESEmailSendingPolicy
```

### Step 4: Handle Bounces and Complaints

Create SNS topic and Lambda handler:
```python
# backend/handle_email_bounces/lambda_function.py
def handler(event, context):
    for record in event['Records']:
        message = json.loads(record['Sns']['Message'])
        notification_type = message['notificationType']
        
        if notification_type == 'Bounce':
            # Update email_verified = false for hard bounces
            if message['bounce']['bounceType'] == 'Permanent':
                email = message['mail']['destination'][0]
                # Update users table
        
        elif notification_type == 'Complaint':
            # User marked as spam - disable notifications
            email = message['mail']['destination'][0]
            # Update email_notifications_enabled = false
```

## Ranking Change Detection Logic

### Update `backend/match_activity_trail/lambda_function.py`

Add ranking snapshot logic:

```python
def get_current_rankings(exec_sql, athlete_id, start_date_local, user_timezone, activity_timezone):
    """Get user's current rankings before activity is processed"""
    bounds = leaderboard_agg.get_window_bounds(start_date_local, user_timezone, activity_timezone)
    if not bounds:
        return {}
    
    rankings = {}
    for window_name, (window_key, _, _) in bounds.items():
        for agg_type in leaderboard_agg.ALL_AGG_TYPES:
            # Get user's rank in this window/type
            sql = """
                SELECT rank FROM (
                    SELECT athlete_id, 
                           ROW_NUMBER() OVER (ORDER BY value DESC) as rank
                    FROM leaderboard_agg
                    WHERE window_key = :window_key 
                      AND metric = :metric
                      AND activity_type = :agg_type
                      AND value > 0
                ) ranked
                WHERE athlete_id = :athlete_id
            """
            params = [
                {"name": "window_key", "value": {"stringValue": window_key}},
                {"name": "metric", "value": {"stringValue": "distance"}},
                {"name": "agg_type", "value": {"stringValue": agg_type}},
                {"name": "athlete_id", "value": {"longValue": int(athlete_id)}}
            ]
            result = exec_sql(sql, params)
            records = result.get("records", [])
            if records and records[0]:
                old_rank = records[0][0].get("longValue")
                rankings[f"{window_name}_{agg_type}"] = old_rank
    
    return rankings

def check_ranking_changes(exec_sql, athlete_id, old_rankings, start_date_local, user_timezone, activity_timezone):
    """Compare old vs new rankings and return list of improvements"""
    new_rankings = get_current_rankings(exec_sql, athlete_id, start_date_local, user_timezone, activity_timezone)
    
    changes = []
    for key, new_rank in new_rankings.items():
        old_rank = old_rankings.get(key)
        # Rank improved if: was unranked and now ranked, OR rank number decreased (e.g., 5 → 3)
        if old_rank is None and new_rank:
            window, agg_type = key.rsplit("_", 1)
            changes.append({
                "window": window,
                "activity_type": agg_type,
                "old_rank": None,
                "new_rank": new_rank
            })
        elif old_rank and new_rank and new_rank < old_rank:
            window, agg_type = key.rsplit("_", 1)
            changes.append({
                "window": window,
                "activity_type": agg_type,
                "old_rank": old_rank,
                "new_rank": new_rank
            })
    
    return changes
```

## Email Notification Queue

### Option A: SQS Queue (Recommended)
Create SQS queue for async email sending:

```bash
aws sqs create-queue --queue-name rabbitmiles-email-notifications
```

**In `match_activity_trail` Lambda:**
```python
import boto3
sqs = boto3.client('sqs')
QUEUE_URL = os.environ.get('EMAIL_QUEUE_URL')

def queue_email_notification(notification_type, athlete_id, activity_id, metadata):
    """Queue email notification for async processing"""
    message = {
        "notification_type": notification_type,
        "athlete_id": athlete_id,
        "activity_id": activity_id,
        "metadata": metadata
    }
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )
```

### Option B: Direct SES Call (Simple)
Call SES directly from `match_activity_trail` Lambda (blocking, but fast for SES).

## Email Sender Lambda

### Create `backend/send_email_notification/lambda_function.py`

```python
import os
import json
import boto3

ses = boto3.client('sesv2')
rds = boto3.client('rds-data')

FROM_EMAIL = os.environ.get('FROM_EMAIL', 'notifications@rabbitmiles.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://rabbitmiles.com')

def handler(event, context):
    """Process email notification from SQS queue"""
    for record in event['Records']:
        message = json.loads(record['body'])
        
        notification_type = message['notification_type']
        athlete_id = message['athlete_id']
        activity_id = message['activity_id']
        metadata = message['metadata']
        
        # Get user details
        user = get_user(athlete_id)
        
        # Check if user has notifications enabled and email verified
        if not user or not user['email'] or not user['email_verified']:
            continue
        
        if not user['email_notifications_enabled']:
            continue
        
        # Check notification-specific preferences
        if notification_type == 'trail_milestone' and not user['send_trail_milestone']:
            continue
        if notification_type == 'ranking_change' and not user['send_ranking_change']:
            continue
        
        # Check for duplicate notifications
        if already_sent(athlete_id, activity_id, notification_type):
            print(f"Skipping duplicate notification for athlete {athlete_id}, activity {activity_id}")
            continue
        
        # Send email
        try:
            send_email(notification_type, user, activity_id, metadata)
            
            # Record notification
            record_notification(athlete_id, activity_id, notification_type, 'sent', metadata)
        except Exception as e:
            print(f"Failed to send email: {e}")
            record_notification(athlete_id, activity_id, notification_type, 'failed', metadata)

def send_email(notification_type, user, activity_id, metadata):
    """Send templated email via SES"""
    template_name = 'trail-milestone' if notification_type == 'trail_milestone' else 'ranking-change'
    
    template_data = {
        "display_name": user['display_name'],
        "settings_url": f"{FRONTEND_URL}/settings",
        "unsubscribe_url": f"{FRONTEND_URL}/unsubscribe?token={generate_unsubscribe_token(user['athlete_id'])}",
        **metadata  # Include trail_distance_miles, activity_name, etc.
    }
    
    ses.send_email(
        FromEmailAddress=FROM_EMAIL,
        Destination={'ToAddresses': [user['email']]},
        Content={
            'Template': {
                'TemplateName': template_name,
                'TemplateData': json.dumps(template_data)
            }
        },
        ConfigurationSetName='rabbitmiles-notifications'
    )
```

## Integration Points

### 1. In `match_activity_trail` Lambda
After successfully matching activity to trails:

```python
# Before leaderboard recompute
old_rankings = get_current_rankings(exec_sql, athlete_id, start_date_local, user_tz, activity_tz)

# Recompute leaderboard
leaderboard_agg.recompute_for_activity(exec_sql, athlete_id, start_date_local, user_tz, activity_tz)

# Check trail milestone
trail_distance_miles = round(distance_on_trail / 1609.34, 1)  # meters to miles
if trail_distance_miles >= min_trail_distance:  # Get from user settings
    queue_email_notification('trail_milestone', athlete_id, activity_id, {
        'trail_distance_miles': trail_distance_miles,
        'trail_name': trail_name,
        'activity_name': activity_name,
        'activity_url': f"{FRONTEND_URL}/activity/{activity_id}"
    })

# Check ranking changes
ranking_changes = check_ranking_changes(exec_sql, athlete_id, old_rankings, start_date_local, user_tz, activity_tz)
for change in ranking_changes:
    queue_email_notification('ranking_change', athlete_id, activity_id, {
        'old_rank': change['old_rank'],
        'new_rank': change['new_rank'],
        'window': change['window'],
        'activity_type': change['activity_type'],
        'activity_name': activity_name,
        'trail_distance_miles': trail_distance_miles,
        'leaderboard_url': f"{FRONTEND_URL}/leaderboard"
    })
```

### 2. Frontend Changes

**Settings Page:**
- Add email input field
- Add email verification status indicator
- Add "Resend verification email" button
- Add checkboxes for notification preferences
- Add slider/input for minimum trail distance threshold

**Email Verification Page:**
- New route: `/verify-email`
- Parse token from URL
- Call verification endpoint
- Show success/error message

## Environment Variables

Add to Lambda functions:

```bash
# Email sender Lambda
FROM_EMAIL=notifications@rabbitmiles.com
EMAIL_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/ACCOUNT/rabbitmiles-email-notifications

# Activity processor Lambdas
EMAIL_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/ACCOUNT/rabbitmiles-email-notifications
```

## Testing Checklist

- [ ] Email collection and validation in settings
- [ ] Email verification flow (send, click link, verify)
- [ ] Trail milestone email triggers at 3+ miles
- [ ] Ranking change email triggers when rank improves
- [ ] No duplicate emails for same activity
- [ ] Unsubscribe link works
- [ ] Email preferences respected (per-notification-type)
- [ ] Bounces handled correctly (email_verified set to false)
- [ ] SES sandbox mode testing with verified emails
- [ ] Production mode with real user emails
- [ ] Mobile-friendly email templates
- [ ] DKIM/SPF/DMARC validation (mail-tester.com)

## Cost Estimates

**AWS SES Pricing:**
- First 62,000 emails/month: FREE (if sending from EC2/Lambda)
- After that: $0.10 per 1,000 emails
- Example: 1,000 active users × 2 emails/week = ~8,000 emails/month = FREE

**Additional Costs:**
- SQS queue: Negligible (first 1M requests free/month)
- Lambda invocations: Negligible (covered by free tier)
- Database storage: ~1KB per notification record

## Future Enhancements

- [ ] Daily/weekly digest option (batch notifications)
- [ ] SMS notifications (via SNS)
- [ ] Push notifications (via mobile app)
- [ ] Email customization (HTML vs plain text preference)
- [ ] Notification history page in UI
- [ ] A/B test email templates
- [ ] Track email open rates (pixel tracking)
- [ ] Track click-through rates (link tracking)

## References

- [AWS SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/)
- [SES Email Templates](https://docs.aws.amazon.com/ses/latest/dg/send-personalized-email-api.html)
- [SES Bounce/Complaint Handling](https://docs.aws.amazon.com/ses/latest/dg/monitor-sending-activity-using-notifications.html)
- [Email Best Practices](https://docs.aws.amazon.com/ses/latest/dg/best-practices.html)
