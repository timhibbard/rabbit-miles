#!/bin/bash
# Verification script for leaderboard fix deployment
# Run this after deploying to verify everything works

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║         Leaderboard Fix - Post-Deployment Verification              ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if required environment variables are set
if [ -z "$API_URL" ]; then
    API_URL="https://api.rabbitmiles.com"
    echo "${YELLOW}⚠ API_URL not set, using default: $API_URL${NC}"
fi

if [ -z "$ADMIN_SESSION_COOKIE" ]; then
    echo "${RED}✗ ERROR: ADMIN_SESSION_COOKIE environment variable not set${NC}"
    echo ""
    echo "Please set your admin session cookie:"
    echo "  export ADMIN_SESSION_COOKIE='your-rm_session-cookie-value'"
    echo ""
    echo "To get your session cookie:"
    echo "  1. Log in to https://rabbitmiles.com as an admin"
    echo "  2. Open DevTools → Application → Cookies"
    echo "  3. Copy the 'rm_session' cookie value"
    exit 1
fi

echo "Configuration:"
echo "  API URL: $API_URL"
echo "  Cookie: ${ADMIN_SESSION_COOKIE:0:20}..."
echo ""

# Step 1: Check if recalculate endpoint exists
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Testing recalculate endpoint..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RECALC_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "$API_URL/admin/leaderboard/recalculate" \
  -H "Cookie: rm_session=$ADMIN_SESSION_COOKIE" \
  -H "Content-Type: application/json")

RECALC_HTTP_CODE=$(echo "$RECALC_RESPONSE" | tail -n1)
RECALC_BODY=$(echo "$RECALC_RESPONSE" | head -n-1)

if [ "$RECALC_HTTP_CODE" = "200" ]; then
    echo "${GREEN}✓ Recalculate endpoint responded successfully${NC}"
    echo ""
    echo "Response:"
    echo "$RECALC_BODY" | python3 -m json.tool 2>/dev/null || echo "$RECALC_BODY"
    echo ""
    
    # Extract stats
    ACTIVITIES=$(echo "$RECALC_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('activities_processed', 0))" 2>/dev/null || echo "?")
    ATHLETES=$(echo "$RECALC_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('athletes_processed', 0))" 2>/dev/null || echo "?")
    
    echo "Summary:"
    echo "  Activities processed: $ACTIVITIES"
    echo "  Athletes processed: $ATHLETES"
    echo ""
else
    echo "${RED}✗ Recalculate endpoint failed${NC}"
    echo "  HTTP Status: $RECALC_HTTP_CODE"
    echo "  Response: $RECALC_BODY"
    echo ""
    
    if [ "$RECALC_HTTP_CODE" = "401" ]; then
        echo "  → Authentication failed. Check your session cookie."
    elif [ "$RECALC_HTTP_CODE" = "403" ]; then
        echo "  → Authorization failed. Make sure you're in ADMIN_ATHLETE_IDS."
    elif [ "$RECALC_HTTP_CODE" = "404" ]; then
        echo "  → Endpoint not found. Check API Gateway configuration."
    fi
    
    exit 1
fi

# Step 2: Check if leaderboard endpoint works
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Testing leaderboard endpoint..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LEADERBOARD_RESPONSE=$(curl -s -w "\n%{http_code}" \
  "$API_URL/leaderboard?window=week&metric=distance&activity_type=foot&limit=10" \
  -H "Cookie: rm_session=$ADMIN_SESSION_COOKIE")

LEADERBOARD_HTTP_CODE=$(echo "$LEADERBOARD_RESPONSE" | tail -n1)
LEADERBOARD_BODY=$(echo "$LEADERBOARD_RESPONSE" | head -n-1)

if [ "$LEADERBOARD_HTTP_CODE" = "200" ]; then
    echo "${GREEN}✓ Leaderboard endpoint responded successfully${NC}"
    echo ""
    echo "Response sample:"
    echo "$LEADERBOARD_BODY" | python3 -m json.tool 2>/dev/null | head -30 || echo "$LEADERBOARD_BODY" | head -30
    echo ""
    
    # Count rows
    ROW_COUNT=$(echo "$LEADERBOARD_BODY" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('rows', [])))" 2>/dev/null || echo "?")
    WINDOW_KEY=$(echo "$LEADERBOARD_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('window_key', '?'))" 2>/dev/null || echo "?")
    
    echo "Summary:"
    echo "  Rows returned: $ROW_COUNT"
    echo "  Window key: $WINDOW_KEY"
    echo ""
    
    if [ "$ROW_COUNT" = "0" ]; then
        echo "${YELLOW}⚠ Warning: No data returned. This might be expected if no activities exist.${NC}"
        echo "  Try backfilling activities first: POST /admin/users/{athlete_id}/backfill-activities"
        echo ""
    fi
else
    echo "${RED}✗ Leaderboard endpoint failed${NC}"
    echo "  HTTP Status: $LEADERBOARD_HTTP_CODE"
    echo "  Response: $LEADERBOARD_BODY"
    echo ""
    
    if [ "$LEADERBOARD_HTTP_CODE" = "500" ]; then
        echo "  → Internal server error. The original problem may still exist."
        echo "  → Check CloudWatch logs for details."
    fi
    
    exit 1
fi

# Step 3: Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Verification Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "${GREEN}✅ All checks passed!${NC}"
echo ""
echo "Next steps:"
echo "  • Check the leaderboard page in your browser"
echo "  • Verify rankings are correct"
echo "  • Monitor CloudWatch logs for any errors"
echo "  • The webhook processor will keep data up-to-date automatically"
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                    Deployment verified! 🎉                           ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
