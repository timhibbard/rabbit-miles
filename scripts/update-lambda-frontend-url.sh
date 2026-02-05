#!/bin/bash
# Script to update FRONTEND_URL in Lambda functions for domain migration
# This script updates the FRONTEND_URL environment variable to match the new custom domain

set -e

NEW_FRONTEND_URL="https://rabbitmiles.com"

# List of Lambda functions that need CORS headers updated
FUNCTIONS_WITH_CORS=(
  "rabbitmiles-me"
  "rabbitmiles-get-activities"
  "rabbitmiles-get-activity-detail"
  "rabbitmiles-fetch-activities"
  "rabbitmiles-reset-last-matched"
)

echo "Updating FRONTEND_URL to: $NEW_FRONTEND_URL"
echo "=========================================="

for FUNC_NAME in "${FUNCTIONS_WITH_CORS[@]}"; do
  echo ""
  echo "Processing: $FUNC_NAME"
  
  # Fetch current configuration
  CURRENT_CONFIG=$(aws lambda get-function-configuration \
    --function-name "$FUNC_NAME" \
    --query 'Environment.Variables' \
    --output json 2>/dev/null || echo "{}")
  
  if [ "$CURRENT_CONFIG" == "{}" ]; then
    echo "  ⚠️  Function not found or no environment variables configured"
    continue
  fi
  
  # Check current FRONTEND_URL value
  CURRENT_URL=$(echo "$CURRENT_CONFIG" | jq -r '.FRONTEND_URL // "not set"')
  echo "  Current FRONTEND_URL: $CURRENT_URL"
  
  if [ "$CURRENT_URL" == "$NEW_FRONTEND_URL" ]; then
    echo "  ✓ Already up to date"
    continue
  fi
  
  # Merge new value into existing variables
  UPDATED_CONFIG=$(echo "$CURRENT_CONFIG" | jq --arg url "$NEW_FRONTEND_URL" '. + {FRONTEND_URL: $url}')
  
  # Apply update
  echo "  → Updating to: $NEW_FRONTEND_URL"
  aws lambda update-function-configuration \
    --function-name "$FUNC_NAME" \
    --environment "Variables=$UPDATED_CONFIG" \
    --output json > /dev/null
  
  echo "  ✓ Updated successfully"
done

echo ""
echo "=========================================="
echo "✓ All functions updated"
echo ""
echo "Verification:"
echo "You can verify CORS headers with:"
echo "curl -H 'Origin: https://rabbitmiles.com' https://api.rabbitmiles.com/me"
