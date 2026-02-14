# Strava Webhook Setup Guide

This document describes how to set up Strava webhooks to receive real-time activity updates.

> **Note:** Wondering if new users are automatically covered by webhooks? See [WEBHOOK_NEW_USERS.md](WEBHOOK_NEW_USERS.md) for details on how webhooks work at the application level.

## Architecture Overview

The webhook implementation uses AWS services for scalability and reliability:

```
Strava API → API Gateway → webhook Lambda → SQS Queue → webhook_processor Lambda → RDS Database
```

### Components:

1. **API Gateway (HTTP API)**: Public HTTPS endpoint that Strava calls
   - Route: `GET /strava/webhook` - Subscription validation
   - Route: `POST /strava/webhook` - Event delivery

2. **webhook Lambda**: Fast responder (<2 seconds)
   - Validates subscription requests
   - Queues events to SQS
   - Returns 200 OK immediately

3. **SQS Queue**: Message queue for async processing
   - Provides durability and retry logic
   - Decouples webhook receipt from processing

4. **webhook_processor Lambda**: Processes events asynchronously
   - Fetches activity details from Strava API
   - Updates database
   - Handles token refresh
   - Implements idempotency

5. **RDS Database**: Stores activities and processed events

## AWS Setup

### 1. Create SQS Queue

Create a FIFO queue for ordered processing and deduplication:

```bash
aws sqs create-queue \
  --queue-name rabbitmiles-webhook-events.fifo \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "MessageRetentionPeriod": "1209600",
    "VisibilityTimeout": "300"
  }'
```

Note the Queue URL for later configuration.

### 2. Create Dead Letter Queue (Optional but Recommended)

```bash
aws sqs create-queue \
  --queue-name rabbitmiles-webhook-dlq.fifo \
  --attributes '{
    "FifoQueue": "true",
    "MessageRetentionPeriod": "1209600"
  }'
```

Configure the main queue to use the DLQ:

```bash
aws sqs set-queue-attributes \
  --queue-url <MAIN_QUEUE_URL> \
  --attributes '{
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"<DLQ_ARN>\",\"maxReceiveCount\":\"3\"}"
  }'
```

### 3. Deploy Lambda Functions

Deploy both Lambda functions:

```bash
# Deploy webhook handler
cd backend/webhook
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-webhook \
  --zip-file fileb://function.zip

# Deploy webhook processor
cd ../webhook_processor
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name rabbitmiles-webhook-processor \
  --zip-file fileb://function.zip
```

### 4. Configure Environment Variables

#### webhook Lambda:
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-webhook \
  --environment Variables='{
    "WEBHOOK_VERIFY_TOKEN": "your-secret-verify-token",
    "WEBHOOK_SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789/rabbitmiles-webhook-events.fifo"
  }'
```

#### webhook_processor Lambda:
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-webhook-processor \
  --environment Variables='{
    "DB_CLUSTER_ARN": "arn:aws:rds:us-east-1:...",
    "DB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:...",
    "DB_NAME": "postgres",
    "STRAVA_CLIENT_ID": "your-client-id",
    "STRAVA_CLIENT_SECRET": "your-client-secret"
  }'
```

### 5. Configure SQS Trigger

Set up the webhook_processor Lambda to be triggered by SQS:

```bash
aws lambda create-event-source-mapping \
  --function-name rabbitmiles-webhook-processor \
  --event-source-arn <QUEUE_ARN> \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5
```

### 6. Configure API Gateway

Add routes to your API Gateway HTTP API:

1. **GET /strava/webhook**
   - Integration: Lambda proxy to webhook function
   - No authentication required

2. **POST /strava/webhook**
   - Integration: Lambda proxy to webhook function
   - No authentication required

### 7. Set IAM Permissions

Ensure Lambda functions have appropriate permissions:

#### webhook Lambda permissions:
- SQS: `SendMessage` on the webhook queue

#### webhook_processor Lambda permissions:
- RDS Data API: `ExecuteStatement` on the database cluster
- Secrets Manager: `GetSecretValue` on Strava credentials secret
- SQS: `ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes` on the webhook queue

### 8. Run Database Migration

Apply the webhook_events table migration:

```sql
-- Run backend/migrations/004_create_webhook_events_table.sql
```

## Strava Subscription Setup

### 1. Create Webhook Subscription

Use curl or a tool like Postman:

```bash
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -F client_id=YOUR_CLIENT_ID \
  -F client_secret=YOUR_CLIENT_SECRET \
  -F callback_url=https://YOUR_API_GATEWAY_URL/strava/webhook \
  -F verify_token=your-secret-verify-token
```

