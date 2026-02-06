#!/bin/bash
# Verification script to check if all Lambda functions have corresponding API Gateway routes
# This helps prevent the "Lambda exists but no route" issue

set -e

echo "🔍 RabbitMiles API Gateway Route Verification"
echo "=============================================="
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
API_ENDPOINT=$(aws apigatewayv2 get-api --api-id "$API_GATEWAY_ID" --query 'ApiEndpoint' --output text)
echo "API Name: $API_NAME"
echo "API Endpoint: $API_ENDPOINT"
echo ""

# Get all routes from API Gateway
echo "📋 Fetching existing routes..."
ROUTES=$(aws apigatewayv2 get-routes --api-id "$API_GATEWAY_ID" --query 'Items[].RouteKey' --output text)
echo ""

# Define expected routes based on Lambda functions
# Format: "METHOD /path|lambda-function-name|description"
#
# NOTE: This list is hardcoded for simplicity. As the project grows, consider
# externalizing this to a configuration file (e.g., routes.json) to make it
# easier to maintain without modifying the script.
#
# Example routes.json structure:
# {
#   "routes": [
#     {"method": "GET", "path": "/auth/start", "lambda": "auth_start", "description": "OAuth start"},
#     ...
#   ]
# }
declare -a EXPECTED_ROUTES=(
    "GET /auth/start|auth_start|OAuth start"
    "GET /auth/callback|auth_callback|OAuth callback"
    "GET /auth/disconnect|auth_disconnect|Disconnect Strava"
    "GET /me|me|Get current user"
    "GET /activities|get_activities|List user activities"
    "GET /activities/{id}|get_activity_detail|Get activity detail"
    "POST /activities/fetch|fetch_activities|Fetch activities from Strava"
    "POST /activities/{id}/reset-matching|reset_last_matched|Reset activity matching"
    "POST /strava/webhook|webhook|Strava webhook receiver"
    "GET /admin/users|admin_list_users|List all users (admin)"
    "GET /admin/users/{athlete_id}/activities|admin_user_activities|Get user activities (admin)"
    "DELETE /admin/users/{athlete_id}|admin_delete_user|Delete user (admin)"
)

echo "=================================="
echo "Route Verification Results"
echo "=================================="
echo ""

MISSING_ROUTES=()
FOUND_ROUTES=()

for expected in "${EXPECTED_ROUTES[@]}"; do
    IFS='|' read -r route_key lambda_name description <<< "$expected"
    
    # Check if route exists (allowing for OPTIONS as well)
    if echo "$ROUTES" | grep -q "$route_key"; then
        echo "✅ $route_key"
        echo "   Lambda: $lambda_name"
        echo "   Description: $description"
        FOUND_ROUTES+=("$route_key")
        
        # Check if OPTIONS route also exists (for CORS)
        options_route="OPTIONS ${route_key#* }"
        if echo "$ROUTES" | grep -q "$options_route"; then
            echo "   CORS: ✅ OPTIONS route exists"
        else
            echo "   CORS: ⚠️  OPTIONS route missing (may cause CORS issues)"
        fi
    else
        echo "❌ $route_key"
        echo "   Lambda: $lambda_name"
        echo "   Description: $description"
        echo "   Status: MISSING - Lambda exists but no API Gateway route"
        MISSING_ROUTES+=("$route_key|$lambda_name")
    fi
    echo ""
done

# Check for Lambda functions that might not have routes
echo "=================================="
echo "Lambda Function Check"
echo "=================================="
echo ""

echo "📋 Checking for Lambda functions without routes..."
LAMBDA_PREFIX="rabbitmiles-"
LAMBDAS=$(aws lambda list-functions --query "Functions[?starts_with(FunctionName, '$LAMBDA_PREFIX')].FunctionName" --output text)

for lambda in $LAMBDAS; do
    # Extract base name (remove prefix)
    base_name=${lambda#$LAMBDA_PREFIX}
    
    # Check if this Lambda is in our expected routes
    found=false
    for expected in "${EXPECTED_ROUTES[@]}"; do
        if echo "$expected" | grep -q "|$base_name|"; then
            found=true
            break
        fi
    done
    
    if [ "$found" = false ]; then
        # Check if it's a background Lambda (no API route needed)
        if [[ "$base_name" =~ ^(webhook_processor|update_activities|match_activity_trail|match_unmatched_activities|update_trail_data|backfill_athlete_count)$ ]]; then
            echo "ℹ️  $lambda - Background/scheduled Lambda (no API route needed)"
        else
            echo "⚠️  $lambda - Not in expected routes list (verify if route is needed)"
        fi
    fi
done

echo ""
echo "=================================="
echo "Summary"
echo "=================================="
echo ""

if [ ${#MISSING_ROUTES[@]} -eq 0 ]; then
    echo "✅ All expected routes are configured!"
    echo ""
    echo "Total routes checked: ${#EXPECTED_ROUTES[@]}"
    echo "Routes found: ${#FOUND_ROUTES[@]}"
    echo "Routes missing: 0"
    exit 0
else
    echo "⚠️  Some routes are missing!"
    echo ""
    echo "Total routes checked: ${#EXPECTED_ROUTES[@]}"
    echo "Routes found: ${#FOUND_ROUTES[@]}"
    echo "Routes missing: ${#MISSING_ROUTES[@]}"
    echo ""
    echo "Missing routes:"
    for missing in "${MISSING_ROUTES[@]}"; do
        IFS='|' read -r route_key lambda_name <<< "$missing"
        echo "  - $route_key (Lambda: $lambda_name)"
    done
    echo ""
    echo "🔧 To fix missing routes:"
    echo ""
    for missing in "${MISSING_ROUTES[@]}"; do
        IFS='|' read -r route_key lambda_name <<< "$missing"
        if [ "$route_key" = "DELETE /admin/users/{athlete_id}" ]; then
            echo "  ./scripts/setup-admin-delete-user-route.sh"
        else
            echo "  # Create route for: $route_key -> $lambda_name"
        fi
    done
    echo ""
    exit 1
fi
