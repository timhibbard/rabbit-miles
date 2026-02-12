#!/bin/bash
# Deployment Verification Script for user_update_activities Lambda
# This script helps verify that the correct code is deployed to AWS

set -e

LAMBDA_NAME="rabbitmiles-user-update-activities"
EXPECTED_MIN_SIZE=4000  # Compressed size (17KB uncompressed becomes ~4.8KB compressed)
EXPECTED_TIMEOUT=60     # Should be 60 seconds
EXPECTED_MEMORY=256     # Should be 256 MB

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

# Get timeout
TIMEOUT=$(aws lambda get-function \
  --function-name "$LAMBDA_NAME" \
  --query 'Configuration.Timeout' \
  --output text)

# Get memory
MEMORY=$(aws lambda get-function \
  --function-name "$LAMBDA_NAME" \
  --query 'Configuration.MemorySize' \
  --output text)

echo "📦 Code Size: $CODE_SIZE bytes (compressed)"
echo "   Expected: >$EXPECTED_MIN_SIZE bytes"
echo "⏱️  Timeout: ${TIMEOUT}s"
echo "   Expected: ${EXPECTED_TIMEOUT}s"
echo "💾 Memory: ${MEMORY}MB"
echo "   Expected: ${EXPECTED_MEMORY}MB"
echo ""

# Verify code size
if [ "$CODE_SIZE" -lt "$EXPECTED_MIN_SIZE" ]; then
    echo "❌ DEPLOYMENT ISSUE DETECTED!"
    echo ""
    echo "The deployed code size ($CODE_SIZE bytes) is significantly smaller than expected (>$EXPECTED_MIN_SIZE bytes)."
    echo "This indicates the Lambda may be running old code."
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

# Verify timeout
if [ "$TIMEOUT" -lt "$EXPECTED_TIMEOUT" ]; then
    echo "⚠️  WARNING: Timeout is too low!"
    echo ""
    echo "   Current: ${TIMEOUT}s"
    echo "   Expected: ${EXPECTED_TIMEOUT}s"
    echo ""
    echo "   A low timeout can cause 500 errors when the Lambda times out during:"
    echo "   - Strava token refresh"
    echo "   - Fetching activities from Strava API"
    echo "   - Storing activities in the database"
    echo ""
    echo "🔧 To fix:"
    echo "  Run: ./scripts/configure-user-update-activities-lambda.sh"
    echo "  Or manually:"
    echo "    aws lambda update-function-configuration \\"
    echo "      --function-name $LAMBDA_NAME \\"
    echo "      --timeout $EXPECTED_TIMEOUT"
    echo ""
    exit 1
else
    echo "✅ Timeout configuration looks correct!"
fi

# Verify memory
if [ "$MEMORY" -lt "$EXPECTED_MEMORY" ]; then
    echo "⚠️  WARNING: Memory is too low!"
    echo ""
    echo "   Current: ${MEMORY}MB"
    echo "   Expected: ${EXPECTED_MEMORY}MB"
    echo ""
    echo "🔧 To fix:"
    echo "  Run: ./scripts/configure-user-update-activities-lambda.sh"
    echo "  Or manually:"
    echo "    aws lambda update-function-configuration \\"
    echo "      --function-name $LAMBDA_NAME \\"
    echo "      --memory-size $EXPECTED_MEMORY"
    echo ""
    exit 1
else
    echo "✅ Memory configuration looks correct!"
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
