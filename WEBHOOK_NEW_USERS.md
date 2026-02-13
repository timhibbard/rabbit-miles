# Strava Webhook for New Users - How It Works

## Question
When new users sign up, does the Strava webhook get updated with their athlete information so new activities are automatically added?

## Answer
**Yes, automatically!** New users are immediately covered by the existing webhook subscription when they authorize the app. No additional configuration or subscription updates are needed.

## How Strava Webhooks Work

### Application-Level Subscription
Strava webhooks operate at the **application level**, not per user:

```
┌──────────────────────────────────────────┐
│  Strava Application                       │
│  (Your Client ID)                        │
│                                          │
│  ONE webhook subscription covers:        │
│  - All existing users                    │
│  - All future users                      │
│  - Automatically                          │
└──────────────────────────────────────────┘
```

### When a New User Signs Up

1. **User authorizes the app** (via OAuth flow)
   - User clicks "Connect with Strava"
   - Strava redirects to `/auth/callback`
   - Access/refresh tokens are stored in database

2. **Webhook coverage is automatic**
   - No API call needed to "add" user to webhook
   - Strava already knows this athlete authorized your app
   - Future activities will trigger webhook events

3. **Webhook event delivery**
   ```json
   {
     "object_type": "activity",
     "aspect_type": "create",
     "object_id": 123456789,
     "owner_id": 999999,  ← This identifies the athlete
     "subscription_id": 12345,
     "event_time": 1234567890
   }
   ```

4. **Event processing**
   - webhook_processor Lambda receives event
   - Looks up user by `owner_id` in database
   - Fetches activity details from Strava API
   - Stores activity in database

## Current Implementation

### What's Already Working ✅

1. **Single Subscription**
   - One webhook subscription for entire application
   - Created via `POST /api/v3/push_subscriptions`
   - Covers all users automatically

2. **Auth Callback Handler**
   - `/auth/callback` stores new user credentials
   - No webhook-specific code needed
   - User is immediately "registered" with Strava

3. **Webhook Processor**
   - Handles events for any `owner_id`
   - Looks up user tokens from database
   - Works for both existing and new users

4. **Token Management**
   - Automatically refreshes expired tokens
   - Uses refresh_token from database
   - No manual intervention needed

### Event Flow for New User

```
1. New user authorizes app
   └─> auth_callback stores credentials
   
2. User creates activity in Strava app
   └─> Strava sends webhook POST
       └─> Contains owner_id (athlete ID)
       
3. webhook Lambda receives event
   └─> Queues to SQS
   
4. webhook_processor Lambda processes event
   └─> Looks up owner_id in users table
   └─> Finds the new user
   └─> Fetches activity from Strava
   └─> Stores in activities table
   
5. Activity appears in user's dashboard
```

## Verification Checklist

To verify webhooks are working for new users:

### 1. Check Webhook Subscription Status
```bash
curl -G https://www.strava.com/api/v3/push_subscriptions \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET
```

Expected response:
```json
[
  {
    "id": 123456,
    "application_id": YOUR_CLIENT_ID,
    "callback_url": "https://api.rabbitmiles.com/strava/webhook",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### 2. Check Lambda Environment Variables

**webhook Lambda:**
```bash
aws lambda get-function-configuration \
  --function-name rabbitmiles-webhook \
  --query 'Environment.Variables'
```

Required:
- `WEBHOOK_VERIFY_TOKEN` - Set
- `WEBHOOK_SQS_QUEUE_URL` - Valid queue URL

**webhook_processor Lambda:**
```bash
aws lambda get-function-configuration \
  --function-name rabbitmiles-webhook-processor \
  --query 'Environment.Variables'
```

Required:
- `DB_CLUSTER_ARN` - Valid cluster ARN
- `DB_SECRET_ARN` - Valid secret ARN
- `DB_NAME` - "postgres"
- `STRAVA_CLIENT_ID` - Set
- `STRAVA_CLIENT_SECRET` - Set

### 3. Test Webhook Endpoint

```bash
# Test validation endpoint
curl -X GET 'https://api.rabbitmiles.com/strava/webhook?hub.verify_token=YOUR_TOKEN&hub.challenge=test123&hub.mode=subscribe'

