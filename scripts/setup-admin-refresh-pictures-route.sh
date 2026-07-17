#!/bin/bash
# Setup script for admin_refresh_pictures API Gateway route
# This script helps create the POST /admin/refresh-pictures route in API Gateway

set -e

echo "🚀 RabbitMiles Admin Refresh Pictures Route Setup"
echo "========================================================="
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

# Prompt for API Gateway ID if not provided
if [ -z "$API_GATEWAY_ID" ]; then
    echo "📋 Finding your API Gateway HTTP API..."
    echo ""
    
    # List available HTTP APIs
    APIS=$(aws apigatewayv2 get-apis --query 'Items[?ProtocolType==`HTTP`].[ApiId,Name]' --output text)
    
    if [ -z "$APIS" ]; then
        echo "❌ No HTTP APIs found in region $AWS_REGION"
        exit 1
    fi
    
    echo "Available HTTP APIs:"
    echo "$APIS"
    echo ""
    
    read -p "Enter your API Gateway ID: " API_GATEWAY_ID
fi

echo "Using API Gateway ID: $API_GATEWAY_ID"
echo ""

# Verify API exists
if ! aws apigatewayv2 get-api --api-id "$API_GATEWAY_ID" &> /dev/null; then
    echo "❌ Error: API Gateway with ID $API_GATEWAY_ID not found"
    exit 1
fi

API_NAME=$(aws apigatewayv2 get-api --api-id "$API_GATEWAY_ID" --query 'Name' --output text)
echo "API Name: $API_NAME"
echo ""

# Prompt for Lambda function name if not provided
if [ -z "$LAMBDA_FUNCTION_NAME" ]; then
    echo "📋 Finding admin_refresh_pictures Lambda function..."
    echo ""
    
    # Try common Lambda function names
    for name in "rabbitmiles-admin-refresh-pictures" "prod-admin-refresh-pictures" "admin-refresh-pictures"; do
        if aws lambda get-function --function-name "$name" &> /dev/null 2>&1; then
            LAMBDA_FUNCTION_NAME="$name"
            echo "✅ Found Lambda function: $LAMBDA_FUNCTION_NAME"
            break
        fi
    done
    
    if [ -z "$LAMBDA_FUNCTION_NAME" ]; then
        echo "⚠️  Could not auto-detect Lambda function name"
        read -p "Enter your admin_refresh_pictures Lambda function name: " LAMBDA_FUNCTION_NAME
    fi
fi

echo "Using Lambda function: $LAMBDA_FUNCTION_NAME"
echo ""

# Verify Lambda exists
if ! aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" &> /dev/null; then
    echo "❌ Error: Lambda function $LAMBDA_FUNCTION_NAME not found"
    exit 1
fi

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --query 'Configuration.FunctionArn' --output text)
echo "Lambda ARN: $LAMBDA_ARN"
echo ""

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Check if route already exists
echo "🔍 Checking if POST /admin/refresh-pictures route exists..."
ROUTE_EXISTS=$(aws apigatewayv2 get-routes --api-id "$API_GATEWAY_ID" \
    --query 'Items[?RouteKey==`POST /admin/refresh-pictures`].RouteId' --output text)

if [ -n "$ROUTE_EXISTS" ]; then
    echo "⚠️  Route POST /admin/refresh-pictures already exists (Route ID: $ROUTE_EXISTS)"
    read -p "Do you want to recreate it? (y/N): " RECREATE
    if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
        echo "🗑️  Deleting existing route..."
        aws apigatewayv2 delete-route --api-id "$API_GATEWAY_ID" --route-id "$ROUTE_EXISTS"
        echo "✅ Deleted existing route"
    else
        echo "✅ Keeping existing route"
        exit 0
    fi
fi
echo ""

# Check if integration exists for this Lambda
echo "🔍 Checking for existing Lambda integration..."
INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id "$API_GATEWAY_ID" \
    --query "Items[?IntegrationUri==\`$LAMBDA_ARN\`].IntegrationId" --output text)

if [ -z "$INTEGRATION_ID" ]; then
    echo "📦 Creating Lambda integration..."
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
        --api-id "$API_GATEWAY_ID" \
        --integration-type AWS_PROXY \
        --integration-uri "$LAMBDA_ARN" \
        --payload-format-version "2.0" \
        --query 'IntegrationId' \
        --output text)
    echo "✅ Created integration: $INTEGRATION_ID"
