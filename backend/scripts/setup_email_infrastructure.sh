#!/bin/bash
# Setup AWS infrastructure for email notifications
# Run this script to create SQS queue, SNS topic, and configure SES

set -e

# Configuration
QUEUE_NAME="rabbitmiles-email-notifications"
SNS_TOPIC_NAME="rabbitmiles-ses-bounces"
SES_CONFIG_SET="rabbitmiles-notifications"

# Auto-detect AWS region and account ID
AWS_REGION="${AWS_REGION:-$(aws configure get region)}"
if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
    echo "⚠️  No region configured, defaulting to us-east-1"
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "❌ ERROR: Could not determine AWS Account ID"
    echo "Please ensure AWS credentials are configured"
    exit 1
fi

echo "========================================="
echo "RabbitMiles Email Infrastructure Setup"
echo "========================================="
echo ""
echo "This script will create:"
echo "- SQS queue for email notifications"
echo "- SNS topic for bounce/complaint handling"
echo "- SES configuration set for tracking"
echo ""
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo ""

# Check for --yes flag to skip confirmation
if [[ "$1" != "--yes" && "$1" != "-y" ]]; then
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "=== Creating SQS Queue ==="

# Check if queue already exists
EXISTING_QUEUE_URL=$(aws sqs get-queue-url --queue-name $QUEUE_NAME --region $AWS_REGION --query 'QueueUrl' --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_QUEUE_URL" ]; then
    echo "ℹ️  Queue already exists: $EXISTING_QUEUE_URL"
    QUEUE_URL=$EXISTING_QUEUE_URL
else
    QUEUE_URL=$(aws sqs create-queue \
        --queue-name $QUEUE_NAME \
        --region $AWS_REGION \
        --attributes '{
            "MessageRetentionPeriod": "1209600",
            "VisibilityTimeout": "300",
            "ReceiveMessageWaitTimeSeconds": "0"
        }' \
        --query 'QueueUrl' \
        --output text)
    echo "✅ Created SQS queue: $QUEUE_URL"
fi

# Get queue ARN
QUEUE_ARN=$(aws sqs get-queue-attributes \
    --queue-url $QUEUE_URL \
    --attribute-names QueueArn \
    --region $AWS_REGION \
    --query 'Attributes.QueueArn' \
    --output text)

echo "✅ Queue ARN: $QUEUE_ARN"

echo ""
echo "=== Creating SNS Topic for Bounces ==="

# Check if topic already exists
EXISTING_TOPIC_ARN=$(aws sns list-topics --region $AWS_REGION --query "Topics[?contains(TopicArn, '$SNS_TOPIC_NAME')].TopicArn" --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_TOPIC_ARN" ]; then
    echo "ℹ️  Topic already exists: $EXISTING_TOPIC_ARN"
    SNS_TOPIC_ARN=$EXISTING_TOPIC_ARN
else
    SNS_TOPIC_ARN=$(aws sns create-topic \
        --name $SNS_TOPIC_NAME \
        --region $AWS_REGION \
        --query 'TopicArn' \
        --output text)
    echo "✅ Created SNS topic: $SNS_TOPIC_ARN"
fi

echo ""
echo "=== Creating SES Configuration Set ==="

# Check if configuration set exists
if aws sesv2 get-configuration-set --configuration-set-name $SES_CONFIG_SET --region $AWS_REGION >/dev/null 2>&1; then
    echo "ℹ️  Configuration set already exists: $SES_CONFIG_SET"
else
    aws sesv2 create-configuration-set \
        --configuration-set-name $SES_CONFIG_SET \
        --region $AWS_REGION
    echo "✅ Created SES configuration set: $SES_CONFIG_SET"
fi

echo ""
echo "=== Adding Event Destination to SES Config Set ==="

# Check if event destination exists
EXISTING_DESTINATION=$(aws sesv2 get-configuration-set-event-destinations \
    --configuration-set-name $SES_CONFIG_SET \
    --region $AWS_REGION \
    --query "EventDestinations[?Name=='bounce-complaints'].Name" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_DESTINATION" ]; then
    echo "ℹ️  Event destination already exists: bounce-complaints"
else
    aws sesv2 create-configuration-set-event-destination \
        --configuration-set-name $SES_CONFIG_SET \
        --event-destination-name bounce-complaints \
        --event-destination "{
            \"Enabled\": true,
            \"MatchingEventTypes\": [\"BOUNCE\", \"COMPLAINT\"],
            \"SnsDestination\": {
                \"TopicArn\": \"$SNS_TOPIC_ARN\"
            }
        }" \
        --region $AWS_REGION
    echo "✅ Added bounce/complaint event destination"
fi

echo ""
echo "========================================="
echo "✅ Infrastructure Setup Complete!"
echo "========================================="
echo ""
echo "📋 Created Resources:"
echo "   SQS Queue: $QUEUE_URL"
echo "   SNS Topic: $SNS_TOPIC_ARN"
echo "   SES Config Set: $SES_CONFIG_SET"
echo ""
echo "📝 Copy these values for Lambda environment variables:"
echo ""
echo "EMAIL_QUEUE_URL=$QUEUE_URL"
echo "SES_CONFIG_SET=$SES_CONFIG_SET"
echo ""
echo "========================================="
echo "🔧 Next Steps"
echo "========================================="
echo ""
echo "1. Update Lambda Environment Variables:"
echo "   • match_activity_trail: Add EMAIL_QUEUE_URL and FRONTEND_URL"
echo "   • send_email_notification: Add SES_CONFIG_SET"
echo ""
echo "2. Configure Lambda Triggers & Permissions:"
echo ""
echo "   Run these commands in CloudShell:"
echo ""
echo "   # Subscribe handle_email_bounces Lambda to SNS topic"
echo "   aws sns subscribe \\"
echo "     --topic-arn $SNS_TOPIC_ARN \\"
echo "     --protocol lambda \\"
echo "     --notification-endpoint arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:rabbitmiles-handle-email-bounces \\"
echo "     --region $AWS_REGION"
echo ""
echo "   # Grant SNS permission to invoke Lambda"
echo "   aws lambda add-permission \\"
echo "     --function-name rabbitmiles-handle-email-bounces \\"
echo "     --statement-id AllowSNSInvoke \\"
echo "     --action lambda:InvokeFunction \\"
echo "     --principal sns.amazonaws.com \\"
echo "     --source-arn $SNS_TOPIC_ARN \\"
echo "     --region $AWS_REGION"
echo ""
echo "3. Configure SQS Trigger on send_email_notification Lambda:"
echo "   • AWS Console → Lambda → send_email_notification"
echo "   • Add trigger → SQS"
echo "   • Queue: rabbitmiles-email-notifications"
echo "   • Batch size: 10"
echo ""
echo "4. Add IAM Permissions:"
echo "   • match_activity_trail: sqs:SendMessage"
echo "   • send_email_notification: sqs:ReceiveMessage, sqs:DeleteMessage, ses:SendEmail"
echo ""
echo "5. Verify SES Domain & Request Production Access"
echo ""
echo "📖 See: .claude/DEPLOYMENT_CHECKLIST.md for detailed instructions"
echo ""
