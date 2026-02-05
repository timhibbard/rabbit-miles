#!/bin/bash

# verify-lambda-env.sh
# Verifies that all required environment variables are set correctly across Lambda functions
# Usage: ./verify-lambda-env.sh [--profile aws-profile-name]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
PROFILE_ARG=""
if [ "$1" == "--profile" ] && [ -n "$2" ]; then
    PROFILE_ARG="--profile $2"
    echo "Using AWS profile: $2"
fi

# Function to check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}ERROR: AWS CLI is not installed${NC}"
        echo "Install it from: https://aws.amazon.com/cli/"
        exit 1
    fi
}

# Function to get environment variable from Lambda
get_lambda_env() {
    local function_name=$1
    local var_name=$2
    
    aws lambda get-function-configuration \
        --function-name "$function_name" \
        $PROFILE_ARG \
        --query "Environment.Variables.$var_name" \
        --output text 2>/dev/null || echo "NOT_SET"
}

# Function to check if a Lambda function exists
lambda_exists() {
    local function_name=$1
    aws lambda get-function --function-name "$function_name" $PROFILE_ARG &>/dev/null
    return $?
}

# Function to print status
print_status() {
    local status=$1
    local message=$2
    
    if [ "$status" == "OK" ]; then
        echo -e "${GREEN}✓${NC} $message"
    elif [ "$status" == "WARN" ]; then
        echo -e "${YELLOW}⚠${NC} $message"
    else
        echo -e "${RED}✗${NC} $message"
    fi
}

# Function to check if a value is set
check_var() {
    local value=$1
    if [ "$value" == "NOT_SET" ] || [ "$value" == "None" ] || [ -z "$value" ]; then
        return 1
    fi
    return 0
}

echo "============================================="
echo "RabbitMiles Lambda Environment Verification"
echo "============================================="
echo

check_aws_cli

# Lambda function names (adjust these to match your naming convention)
# You can override these by setting environment variables before running the script
AUTH_START_FUNCTION="${AUTH_START_FUNCTION:-rabbitmiles-auth-start}"
AUTH_CALLBACK_FUNCTION="${AUTH_CALLBACK_FUNCTION:-rabbitmiles-auth-callback}"
ME_FUNCTION="${ME_FUNCTION:-rabbitmiles-me}"
AUTH_DISCONNECT_FUNCTION="${AUTH_DISCONNECT_FUNCTION:-rabbitmiles-auth-disconnect}"

echo "Checking Lambda functions:"
echo "  - $AUTH_START_FUNCTION"
echo "  - $AUTH_CALLBACK_FUNCTION"
echo "  - $ME_FUNCTION"
echo "  - $AUTH_DISCONNECT_FUNCTION"
echo

# Check if Lambda functions exist
ERRORS=0
WARNINGS=0

echo "--- Function Existence Check ---"
for func in "$AUTH_START_FUNCTION" "$AUTH_CALLBACK_FUNCTION" "$ME_FUNCTION" "$AUTH_DISCONNECT_FUNCTION"; do
    if lambda_exists "$func"; then
        print_status "OK" "Lambda function exists: $func"
    else
        print_status "ERROR" "Lambda function NOT FOUND: $func"
        ((ERRORS++))
    fi
done
echo

# Only proceed if all functions exist
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}ERROR: Some Lambda functions don't exist. Please check function names.${NC}"
    echo "You can override function names by setting environment variables:"
    echo "  export AUTH_START_FUNCTION=your-auth-start-function-name"
    echo "  export AUTH_CALLBACK_FUNCTION=your-auth-callback-function-name"
    echo "  export ME_FUNCTION=your-me-function-name"
    echo "  export AUTH_DISCONNECT_FUNCTION=your-auth-disconnect-function-name"
    exit 1
fi

# Check auth_start Lambda
echo "--- $AUTH_START_FUNCTION ---"
API_BASE_URL_START=$(get_lambda_env "$AUTH_START_FUNCTION" "API_BASE_URL")
FRONTEND_URL_START=$(get_lambda_env "$AUTH_START_FUNCTION" "FRONTEND_URL")
STRAVA_CLIENT_ID_START=$(get_lambda_env "$AUTH_START_FUNCTION" "STRAVA_CLIENT_ID")
DB_CLUSTER_ARN_START=$(get_lambda_env "$AUTH_START_FUNCTION" "DB_CLUSTER_ARN")
DB_SECRET_ARN_START=$(get_lambda_env "$AUTH_START_FUNCTION" "DB_SECRET_ARN")
DB_NAME_START=$(get_lambda_env "$AUTH_START_FUNCTION" "DB_NAME")

