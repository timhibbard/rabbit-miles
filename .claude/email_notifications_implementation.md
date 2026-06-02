# Email Notifications Implementation Guide

## Overview
Implementing email notifications for trail milestones (3+ miles) and ranking changes on leaderboards.

## Preventing Historical Activity Notifications

### The Challenge
We need to prevent email notifications for:
1. **Historical activities** - Activities uploaded during backfills or manual imports
2. **Pre-existing activities** - Activities that existed before the email feature was deployed
3. **Reprocessed activities** - Activities being recomputed for leaderboards

### The Solution: Two-Factor Check

We use a **dual-check strategy** in `match_activity_trail` Lambda:

1. **`notifications_sent` flag** - Boolean column on `activities` table
   - Default: `false` for new activities
   - Set to `true` after notifications are queued
   - Migration 014 sets it to `true` for all existing activities (one-time)

2. **`created_at` timestamp check** - Verify activity is fresh
   - Only send notifications if `created_at` is within last **10 minutes**
   - This ensures we only notify for fresh webhook events, not backfills

### Logic Flow in match_activity_trail

```python
# After successfully matching activity to trail and updating leaderboards:

# 1. Get activity metadata
activity_query = """
SELECT notifications_sent, created_at, start_date_local
FROM activities
WHERE id = :activity_id
"""
activity_info = exec_sql(activity_query, ...)

notifications_sent = activity_info['notifications_sent']
created_at = activity_info['created_at']

# 2. Check if we should send notifications
current_time = datetime.now(timezone.utc)
activity_age_minutes = (current_time - created_at).total_seconds() / 60

should_notify = (
    not notifications_sent and  # Haven't sent yet
    activity_age_minutes <= 10   # Fresh activity (webhook event)
)

if not should_notify:
    print(f"Skipping notifications: notifications_sent={notifications_sent}, age={activity_age_minutes:.1f}min")
    return

# 3. Queue notifications (trail milestone and/or ranking change)
# ... queue logic here ...

# 4. Mark as sent to prevent duplicates
update_sql = """
UPDATE activities
SET notifications_sent = true, updated_at = now()
WHERE id = :activity_id
"""
exec_sql(update_sql, ...)
```

### Why This Works

**Webhook flow (WILL send notifications):**
- User completes activity → Strava webhook fires immediately
- `webhook_processor` fetches and stores activity (creates new row)
- `created_at` is set to NOW()
- `match_activity_trail` runs within seconds
- Age check passes (< 10 minutes), notifications queued
- `notifications_sent` set to `true`