# Expected: {"hub.challenge":"test123"}
```

### 4. Monitor CloudWatch Logs

After a new user signs up and creates an activity:

```bash
# Check webhook Lambda logs
aws logs tail /aws/lambda/rabbitmiles-webhook --follow

# Check webhook_processor Lambda logs
aws logs tail /aws/lambda/rabbitmiles-webhook-processor --follow
```

Look for:
- "Received webhook event" with the new user's athlete_id
- "Successfully stored activity" messages
- No "User not found" errors

### 5. Check Database

Verify events are being processed:

```sql
-- Check recent webhook events
SELECT * FROM webhook_events 
ORDER BY processed_at DESC 
LIMIT 10;

-- Check activities for new user
SELECT * FROM activities 
WHERE athlete_id = NEW_USER_ATHLETE_ID
ORDER BY start_date DESC;
```

## Common Issues and Solutions

### Issue: Webhook events not being received

**Symptom:** New user creates activity but it doesn't appear

**Check:**
1. Subscription exists: `curl -G https://www.strava.com/api/v3/push_subscriptions ...`
2. API Gateway route configured: `GET/POST /strava/webhook`
3. Lambda has correct environment variables
4. CloudWatch logs show no errors

**Solution:** 
- If no subscription exists, create one (see WEBHOOK_SETUP.md)
- Verify callback URL matches API Gateway URL exactly
- Check IAM permissions for Lambda functions

### Issue: Events received but not processed

**Symptom:** Logs show "Received webhook event" but no "Successfully stored activity"

**Check:**
1. SQS queue has messages: AWS Console → SQS
2. Lambda triggered by SQS: Event source mapping exists
3. Database credentials valid
4. User exists in database with valid tokens

**Solution:**
- Check SQS event source mapping configuration
- Verify database connectivity
- Check user's token expiration (should auto-refresh)

### Issue: User not found in database

**Symptom:** Logs show "User {athlete_id} not found or not connected to Strava"

**Root Cause:** This is normal! It means:
- User previously authorized app but has since disconnected
- Or webhook received event for athlete who never authorized your app (should be rare)

**Solution:** This is expected behavior. Event is marked as processed to avoid retries.

## Architecture Summary

```
┌─────────────────────────────────────────────────────┐
│  Strava                                             │
│                                                     │
│  ONE subscription → Events for ALL authorized users │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ POST webhook event
                   │ (contains owner_id)
                   │
                   ▼
         ┌─────────────────┐
         │  webhook Lambda │ ← Fast responder
         │  Queue to SQS   │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  SQS Queue      │ ← Durability & retry
         └────────┬────────┘
                  │
                  ▼
    ┌──────────────────────────┐
    │  webhook_processor       │
    │  - Lookup owner_id       │ ← Works for any user
    │  - Fetch activity        │
    │  - Store in DB           │
    └──────────┬───────────────┘
               │
               ▼
    ┌─────────────────────┐
    │  Database           │
    │  - users            │
    │  - activities       │
    │  - webhook_events   │
    └─────────────────────┘
```

## Key Takeaways

✅ **No per-user webhook management needed**
   - One subscription covers all users
   - Automatic for new signups

✅ **New users immediately covered**
   - As soon as they authorize the app
   - First activity will trigger webhook

✅ **System is user-agnostic**
   - webhook_processor looks up any owner_id
   - Works for all authorized users

✅ **No code changes needed**
   - Current implementation is correct
   - Architecture supports unlimited users

## Reference Documentation

- **WEBHOOK_SETUP.md** - Complete setup guide
- **WEBHOOK_IMPLEMENTATION_SUMMARY.md** - Technical details
- **Strava API Docs** - https://developers.strava.com/docs/webhooks/

## Maintenance

The only maintenance required:

1. **Monitor subscription status** (should remain active indefinitely)
2. **Check CloudWatch logs** for errors
3. **Monitor SQS queue depth** (should stay near 0)
4. **Verify database connectivity** for webhook_processor

No per-user maintenance or configuration needed!