else
    echo "✅ Using existing integration: $INTEGRATION_ID"
fi
echo ""

# Create the POST route
echo "🛣️  Creating POST /admin/refresh-pictures route..."
ROUTE_ID=$(aws apigatewayv2 create-route \
    --api-id "$API_GATEWAY_ID" \
    --route-key "POST /admin/refresh-pictures" \
    --target "integrations/$INTEGRATION_ID" \
    --query 'RouteId' \
    --output text)
echo "✅ Created route: $ROUTE_ID"
echo ""

# Create OPTIONS route for CORS preflight
echo "🛣️  Creating OPTIONS /admin/refresh-pictures route for CORS..."
OPTIONS_ROUTE_EXISTS=$(aws apigatewayv2 get-routes --api-id "$API_GATEWAY_ID" \
    --query 'Items[?RouteKey==`OPTIONS /admin/refresh-pictures`].RouteId' --output text)

if [ -z "$OPTIONS_ROUTE_EXISTS" ]; then
    OPTIONS_ROUTE_ID=$(aws apigatewayv2 create-route \
        --api-id "$API_GATEWAY_ID" \
        --route-key "OPTIONS /admin/refresh-pictures" \
        --target "integrations/$INTEGRATION_ID" \
        --query 'RouteId' \
        --output text)
    echo "✅ Created OPTIONS route: $OPTIONS_ROUTE_ID"
else
    echo "✅ OPTIONS route already exists: $OPTIONS_ROUTE_EXISTS"
fi
echo ""

# Add Lambda permission for API Gateway to invoke the function
echo "🔐 Adding Lambda permission for API Gateway..."

# Use a consistent statement ID
STATEMENT_ID="apigateway-admin-refresh-pictures"

# Remove existing permission if any (ignore errors if it doesn't exist)
aws lambda remove-permission \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --statement-id "$STATEMENT_ID" \
    &> /dev/null || true

# Add the permission with consistent statement ID
aws lambda add-permission \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --statement-id "$STATEMENT_ID" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_GATEWAY_ID/*/*/admin/refresh-pictures" \
    &> /dev/null

echo "✅ Lambda permission added"
echo ""

# Get API endpoint
API_ENDPOINT=$(aws apigatewayv2 get-api --api-id "$API_GATEWAY_ID" --query 'ApiEndpoint' --output text)

# Output summary
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "📋 Configuration Summary:"
echo ""
echo "API Gateway ID: $API_GATEWAY_ID"
echo "API Endpoint: $API_ENDPOINT"
echo "Route: POST /admin/refresh-pictures"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "Integration ID: $INTEGRATION_ID"
echo "Route ID: $ROUTE_ID"
echo ""
echo "🧪 Testing:"
echo ""
echo "Test the endpoint with an admin session cookie:"
echo ""
echo "curl -X POST $API_ENDPOINT/admin/refresh-pictures \\"
echo "  -H \"Cookie: rm_session=your-admin-session-cookie\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -v"
echo ""
echo "Expected response (202 - refresh runs asynchronously in the background):"
echo "{\"message\": \"Profile picture refresh started. This runs in the background and may take a minute.\", \"status\": \"processing\"}"
echo ""
echo "⚠️  Important Notes:"
echo ""
echo "1. Ensure your Lambda has these environment variables set:"
echo "   - APP_SECRET"
echo "   - FRONTEND_URL"
echo "   - DB_CLUSTER_ARN"
echo "   - DB_SECRET_ARN"
echo "   - DB_NAME"
echo "   - ADMIN_ATHLETE_IDS (comma-separated)"
echo "   - STRAVA_CLIENT_ID + STRAVA_CLIENT_SECRET (or STRAVA_SECRET_ARN)"
echo ""
echo "2. Ensure your Lambda has IAM permissions for:"
echo "   - rds-data:ExecuteStatement"
echo "   - secretsmanager:GetSecretValue"
echo "   - lambda:InvokeFunction on itself (it self-invokes to run in the background)"
echo ""
echo "3. The Lambda function must NOT be in a VPC (RDS Data API requirement)"
echo ""
echo "For detailed instructions, see DEPLOYMENT_REFRESH_PICTURES.md"
echo ""