**Backfill flow (WON'T send notifications):**
- Admin runs backfill script for historical activities
- Script creates activities in database
- `created_at` is set to NOW() when inserted
- BUT: backfill is slow, processes activities in batches
- By the time `match_activity_trail` runs, age > 10 minutes
- Age check fails, no notifications sent

**Manual refresh flow (WON'T send notifications):**
- User clicks "Refresh Activities" button
- Fetches last N activities from Strava
- Activities already exist (ON CONFLICT DO UPDATE)
- `created_at` remains unchanged (old timestamp)
- Age check fails, no notifications sent

**Reprocessing flow (WON'T send notifications):**
- Admin triggers leaderboard recomputation
- Re-runs `match_activity_trail` for existing activities
- Either: `notifications_sent = true` (already sent)
- Or: `created_at` is old (> 10 minutes)
- No duplicate notifications sent

### Edge Cases Handled

1. **Lambda cold start delays:**
   - 10-minute window provides buffer for Lambda cold starts
   - Webhook → trail matching typically completes in 5-30 seconds

2. **SQS retries:**
   - If `match_activity_trail` fails and retries
   - `notifications_sent` remains `false` until success
   - Retries still pass age check if within 10 minutes
   - Only sets flag on successful completion

3. **Activity updates:**
   - User edits activity name/description on Strava
   - Webhook fires "update" event
   - `ON CONFLICT DO UPDATE` preserves `notifications_sent = true`
   - No duplicate notifications sent

4. **Manual testing:**
   - Developers can manually trigger `match_activity_trail`
   - Age check prevents accidental notifications
   - Can override by temporarily setting `notifications_sent = false` and `created_at = NOW()`

## Database Schema

### Migration 012: User Email Fields
```sql
ALTER TABLE users
ADD COLUMN email TEXT,
ADD COLUMN email_notifications_enabled BOOLEAN DEFAULT false,
ADD COLUMN email_verified BOOLEAN DEFAULT false,
ADD COLUMN send_trail_milestone BOOLEAN DEFAULT true,
ADD COLUMN send_ranking_change BOOLEAN DEFAULT true,
ADD COLUMN min_trail_distance_miles DECIMAL(5, 2) DEFAULT 3.0;
```

### Migration 013: Email Notifications Tracking
```sql
CREATE TABLE email_notifications (
    id BIGSERIAL PRIMARY KEY,
    athlete_id BIGINT REFERENCES users(athlete_id),
    activity_id BIGINT REFERENCES activities(id),
    notification_type TEXT CHECK (notification_type IN ('trail_milestone', 'ranking_change')),
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivery_status TEXT DEFAULT 'pending',
    metadata JSONB,
    ...
);

-- Prevent duplicate notifications
CREATE UNIQUE INDEX idx_email_notifications_unique_activity
ON email_notifications(athlete_id, activity_id, notification_type)
WHERE activity_id IS NOT NULL;
```

### Migration 014: Notifications Sent Flag
```sql
ALTER TABLE activities
ADD COLUMN notifications_sent BOOLEAN DEFAULT false;

-- Mark all existing activities as already notified
UPDATE activities SET notifications_sent = true;
```

## Lambda Functions Created

### 1. verify_email/lambda_function.py
**Purpose:** Send and verify email verification links

**Endpoints:**
- `POST /verify-email/send` - Send verification email to authenticated user
- `GET /verify-email?token=...` - Verify token and mark email as verified

**Token format:** `{athlete_id}:{timestamp}:{hmac_hash}`
- 24-hour expiry
- HMAC-SHA256 signed with APP_SECRET

### 2. send_email_notification/lambda_function.py
**Purpose:** Process email queue and send notifications via SES

**Trigger:** SQS queue messages from `match_activity_trail`

**Logic:**
1. Get user preferences from database
2. Check email verified and notifications enabled
3. Check notification-specific preferences
4. Check for duplicate notifications (via `email_notifications` table)
5. Send email via SES
6. Record in `email_notifications` table

**Email types:**
- `trail_milestone` - "🎉 X new miles on {trail_name}!"
- `ranking_change` - "🏆 You're now #X on the {window} leaderboard!"

### 3. handle_email_bounces/lambda_function.py (TODO)
**Purpose:** Handle SES bounces and complaints via SNS

**Actions:**
- Hard bounce → Set `email_verified = false`
- Complaint → Set `email_notifications_enabled = false`

## Updated Lambda Functions

### update_user_settings/lambda_function.py
**Added fields:**
- `email` - Validated email address (regex check)
- `email_notifications_enabled` - Master switch (requires verified email)
- `send_trail_milestone` - Trail milestone preference
- `send_ranking_change` - Ranking change preference
- `min_trail_distance_miles` - Minimum threshold (0.1-100.0)

**Validation:**
- Email format validation
- Requires verified email before enabling notifications
- Auto-sets `email_verified = false` when email changes

## Next Steps (Remaining Tasks)

### Task 6: Add ranking snapshot logic to match_activity_trail
1. Query user's current rankings BEFORE recomputing leaderboard
2. Recompute leaderboard (existing logic)
3. Query user's NEW rankings AFTER recompute
4. Compare old vs new rankings
5. Detect improvements (rank number decreased or newly ranked)

### Task 7: Integrate email queueing in match_activity_trail
1. Check `notifications_sent` flag and `created_at` age
2. Check trail milestone threshold
3. Queue SQS messages for notifications
4. Set `notifications_sent = true`

### Task 8: Create AWS SES email templates
Using SES `CreateEmailTemplate` API:
- `trail-milestone` template
- `ranking-change` template

### Task 9: Create bounce/complaint handler Lambda
- Subscribe to SNS topic from SES
- Parse bounce/complaint events
- Update user database fields

### Task 10-11: Frontend changes
- Settings page: Email input, verification status, preferences
- Verification page: `/verify-email?token=...` route

### Task 12: AWS infrastructure
- Set up SES domain verification (rabbitmiles.com)
- Create SQS queue (`rabbitmiles-email-notifications`)
- Create SNS topic for bounces/complaints
- Configure IAM policies for Lambdas
- Move SES out of sandbox mode

## Testing Strategy

### Unit Testing
1. Test email validation in `update_user_settings`
2. Test token generation/verification in `verify_email`
3. Test notification queueing logic in `match_activity_trail`
4. Test user preference checks in `send_email_notification`

### Integration Testing (Sandbox Mode)
1. Add verified test email to SES sandbox
2. Create test activity via webhook
3. Verify notification queued (check SQS)
4. Verify email sent (check test inbox)
5. Verify recorded in `email_notifications` table

### Edge Case Testing
1. **Historical activity:** Create activity with old `created_at`, verify no notification
2. **Duplicate:** Trigger same activity twice, verify only one email sent
3. **Below threshold:** Activity with 2 miles, verify no trail milestone email
4. **Unverified email:** User with unverified email, verify no email sent
5. **Disabled notifications:** User with notifications off, verify no email sent
6. **No email:** User without email set, verify no error thrown

### Production Testing
1. Enable for single test user first (allowlist in code)
2. Monitor CloudWatch logs for errors
3. Check SES bounce/complaint rates
4. Gradually roll out to all users

## Monitoring & Alerts

### CloudWatch Metrics
- Email send rate (per hour)
- Email failure rate
- Bounce rate
- Complaint rate
- SQS queue depth

### CloudWatch Alarms
- Email failure rate > 5%
- Bounce rate > 2%
- Complaint rate > 0.1%
- SQS queue depth > 100 (backlog)

### Logs to Monitor
- `send_email_notification` errors
- SES API errors (throttling, bounce)
- Duplicate notification attempts
- Users with unverified emails attempting to enable notifications

## Cost Estimates

### AWS SES
- First 62,000 emails/month: FREE (Lambda-originated)
- After that: $0.10 per 1,000 emails
- Example: 1,000 users × 2 emails/week = ~8,000/month = FREE

### SQS
- First 1M requests/month: FREE
- After: $0.40 per 1M requests
- Negligible cost

### Lambda
- Invocations covered by free tier
- Negligible incremental cost

### Total estimated cost: $0-5/month for <5,000 active users
