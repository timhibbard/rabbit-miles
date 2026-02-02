#!/bin/bash
# Quick setup script for Strava webhook infrastructure
# This script helps create the necessary AWS resources for webhook processing

set -e

echo "🚀 RabbitMiles Webhook Setup Script"
echo "===================================="
echo ""

# Check for required tools
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI not found. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ Error: AWS credentials not configured."
    echo "Please run: aws configure"
    exit 1
fi

echo "✅ AWS CLI configured"
echo ""

# Get AWS region
AWS_REGION=${AWS_REGION:-us-east-1}
echo "Using AWS region: $AWS_REGION"
echo ""

# Generate a secure verify token if not provided
VERIFY_TOKEN=${WEBHOOK_VERIFY_TOKEN:-$(openssl rand -hex 32)}
echo "Verify token: $VERIFY_TOKEN"
echo "⚠️  Save this token - you'll need it for Strava subscription creation"
echo ""

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $ACCOUNT_ID"
echo ""

# Step 1: Create SQS FIFO Queue
echo "📬 Creating SQS FIFO queue..."
QUEUE_NAME="rabbitmiles-webhook-events.fifo"

if aws sqs get-queue-url --queue-name "$QUEUE_NAME" &> /dev/null; then
    echo "Queue already exists: $QUEUE_NAME"
    QUEUE_URL=$(aws sqs get-queue-url --queue-name "$QUEUE_NAME" --query QueueUrl --output text)
else
    QUEUE_URL=$(aws sqs create-queue \
        --queue-name "$QUEUE_NAME" \
        --attributes '{
            "FifoQueue": "true",
            "ContentBasedDeduplication": "false",
            "MessageRetentionPeriod": "1209600",
            "VisibilityTimeout": "300"
        }' \
        --region "$AWS_REGION" \
        --query QueueUrl \
        --output text)
    echo "✅ Created queue: $QUEUE_URL"
fi

QUEUE_ARN="arn:aws:sqs:$AWS_REGION:$ACCOUNT_ID:$QUEUE_NAME"
echo "Queue ARN: $QUEUE_ARN"
echo ""

# Step 2: Create Dead Letter Queue
echo "💀 Creating Dead Letter Queue..."
DLQ_NAME="rabbitmiles-webhook-dlq.fifo"

if aws sqs get-queue-url --queue-name "$DLQ_NAME" &> /dev/null; then
    echo "DLQ already exists: $DLQ_NAME"
    DLQ_URL=$(aws sqs get-queue-url --queue-name "$DLQ_NAME" --query QueueUrl --output text)
else
    DLQ_URL=$(aws sqs create-queue \
        --queue-name "$DLQ_NAME" \
        --attributes '{
            "FifoQueue": "true",
            "MessageRetentionPeriod": "1209600"
        }' \
        --region "$AWS_REGION" \
        --query QueueUrl \
        --output text)
    echo "✅ Created DLQ: $DLQ_URL"
fi

DLQ_ARN="arn:aws:sqs:$AWS_REGION:$ACCOUNT_ID:$DLQ_NAME"
echo "DLQ ARN: $DLQ_ARN"
echo ""

# Step 3: Configure DLQ on main queue
echo "🔗 Configuring Dead Letter Queue..."
aws sqs set-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}" \
    --region "$AWS_REGION"
echo "✅ DLQ configured"
echo ""

# Output summary
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Update Lambda environment variables:"
echo ""
echo "   webhook Lambda:"
echo "   - WEBHOOK_VERIFY_TOKEN=$VERIFY_TOKEN"
echo "   - WEBHOOK_SQS_QUEUE_URL=$QUEUE_URL"
echo ""
echo "2. Configure IAM permissions:"
echo "   - webhook Lambda needs: sqs:SendMessage on $QUEUE_ARN"
echo "   - webhook_processor Lambda needs: sqs:ReceiveMessage, sqs:DeleteMessage on $QUEUE_ARN"
echo ""
echo "3. Create event source mapping:"
echo ""
echo "   aws lambda create-event-source-mapping \\"
echo "     --function-name rabbitmiles-webhook-processor \\"
echo "     --event-source-arn $QUEUE_ARN \\"
echo "     --batch-size 10 \\"
echo "     --maximum-batching-window-in-seconds 5"
echo ""
echo "4. Create Strava webhook subscription:"
echo ""
echo "   curl -X POST https://www.strava.com/api/v3/push_subscriptions \\"
echo "     -F client_id=YOUR_CLIENT_ID \\"
echo "     -F client_secret=YOUR_CLIENT_SECRET \\"
echo "     -F callback_url=YOUR_API_GATEWAY_URL/strava/webhook \\"
echo "     -F verify_token=$VERIFY_TOKEN"
echo ""
echo "For detailed instructions, see WEBHOOK_SETUP.md"
echo ""
