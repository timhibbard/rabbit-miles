#!/bin/bash
# Deployment Verification Script for user_update_activities Lambda
# This script helps verify that the correct code is deployed to AWS

set -e

LAMBDA_NAME="rabbitmiles-user-update-activities"
EXPECTED_MIN_SIZE=16000

echo "========================================"
echo "Verifying Lambda Deployment"
echo "========================================"
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI first."
    exit 1
fi

echo "Checking Lambda: $LAMBDA_NAME"
echo ""

# Get Lambda configuration
echo "📊 Lambda Configuration:"
aws lambda get-function \
  --function-name "$LAMBDA_NAME" \
  --query 'Configuration.[FunctionName,LastModified,CodeSize,Runtime,Handler,Timeout,MemorySize]' \
  --output table

echo ""

# Get code size
CODE_SIZE=$(aws lambda get-function \
  --function-name "$LAMBDA_NAME" \
  --query 'Configuration.CodeSize' \
  --output text)

echo "📦 Code Size: $CODE_SIZE bytes"
echo "✓ Expected: >$EXPECTED_MIN_SIZE bytes"
echo ""

# Verify code size
if [ "$CODE_SIZE" -lt "$EXPECTED_MIN_SIZE" ]; then
    echo "❌ DEPLOYMENT ISSUE DETECTED!"
    echo ""
    echo "The deployed code size ($CODE_SIZE bytes) is significantly smaller than expected (>$EXPECTED_MIN_SIZE bytes)."
    echo "This indicates the Lambda is running old code that predates PR #217."
    echo ""
    echo "🔧 To fix:"
    echo "  1. Deploy the Lambda using GitHub Actions:"
    echo "     - Merge this PR to main branch, OR"
    echo "     - Manually trigger 'Deploy Lambda Functions' workflow"
    echo ""
    echo "  2. Or deploy manually:"
    echo "     cd backend/user_update_activities"
    echo "     zip -r function.zip lambda_function.py"
    echo "     aws lambda update-function-code \\"
    echo "       --function-name $LAMBDA_NAME \\"
    echo "       --zip-file fileb://function.zip"
    echo ""
    exit 1
else
    echo "✅ Code size looks correct!"
fi

echo ""
echo "🔐 Environment Variables:"
REQUIRED_VARS=("DB_CLUSTER_ARN" "DB_SECRET_ARN" "APP_SECRET" "FRONTEND_URL" "STRAVA_CLIENT_ID" "STRAVA_CLIENT_SECRET")

for var in "${REQUIRED_VARS[@]}"; do
    value=$(aws lambda get-function-configuration \
      --function-name "$LAMBDA_NAME" \
      --query "Environment.Variables.$var" \
      --output text 2>/dev/null)
    
    if [ "$value" = "None" ] || [ -z "$value" ]; then
        echo "  ❌ $var: NOT SET"
    else
        echo "  ✅ $var: SET"
    fi
done

echo ""
echo "📝 CloudWatch Log Group:"
LOG_GROUP="/aws/lambda/$LAMBDA_NAME"
echo "  $LOG_GROUP"
echo ""
echo "To tail logs:"
echo "  aws logs tail $LOG_GROUP --follow"
echo ""

echo "========================================"
echo "✅ Verification Complete"
echo "========================================"