check_var "$API_BASE_URL_START" && print_status "OK" "API_BASE_URL: $API_BASE_URL_START" || { print_status "ERROR" "API_BASE_URL: NOT SET"; ((ERRORS++)); }
check_var "$FRONTEND_URL_START" && print_status "OK" "FRONTEND_URL: $FRONTEND_URL_START" || { print_status "ERROR" "FRONTEND_URL: NOT SET"; ((ERRORS++)); }
check_var "$STRAVA_CLIENT_ID_START" && print_status "OK" "STRAVA_CLIENT_ID: ${STRAVA_CLIENT_ID_START:0:10}..." || { print_status "ERROR" "STRAVA_CLIENT_ID: NOT SET"; ((ERRORS++)); }
check_var "$DB_CLUSTER_ARN_START" && print_status "OK" "DB_CLUSTER_ARN: ${DB_CLUSTER_ARN_START:0:50}..." || { print_status "ERROR" "DB_CLUSTER_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_SECRET_ARN_START" && print_status "OK" "DB_SECRET_ARN: ${DB_SECRET_ARN_START:0:50}..." || { print_status "ERROR" "DB_SECRET_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_NAME_START" && print_status "OK" "DB_NAME: $DB_NAME_START" || { print_status "WARN" "DB_NAME: NOT SET (will default to 'postgres')"; ((WARNINGS++)); }
echo

# Check auth_callback Lambda
echo "--- $AUTH_CALLBACK_FUNCTION ---"
API_BASE_URL_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "API_BASE_URL")
FRONTEND_URL_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "FRONTEND_URL")
APP_SECRET_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "APP_SECRET")
STRAVA_CLIENT_ID_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "STRAVA_CLIENT_SECRET")
STRAVA_SECRET_ARN_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "STRAVA_SECRET_ARN")
DB_CLUSTER_ARN_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "DB_CLUSTER_ARN")
DB_SECRET_ARN_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "DB_SECRET_ARN")
DB_NAME_CALLBACK=$(get_lambda_env "$AUTH_CALLBACK_FUNCTION" "DB_NAME")

check_var "$API_BASE_URL_CALLBACK" && print_status "OK" "API_BASE_URL: $API_BASE_URL_CALLBACK" || { print_status "ERROR" "API_BASE_URL: NOT SET"; ((ERRORS++)); }
check_var "$FRONTEND_URL_CALLBACK" && print_status "OK" "FRONTEND_URL: $FRONTEND_URL_CALLBACK" || { print_status "ERROR" "FRONTEND_URL: NOT SET"; ((ERRORS++)); }
check_var "$APP_SECRET_CALLBACK" && print_status "OK" "APP_SECRET: SET (${#APP_SECRET_CALLBACK} chars)" || { print_status "ERROR" "APP_SECRET: NOT SET"; ((ERRORS++)); }
check_var "$STRAVA_CLIENT_ID_CALLBACK" && print_status "OK" "STRAVA_CLIENT_ID: ${STRAVA_CLIENT_ID_CALLBACK:0:10}..." || { print_status "ERROR" "STRAVA_CLIENT_ID: NOT SET"; ((ERRORS++)); }

# Check Strava credentials (either CLIENT_SECRET or SECRET_ARN must be set)
if check_var "$STRAVA_CLIENT_SECRET_CALLBACK"; then
    print_status "OK" "STRAVA_CLIENT_SECRET: SET (${#STRAVA_CLIENT_SECRET_CALLBACK} chars)"
elif check_var "$STRAVA_SECRET_ARN_CALLBACK"; then
    print_status "OK" "STRAVA_SECRET_ARN: ${STRAVA_SECRET_ARN_CALLBACK:0:50}..."
else
    print_status "ERROR" "STRAVA_CLIENT_SECRET or STRAVA_SECRET_ARN: NOT SET (need one)"
    ((ERRORS++))
fi

