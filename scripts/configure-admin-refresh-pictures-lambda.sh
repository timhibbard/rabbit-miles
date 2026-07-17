#!/bin/bash
# Configuration script for admin_refresh_pictures Lambda
# This script sets the appropriate timeout and memory settings

set -e

LAMBDA_NAME="rabbitmiles-admin-refresh-pictures"
TIMEOUT=600  # 10 minutes - enough time to fetch one profile per user (and wait out a rate-limit window if hit)
MEMORY=256   # 256MB - light workload, one Strava GET + one UPDATE per user

echo "========================================"
echo "Configuring Lambda: $LAMBDA_NAME"
echo "========================================"
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI first."
    exit 1
fi

echo "Setting Lambda configuration:"
echo "  Timeout: ${TIMEOUT}s (10 minutes)"
echo "  Memory: ${MEMORY}MB"
echo ""

# Update Lambda configuration
OUTPUT=$(aws lambda update-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --timeout "$TIMEOUT" \
  --memory-size "$MEMORY" 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Failed to update Lambda configuration"
    echo ""
    echo "Error details:"
    echo "$OUTPUT"
    echo ""
    echo "Possible causes:"
    echo "  - Lambda function doesn't exist"
    echo "  - AWS credentials don't have Lambda update permissions"
    echo "  - Function is currently being updated (wait 30 seconds and retry)"
    echo ""
    exit 1
fi

echo ""
echo "✅ Configuration updated successfully"
echo ""

# Verify the configuration
echo "📊 Current Lambda Configuration:"
aws lambda get-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --query '[FunctionName,Timeout,MemorySize,LastModified]' \
  --output table

echo ""
echo "========================================"
echo "✅ Configuration Complete"
echo "========================================"
