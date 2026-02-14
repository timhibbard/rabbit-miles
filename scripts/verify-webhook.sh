#!/bin/bash

# Strava Webhook Verification Script
# This script verifies that the Strava webhook subscription is properly configured
# and working for all users (including new signups)
#
# SECURITY NOTE: This script uses Strava's API which requires credentials in GET parameters.
# Credentials may appear in command history, process listings (ps), or logs.
# This is a VERIFICATION/DEBUGGING tool only - not for production monitoring.
# For production monitoring, use AWS Lambda with Secrets Manager instead.
#
# Configuration (can be overridden via environment variables):
# - WEBHOOK_LAMBDA: webhook Lambda function name (default: rabbitmiles-webhook)
# - PROCESSOR_LAMBDA: webhook_processor Lambda function name (default: rabbitmiles-webhook-processor)
# - QUEUE_DEPTH_ERROR: Queue depth threshold for errors (default: 100)
# - QUEUE_DEPTH_WARN: Queue depth threshold for warnings (default: 10)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Strava Webhook Verification Script"
echo "========================================"
echo ""

# Function to print colored status
print_status() {
    local status=$1
    local message=$2
    case $status in
        "ok")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "warn")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        "error")
            echo -e "${RED}✗${NC} $message"
            ;;
        "info")
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
    esac
}

# Function to check if required command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_status "error" "$1 is not installed"
        return 1
    fi
    return 0
}

# Check required commands
print_status "info" "Checking required tools..."
check_command "aws" || exit 1
check_command "curl" || exit 1
check_command "jq" || exit 1

echo ""
print_status "ok" "All required tools are available"
echo ""

# Check if AWS credentials are configured
print_status "info" "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    print_status "error" "AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi
print_status "ok" "AWS credentials configured"
echo ""

# Get Lambda function names
WEBHOOK_LAMBDA=${WEBHOOK_LAMBDA:-"rabbitmiles-webhook"}
PROCESSOR_LAMBDA=${PROCESSOR_LAMBDA:-"rabbitmiles-webhook-processor"}

# Queue depth thresholds (configurable via environment)
QUEUE_DEPTH_ERROR=${QUEUE_DEPTH_ERROR:-100}
QUEUE_DEPTH_WARN=${QUEUE_DEPTH_WARN:-10}

echo "========================================"
echo "1. Checking Lambda Functions"
echo "========================================"
echo ""

# Check webhook Lambda
print_status "info" "Checking $WEBHOOK_LAMBDA..."
if aws lambda get-function --function-name "$WEBHOOK_LAMBDA" &> /dev/null; then
    print_status "ok" "webhook Lambda exists"
    
    # Check environment variables
    WEBHOOK_ENV=$(aws lambda get-function-configuration --function-name "$WEBHOOK_LAMBDA" --query 'Environment.Variables' 2>/dev/null)
    
    if echo "$WEBHOOK_ENV" | jq -e '.WEBHOOK_VERIFY_TOKEN' &> /dev/null; then
        print_status "ok" "WEBHOOK_VERIFY_TOKEN is set"
    else
        print_status "error" "WEBHOOK_VERIFY_TOKEN is not set"
    fi
    
    if echo "$WEBHOOK_ENV" | jq -e '.WEBHOOK_SQS_QUEUE_URL' &> /dev/null; then
        QUEUE_URL=$(echo "$WEBHOOK_ENV" | jq -r '.WEBHOOK_SQS_QUEUE_URL')
        print_status "ok" "WEBHOOK_SQS_QUEUE_URL is set: $QUEUE_URL"
    else
        print_status "error" "WEBHOOK_SQS_QUEUE_URL is not set"
    fi
else
    print_status "error" "$WEBHOOK_LAMBDA does not exist"
fi
echo ""

# Check webhook_processor Lambda
print_status "info" "Checking $PROCESSOR_LAMBDA..."
if aws lambda get-function --function-name "$PROCESSOR_LAMBDA" &> /dev/null; then
    print_status "ok" "webhook_processor Lambda exists"
    
    # Check environment variables
    PROCESSOR_ENV=$(aws lambda get-function-configuration --function-name "$PROCESSOR_LAMBDA" --query 'Environment.Variables' 2>/dev/null)
    
    REQUIRED_VARS=("DB_CLUSTER_ARN" "DB_SECRET_ARN" "DB_NAME" "STRAVA_CLIENT_ID")
    for var in "${REQUIRED_VARS[@]}"; do
        if echo "$PROCESSOR_ENV" | jq -e ".$var" &> /dev/null; then
            print_status "ok" "$var is set"
        else
            print_status "error" "$var is not set"
        fi
    done
    
    # Check for either STRAVA_CLIENT_SECRET or STRAVA_SECRET_ARN
    if echo "$PROCESSOR_ENV" | jq -e '.STRAVA_CLIENT_SECRET' &> /dev/null; then
        print_status "ok" "STRAVA_CLIENT_SECRET is set"
    elif echo "$PROCESSOR_ENV" | jq -e '.STRAVA_SECRET_ARN' &> /dev/null; then
        print_status "ok" "STRAVA_SECRET_ARN is set"
    else
        print_status "error" "Neither STRAVA_CLIENT_SECRET nor STRAVA_SECRET_ARN is set"
    fi