check_var "$DB_CLUSTER_ARN_CALLBACK" && print_status "OK" "DB_CLUSTER_ARN: ${DB_CLUSTER_ARN_CALLBACK:0:50}..." || { print_status "ERROR" "DB_CLUSTER_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_SECRET_ARN_CALLBACK" && print_status "OK" "DB_SECRET_ARN: ${DB_SECRET_ARN_CALLBACK:0:50}..." || { print_status "ERROR" "DB_SECRET_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_NAME_CALLBACK" && print_status "OK" "DB_NAME: $DB_NAME_CALLBACK" || { print_status "WARN" "DB_NAME: NOT SET (will default to 'postgres')"; ((WARNINGS++)); }
echo

# Check me Lambda
echo "--- $ME_FUNCTION ---"
APP_SECRET_ME=$(get_lambda_env "$ME_FUNCTION" "APP_SECRET")
FRONTEND_URL_ME=$(get_lambda_env "$ME_FUNCTION" "FRONTEND_URL")
DB_CLUSTER_ARN_ME=$(get_lambda_env "$ME_FUNCTION" "DB_CLUSTER_ARN")
DB_SECRET_ARN_ME=$(get_lambda_env "$ME_FUNCTION" "DB_SECRET_ARN")
DB_NAME_ME=$(get_lambda_env "$ME_FUNCTION" "DB_NAME")

check_var "$APP_SECRET_ME" && print_status "OK" "APP_SECRET: SET (${#APP_SECRET_ME} chars)" || { print_status "ERROR" "APP_SECRET: NOT SET"; ((ERRORS++)); }
check_var "$FRONTEND_URL_ME" && print_status "OK" "FRONTEND_URL: $FRONTEND_URL_ME" || { print_status "ERROR" "FRONTEND_URL: NOT SET"; ((ERRORS++)); }
check_var "$DB_CLUSTER_ARN_ME" && print_status "OK" "DB_CLUSTER_ARN: ${DB_CLUSTER_ARN_ME:0:50}..." || { print_status "ERROR" "DB_CLUSTER_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_SECRET_ARN_ME" && print_status "OK" "DB_SECRET_ARN: ${DB_SECRET_ARN_ME:0:50}..." || { print_status "ERROR" "DB_SECRET_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_NAME_ME" && print_status "OK" "DB_NAME: $DB_NAME_ME" || { print_status "WARN" "DB_NAME: NOT SET (will default to 'postgres')"; ((WARNINGS++)); }
echo

# Check auth_disconnect Lambda
echo "--- $AUTH_DISCONNECT_FUNCTION ---"
API_BASE_URL_DISCONNECT=$(get_lambda_env "$AUTH_DISCONNECT_FUNCTION" "API_BASE_URL")
FRONTEND_URL_DISCONNECT=$(get_lambda_env "$AUTH_DISCONNECT_FUNCTION" "FRONTEND_URL")
APP_SECRET_DISCONNECT=$(get_lambda_env "$AUTH_DISCONNECT_FUNCTION" "APP_SECRET")
DB_CLUSTER_ARN_DISCONNECT=$(get_lambda_env "$AUTH_DISCONNECT_FUNCTION" "DB_CLUSTER_ARN")
DB_SECRET_ARN_DISCONNECT=$(get_lambda_env "$AUTH_DISCONNECT_FUNCTION" "DB_SECRET_ARN")
DB_NAME_DISCONNECT=$(get_lambda_env "$AUTH_DISCONNECT_FUNCTION" "DB_NAME")

check_var "$API_BASE_URL_DISCONNECT" && print_status "OK" "API_BASE_URL: $API_BASE_URL_DISCONNECT" || { print_status "ERROR" "API_BASE_URL: NOT SET"; ((ERRORS++)); }
check_var "$FRONTEND_URL_DISCONNECT" && print_status "OK" "FRONTEND_URL: $FRONTEND_URL_DISCONNECT" || { print_status "ERROR" "FRONTEND_URL: NOT SET"; ((ERRORS++)); }
check_var "$APP_SECRET_DISCONNECT" && print_status "OK" "APP_SECRET: SET (${#APP_SECRET_DISCONNECT} chars)" || { print_status "ERROR" "APP_SECRET: NOT SET"; ((ERRORS++)); }
check_var "$DB_CLUSTER_ARN_DISCONNECT" && print_status "OK" "DB_CLUSTER_ARN: ${DB_CLUSTER_ARN_DISCONNECT:0:50}..." || { print_status "ERROR" "DB_CLUSTER_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_SECRET_ARN_DISCONNECT" && print_status "OK" "DB_SECRET_ARN: ${DB_SECRET_ARN_DISCONNECT:0:50}..." || { print_status "ERROR" "DB_SECRET_ARN: NOT SET"; ((ERRORS++)); }
check_var "$DB_NAME_DISCONNECT" && print_status "OK" "DB_NAME: $DB_NAME_DISCONNECT" || { print_status "WARN" "DB_NAME: NOT SET (will default to 'postgres')"; ((WARNINGS++)); }
echo

# Cross-Lambda consistency checks
echo "--- Cross-Lambda Consistency Checks ---"

# Check APP_SECRET consistency
if [ "$APP_SECRET_CALLBACK" == "$APP_SECRET_ME" ] && [ "$APP_SECRET_ME" == "$APP_SECRET_DISCONNECT" ]; then
    print_status "OK" "APP_SECRET is consistent across auth_callback, me, and auth_disconnect"
else
    print_status "ERROR" "APP_SECRET is NOT consistent across Lambdas!"
    echo "  auth_callback: ${#APP_SECRET_CALLBACK} chars"
    echo "  me: ${#APP_SECRET_ME} chars"
    echo "  auth_disconnect: ${#APP_SECRET_DISCONNECT} chars"
    ((ERRORS++))
fi

# Check FRONTEND_URL consistency
if [ "$FRONTEND_URL_START" == "$FRONTEND_URL_CALLBACK" ] && \
   [ "$FRONTEND_URL_CALLBACK" == "$FRONTEND_URL_ME" ] && \
   [ "$FRONTEND_URL_ME" == "$FRONTEND_URL_DISCONNECT" ]; then
    print_status "OK" "FRONTEND_URL is consistent across all auth Lambdas"
else
    print_status "ERROR" "FRONTEND_URL is NOT consistent across Lambdas!"
    echo "  auth_start: $FRONTEND_URL_START"
    echo "  auth_callback: $FRONTEND_URL_CALLBACK"
    echo "  me: $FRONTEND_URL_ME"
    echo "  auth_disconnect: $FRONTEND_URL_DISCONNECT"
    ((ERRORS++))
fi

# Check for trailing slash in FRONTEND_URL
if [[ "$FRONTEND_URL_START" == */ ]] || \
   [[ "$FRONTEND_URL_CALLBACK" == */ ]] || \
   [[ "$FRONTEND_URL_ME" == */ ]] || \
   [[ "$FRONTEND_URL_DISCONNECT" == */ ]]; then
    print_status "ERROR" "FRONTEND_URL has trailing slash (should not have one)"
    ((ERRORS++))
else
    print_status "OK" "FRONTEND_URL has no trailing slash"
fi

# Check API_BASE_URL consistency
if [ "$API_BASE_URL_START" == "$API_BASE_URL_CALLBACK" ] && \
   [ "$API_BASE_URL_CALLBACK" == "$API_BASE_URL_DISCONNECT" ]; then
    print_status "OK" "API_BASE_URL is consistent across auth_start, auth_callback, and auth_disconnect"
else
    print_status "WARN" "API_BASE_URL is not consistent across Lambdas (may be intentional)"
    echo "  auth_start: $API_BASE_URL_START"
    echo "  auth_callback: $API_BASE_URL_CALLBACK"
    echo "  auth_disconnect: $API_BASE_URL_DISCONNECT"
    ((WARNINGS++))
fi

# Check if API_BASE_URL includes stage
if [[ "$API_BASE_URL_START" == */prod ]] || [[ "$API_BASE_URL_START" == */dev ]]; then
    print_status "OK" "API_BASE_URL includes stage path"
else
    print_status "WARN" "API_BASE_URL may be missing stage path (e.g., /prod)"
    ((WARNINGS++))
fi

# Check DB credentials consistency
if [ "$DB_CLUSTER_ARN_START" == "$DB_CLUSTER_ARN_CALLBACK" ] && \
   [ "$DB_CLUSTER_ARN_CALLBACK" == "$DB_CLUSTER_ARN_ME" ] && \
   [ "$DB_CLUSTER_ARN_ME" == "$DB_CLUSTER_ARN_DISCONNECT" ]; then
    print_status "OK" "DB_CLUSTER_ARN is consistent across all Lambdas"
else
    print_status "ERROR" "DB_CLUSTER_ARN is NOT consistent across Lambdas!"
    ((ERRORS++))
fi

if [ "$DB_SECRET_ARN_START" == "$DB_SECRET_ARN_CALLBACK" ] && \
   [ "$DB_SECRET_ARN_CALLBACK" == "$DB_SECRET_ARN_ME" ] && \
   [ "$DB_SECRET_ARN_ME" == "$DB_SECRET_ARN_DISCONNECT" ]; then
    print_status "OK" "DB_SECRET_ARN is consistent across all Lambdas"
else
    print_status "ERROR" "DB_SECRET_ARN is NOT consistent across Lambdas!"
    ((ERRORS++))
fi

echo

# Summary
echo "============================================="
echo "Summary"
echo "============================================="
echo -e "Errors: ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠ There are $WARNINGS warnings that should be reviewed.${NC}"
    fi
    exit 0
else
    echo -e "${RED}✗ There are $ERRORS errors that must be fixed.${NC}"
    echo
    echo "Next steps:"
    echo "1. Review the errors above"
    echo "2. Update Lambda environment variables using AWS Console or CLI"
    echo "3. Re-run this script to verify fixes"
    echo
    echo "See ENV_VARS.md for complete environment variable documentation"
    exit 1
fi
