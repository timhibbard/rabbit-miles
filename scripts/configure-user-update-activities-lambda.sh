#!/bin/bash
# Configuration script for user_update_activities Lambda
# This script sets the appropriate timeout and memory settings

set -e

LAMBDA_NAME="rabbitmiles-user-update-activities"
TIMEOUT=60  # 60 seconds - enough time for token refresh + API calls + DB operations
MEMORY=256  # 256MB - sufficient for the operation

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
echo "  Timeout: ${TIMEOUT}s"
echo "  Memory: ${MEMORY}MB"
echo ""

# Update Lambda configuration
aws lambda update-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --timeout "$TIMEOUT" \
  --memory-size "$MEMORY"

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