else
    print_status "error" "$PROCESSOR_LAMBDA does not exist"
fi
echo ""

echo "========================================"
echo "2. Checking Strava Webhook Subscription"
echo "========================================"
echo ""

# Check if credentials are in environment
if [ -z "$STRAVA_CLIENT_ID" ] || [ -z "$STRAVA_CLIENT_SECRET" ]; then
    print_status "warn" "STRAVA_CLIENT_ID or STRAVA_CLIENT_SECRET not set in environment"
    print_status "info" "Set these variables to check subscription status:"
    echo "  export STRAVA_CLIENT_ID=your_client_id"
    echo "  export STRAVA_CLIENT_SECRET=your_client_secret"
    echo ""
    print_status "warn" "SECURITY NOTE: Strava API requires credentials in GET request parameters"
    print_status "warn" "Credentials may appear in logs. Use this script for verification only."
    echo ""
else
    print_status "info" "Checking Strava subscription..."
    print_status "warn" "SECURITY: Strava API requires credentials in GET parameters (may appear in logs)"
    
    # Note: This uses Strava's documented API endpoint which requires GET with credentials
    # The credentials are passed as URL parameters as required by Strava's API design
    # Limitations:
    # - Credentials appear in process listings (`ps aux`) while curl is running
    # - Credentials may appear in command history (we disable history temporarily)
    # - Credentials may appear in system logs
    # For production monitoring, use AWS Lambda with Secrets Manager to query subscription status
    # This script is intended for verification/debugging only, not production use
    
    # Temporarily disable command history for this command (bash-specific)
    set +o history 2>/dev/null || true
    
    SUBSCRIPTION_RESPONSE=$(curl -s -G https://www.strava.com/api/v3/push_subscriptions \
        -d "client_id=$STRAVA_CLIENT_ID" \
        -d "client_secret=$STRAVA_CLIENT_SECRET")
    CURL_EXIT_CODE=$?
    
    # Re-enable command history
    set -o history 2>/dev/null || true
    
    # Check if curl succeeded
    if [ $CURL_EXIT_CODE -ne 0 ]; then
        print_status "error" "Failed to connect to Strava API (curl exit code: $CURL_EXIT_CODE)"
        print_status "info" "Check network connectivity and Strava API status"
        echo ""
    elif ! echo "$SUBSCRIPTION_RESPONSE" | jq empty 2>/dev/null; then
        print_status "error" "Strava API returned invalid JSON response"
        print_status "info" "Response: $SUBSCRIPTION_RESPONSE"
        echo ""
    elif echo "$SUBSCRIPTION_RESPONSE" | jq -e '.message' &> /dev/null; then
        ERROR_MSG=$(echo "$SUBSCRIPTION_RESPONSE" | jq -r '.message')
        print_status "error" "Strava API error: $ERROR_MSG"
        print_status "info" "Check your STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET"
        echo ""
    
    if echo "$SUBSCRIPTION_RESPONSE" | jq -e '. | length > 0' &> /dev/null; then
        SUBSCRIPTION_COUNT=$(echo "$SUBSCRIPTION_RESPONSE" | jq '. | length')
        print_status "ok" "Found $SUBSCRIPTION_COUNT active webhook subscription(s)"
        
        # Show subscription details
        echo "$SUBSCRIPTION_RESPONSE" | jq -r '.[] | "  ID: \(.id)\n  Callback: \(.callback_url)\n  Created: \(.created_at)"'
        echo ""
        
        # Verify callback URL
        CALLBACK_URL=$(echo "$SUBSCRIPTION_RESPONSE" | jq -r '.[0].callback_url')
        if [[ "$CALLBACK_URL" == *"/strava/webhook" ]]; then
            print_status "ok" "Callback URL looks correct"
        else
            print_status "warn" "Callback URL may be incorrect: $CALLBACK_URL"
            print_status "info" "Expected format: https://your-domain/strava/webhook"
        fi
    else
        print_status "error" "No webhook subscriptions found"
        print_status "info" "Create a subscription using the command in WEBHOOK_SETUP.md"
    fi
fi
echo ""

echo "========================================"
echo "3. Checking SQS Queue"
echo "========================================"
echo ""