The response will include a subscription ID:

```json
{
  "id": 123456
}
```

Save this ID for future reference.

### 2. Verify Subscription

Check your subscription status:

```bash
curl -G https://www.strava.com/api/v3/push_subscriptions \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET
```

### 3. Test Webhook

Test with a manual POST to your callback URL:

```bash
curl -X POST https://YOUR_API_GATEWAY_URL/strava/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "aspect_type": "create",
    "event_time": 1549560669,
    "object_id": 1234567890,
    "object_type": "activity",
    "owner_id": 9999999,
    "subscription_id": 123456
  }'
```

Check CloudWatch Logs to verify the event was processed.

## Verification

Run the webhook verification script to check your configuration:

```bash
# Export your Strava credentials (optional but recommended)
export STRAVA_CLIENT_ID=your_client_id
export STRAVA_CLIENT_SECRET=your_client_secret

# Run verification script
./scripts/verify-webhook.sh
```

The script will check:
- Lambda functions exist and are configured
- Required environment variables are set
- Strava webhook subscription is active
- SQS queue is healthy
- Event source mapping is enabled

For more details on how webhooks work for new users, see [WEBHOOK_NEW_USERS.md](WEBHOOK_NEW_USERS.md).

## Environment Variables Reference

### webhook Lambda:
- `WEBHOOK_VERIFY_TOKEN` (required): Secret token for subscription validation
- `WEBHOOK_SQS_QUEUE_URL` (required): URL of the SQS queue for event processing

### webhook_processor Lambda:
- `DB_CLUSTER_ARN` (required): Aurora cluster ARN
- `DB_SECRET_ARN` (required): Database credentials secret ARN
- `DB_NAME` (required): Database name (default: "postgres")
- `STRAVA_CLIENT_ID` (required): Strava API client ID
- `STRAVA_CLIENT_SECRET` (required): Strava API client secret
- `STRAVA_SECRET_ARN` (optional): Alternative to client_id/secret env vars

## Monitoring

### CloudWatch Logs

Monitor Lambda execution logs:

```bash
# webhook Lambda logs
aws logs tail /aws/lambda/rabbitmiles-webhook --follow

# webhook_processor Lambda logs
aws logs tail /aws/lambda/rabbitmiles-webhook-processor --follow
```

### SQS Metrics

Monitor queue depth and processing:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=rabbitmiles-webhook-events.fifo \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### Dead Letter Queue

Check for failed messages:

```bash
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --max-number-of-messages 10
```

## Troubleshooting

### Subscription Creation Fails

1. Verify callback URL is accessible from the internet
2. Check that webhook Lambda has `WEBHOOK_VERIFY_TOKEN` configured
3. Test GET request manually:
   ```bash
   curl -X GET 'https://YOUR_API_GATEWAY_URL/strava/webhook?hub.verify_token=your-secret-verify-token&hub.challenge=test123&hub.mode=subscribe'
   ```
4. Should return: `{"hub.challenge":"test123"}`

### Events Not Being Processed

1. Check SQS queue has messages
2. Verify webhook_processor Lambda is triggered by SQS
3. Check CloudWatch Logs for errors
4. Verify database connectivity and credentials

### Duplicate Events

1. Ensure SQS queue is configured as FIFO
2. Check webhook_events table for idempotency records
3. Verify MessageDeduplicationId is being set correctly

### Token Refresh Failures

1. Check user has valid refresh_token in database
2. Verify Strava client credentials are correct
3. Check token expiration logic (5-minute buffer)

## Deleting a Subscription

To delete a webhook subscription:

```bash
curl -X DELETE "https://www.strava.com/api/v3/push_subscriptions/SUBSCRIPTION_ID?client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"
```

## Security Considerations

1. **Verify Token**: Always use a strong, random verify_token
2. **Rate Limiting**: Consider adding API Gateway rate limiting
3. **Logging**: Monitor for unusual patterns or excessive events
4. **Secrets**: Store all secrets in AWS Secrets Manager or Parameter Store
5. **IAM**: Use least-privilege IAM policies for Lambda functions
6. **VPC**: Consider placing webhook_processor in VPC if database requires it

## Cost Optimization

1. Use SQS batch processing (10 messages per invocation)
2. Set appropriate SQS visibility timeout (5 minutes)
3. Configure dead letter queue to avoid infinite retries
4. Monitor CloudWatch metrics for optimization opportunities
