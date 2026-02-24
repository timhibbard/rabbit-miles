#!/bin/bash
# Configuration script for admin_recalculate_leaderboard Lambda
# This script sets the appropriate timeout and memory settings

set -e

LAMBDA_NAME="rabbitmiles-admin-recalculate-leaderboard"
TIMEOUT=600  # 10 minutes - enough time to process many activities
MEMORY=1024  # 1024MB - sufficient for processing large datasets

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