if [ -n "$QUEUE_URL" ]; then
    print_status "info" "Checking SQS queue..."
    
    # Get queue attributes
    if QUEUE_ATTRS=$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names All 2>/dev/null); then
        print_status "ok" "Queue is accessible"
        
        # Check queue depth
        MSG_AVAILABLE=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages')
        MSG_IN_FLIGHT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')
        
        echo "  Messages available: $MSG_AVAILABLE"
        echo "  Messages in flight: $MSG_IN_FLIGHT"
        
        if [ "$MSG_AVAILABLE" -gt "$QUEUE_DEPTH_ERROR" ]; then
            print_status "error" "Queue depth ($MSG_AVAILABLE) exceeds error threshold ($QUEUE_DEPTH_ERROR) - processing may be stalled"
            print_status "info" "Check webhook_processor Lambda logs for errors"
        elif [ "$MSG_AVAILABLE" -gt "$QUEUE_DEPTH_WARN" ]; then
            print_status "warn" "Queue has $MSG_AVAILABLE messages - monitor for continued growth"
        else
            print_status "ok" "Queue depth is healthy"
        fi
        
        # Check if it's a FIFO queue
        if [[ "$QUEUE_URL" == *".fifo" ]]; then
            print_status "ok" "Queue is FIFO (ensures ordered processing)"
        else
            print_status "warn" "Queue is not FIFO (events may be processed out of order)"
        fi
    else
        print_status "error" "Cannot access queue at $QUEUE_URL"
    fi
else
    print_status "warn" "Queue URL not available, skipping SQS checks"
fi
echo ""

echo "========================================"
echo "4. Checking Event Source Mapping"
echo "========================================"
echo ""

print_status "info" "Checking if SQS triggers webhook_processor Lambda..."

EVENT_MAPPINGS=$(aws lambda list-event-source-mappings --function-name "$PROCESSOR_LAMBDA" 2>/dev/null)

if echo "$EVENT_MAPPINGS" | jq -e '.EventSourceMappings | length > 0' &> /dev/null; then
    MAPPING_COUNT=$(echo "$EVENT_MAPPINGS" | jq '.EventSourceMappings | length')
    print_status "ok" "Found $MAPPING_COUNT event source mapping(s)"
    
    # Check mapping state
    MAPPING_STATE=$(echo "$EVENT_MAPPINGS" | jq -r '.EventSourceMappings[0].State')
    if [ "$MAPPING_STATE" == "Enabled" ]; then
        print_status "ok" "Event source mapping is Enabled"
    else
        print_status "error" "Event source mapping is $MAPPING_STATE (should be Enabled)"
    fi
    
    # Check batch size
    BATCH_SIZE=$(echo "$EVENT_MAPPINGS" | jq -r '.EventSourceMappings[0].BatchSize')
    echo "  Batch size: $BATCH_SIZE"
    if [ "$BATCH_SIZE" -gt 1 ]; then
        print_status "ok" "Batch processing enabled (efficient)"
    fi
else
    print_status "error" "No event source mappings found"
    print_status "info" "webhook_processor will not be triggered by SQS events"
    print_status "info" "Create mapping using:"
    if [ -n "$QUEUE_URL" ]; then
        # Extract queue ARN from URL for the example command
        # Queue URL format: https://sqs.region.amazonaws.com/account/queue-name.fifo
        QUEUE_ARN=$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text 2>/dev/null || echo "QUEUE_ARN")
        echo "  aws lambda create-event-source-mapping \\"
        echo "    --function-name $PROCESSOR_LAMBDA \\"
        echo "    --event-source-arn $QUEUE_ARN \\"
        echo "    --batch-size 10"
    else
        echo "  See WEBHOOK_SETUP.md section 5 for complete setup instructions"
    fi
fi
echo ""

echo "========================================"
echo "5. Summary"
echo "========================================"
echo ""

print_status "info" "How Strava Webhooks Work for New Users:"
echo ""
echo "  1. Strava webhooks are APPLICATION-LEVEL, not per-user"
echo "  2. ONE subscription covers ALL users (existing + new)"
echo "  3. When new user authorizes app:"
echo "     → auth_callback stores their credentials"
echo "     → Webhook automatically receives their activity events"
echo "     → No additional configuration needed"
echo ""
echo "  4. When new user creates activity:"
echo "     → Strava sends webhook event with owner_id (athlete ID)"
echo "     → webhook Lambda queues event to SQS"
echo "     → webhook_processor looks up user by owner_id"
echo "     → Activity is fetched and stored"
echo ""

print_status "ok" "New users are automatically covered by existing webhook subscription"
echo ""

if [ -z "$STRAVA_CLIENT_ID" ] || [ -z "$STRAVA_CLIENT_SECRET" ]; then
    echo "To verify webhook subscription status, set:"
    echo "  export STRAVA_CLIENT_ID=your_client_id"
    echo "  export STRAVA_CLIENT_SECRET=your_client_secret"
    echo "Then run this script again."
    echo ""
fi

echo "For detailed documentation, see:"
echo "  - WEBHOOK_NEW_USERS.md - How webhooks work for new users"
echo "  - WEBHOOK_SETUP.md - Complete setup guide"
echo ""

print_status "info" "Verification complete!"
