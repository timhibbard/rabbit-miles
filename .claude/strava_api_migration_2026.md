# Strava API Migration Plan - 2026 Developer Program Changes

## Executive Summary

Strava announced major changes to their Developer Program on June 1, 2026. This document outlines the required technical changes, administrative actions, and migration timeline for RabbitMiles.

**TL;DR:**
- ✅ Already compliant: Authorization tokens in headers
- ⚠️ Action required by June 1, 2027: Update API base URL and OAuth endpoints
- 📋 Administrative: Subscription required by June 30, 2026 (3-month free code: `6ae7cec87e`)

---

## Timeline Overview

### ✅ Already Compliant (No Action)
- **Authorization tokens in request headers**: Already using `Authorization: Bearer {token}` ✓

### 📋 Effective June 1, 2026 (Administrative)
- **Official Strava MCP**: Available with Strava subscription (for personal data analysis)
- **New tier classifications**: Standard Tier vs Extended Access Tier
- **Subscription required for new developers**: Standard Tier needs subscription
- **Intermediary platform restrictions**: Direct integrations only (RabbitMiles is already direct)

### ⚠️ Effective June 30, 2026 (Action Required)
- **Subscription required**: Standard Tier developers must have active Strava subscription
  - **Action**: Redeem 3-month free code: `6ae7cec87e` at [https://www.strava.com/subscribe](https://www.strava.com/subscribe)
  - **Follow-up**: Subscribe before September 30, 2026

### 📊 Effective September 1, 2026 (Review Usage)
- **Deprecated endpoints**:
  - Club Activities
  - Club Administrators
  - Club Members
  - Segments Explore (Extended Access only)
  - **Action**: Verify RabbitMiles doesn't use these endpoints (preliminary scan shows none)

### 🚨 Effective June 1, 2027 (CODE CHANGES REQUIRED)
- **API base URL change**: `https://www.strava.com/api/v3` → `https://www.api-v3.strava.com`
- **OAuth endpoint changes**: New `oauth/revoke`, deprecate `oauth/deauthorize`
- **Authorization tokens in headers**: Must use headers, not form params (already compliant ✓)

---

## Required Code Changes (Deadline: June 1, 2027)

### Phase 1: Update Strava API Base URL

**Change from:** `https://www.strava.com/api/v3`  
**Change to:** `https://www.api-v3.strava.com`

#### Affected Files (10 Lambda functions)

1. **backend/scheduled_activity_update/lambda_function.py**
   - Line 35: `STRAVA_ACTIVITIES_URL = "https://www.api-v3.strava.com/athlete/activities"`
   - Line 36: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

2. **backend/fetch_activities/lambda_function.py**
   - Line 35: `STRAVA_ACTIVITIES_URL = "https://www.api-v3.strava.com/athlete/activities"`
   - Line 36: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

3. **backend/backfill_athlete_count/lambda_function.py**
   - Update: `STRAVA_API_BASE = "https://www.api-v3.strava.com"`
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

4. **backend/update_activities/lambda_function.py**
   - Update: `STRAVA_ACTIVITY_URL = "https://www.api-v3.strava.com/activities"`
   - Update: `STRAVA_ACTIVITIES_URL = "https://www.api-v3.strava.com/athlete/activities"`
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

5. **backend/webhook_processor/lambda_function.py**
   - Update: `STRAVA_ACTIVITY_URL = "https://www.api-v3.strava.com/activities"`
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

6. **backend/admin_update_activities/lambda_function.py**
   - Update: `STRAVA_ACTIVITIES_URL = "https://www.api-v3.strava.com/athlete/activities"`
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

7. **backend/user_update_activities/lambda_function.py**
   - Update: `STRAVA_ACTIVITIES_URL = "https://www.api-v3.strava.com/athlete/activities"`
   - Update: `STRAVA_ATHLETE_URL = "https://www.api-v3.strava.com/athlete"`
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

8. **backend/admin_backfill_activities/lambda_function.py**
   - Update: `STRAVA_ACTIVITIES_URL = "https://www.api-v3.strava.com/athlete/activities"`
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

9. **backend/auth_callback/lambda_function.py**
   - Update: `STRAVA_TOKEN_URL = "https://www.api-v3.strava.com/oauth/token"`

10. **backend/auth_start/lambda_function.py**
    - Update: OAuth authorize URL to `https://www.api-v3.strava.com/oauth/authorize`

### Phase 2: Implement New OAuth Revoke Endpoint

**New endpoint available now:** `oauth/revoke`  
**Deprecated June 1, 2027:** `oauth/deauthorize`

#### Current State
- `backend/auth_disconnect/lambda_function.py` currently only clears local tokens (does not call Strava deauthorize)

#### Required Changes
Add Strava API revocation call when user disconnects:

```python
# In backend/auth_disconnect/lambda_function.py
# After verifying session and before clearing database tokens

def revoke_strava_token(access_token, client_id, client_secret):
    """Revoke Strava access token using new oauth/revoke endpoint"""
    import urllib.request
    import urllib.parse
    
    url = "https://www.api-v3.strava.com/oauth/revoke"
    data = urllib.parse.urlencode({
        'access_token': access_token
    }).encode()
    
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', f'Bearer {access_token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except Exception as e:
        print(f"WARN - Failed to revoke Strava token: {e}")
        # Don't fail the disconnect flow if Strava revocation fails
        return False

# Usage in handler after verifying session:
# 1. Get user's access_token from database
# 2. Call revoke_strava_token(access_token, client_id, client_secret)
# 3. Then proceed with existing token clearing logic
```

**Implementation Steps:**
1. Query database for user's `access_token` before clearing
2. Call new `oauth/revoke` endpoint
3. Continue with existing token clearing (don't fail if revoke fails)
4. Update frontend to show revocation status

### Phase 3: Environment Variable Updates (Optional)

Consider centralizing Strava API base URL as environment variable:

```bash
# Lambda environment variables
STRAVA_API_BASE=https://www.api-v3.strava.com
```

**Benefits:**
- Single source of truth for API URL
- Easier to roll back if issues occur
- Can test new URL in staging before production

**Files to refactor:**
- Create shared `backend/strava_config.py` module
- Import in all Lambda functions
- Use environment variable with fallback to new URL

---

## Frontend Changes

### OAuth Authorization URL

**File:** `src/pages/ConnectStrava.jsx`

**Current code** (Line ~65-70):
```javascript
'https://www.strava.com/oauth/authorize',
```

**Update to:**
```javascript
'https://www.api-v3.strava.com/oauth/authorize',
```

**Note:** This change should be coordinated with backend OAuth changes.

---

## Testing Plan

### Phase 1: Staging Environment Testing (Target: April 2027)

1. **Set up staging environment with new URLs**
   - Create separate Lambda functions for testing
   - Use test Strava API application (separate client ID)
   - Test with personal account first

2. **Test OAuth flow**
   - New user authorization
   - Token refresh
   - Token revocation (disconnect)

3. **Test activity fetching**
   - Initial fetch (backfill)
   - Incremental updates
   - Webhook processing
   - Manual refresh

4. **Monitor for breaking changes**
   - Rate limiting behavior
   - Response formats
   - Error codes
   - Rate limit headers

### Phase 2: Canary Deployment (Target: May 1, 2027)

1. **Deploy to subset of users**
   - Use Lambda aliases for gradual rollout
   - Monitor CloudWatch logs for errors
   - Track API response times

2. **Success criteria**
   - Zero increase in error rates
   - Same API response times (<500ms p99)
   - All OAuth flows working
   - Webhooks processing correctly

### Phase 3: Full Production Rollout (Target: May 15, 2027)

1. **Deploy to all users**
2. **Monitor for 7 days**
3. **Rollback plan ready** (keep old URL as fallback)

---

## Administrative Actions

### Immediate (June 2026)

- [ ] **Check developer tier status**
  - Visit: [Strava API Settings Dashboard](https://www.strava.com/settings/api)
  - Confirm current tier (Standard vs Extended Access)
  - Note rate limits and user capacity

- [ ] **Redeem 3-month free subscription**
  - Code: `6ae7cec87e`
  - Redeem at: [https://www.strava.com/subscribe](https://www.strava.com/subscribe)
  - Calendar reminder: Subscribe before September 30, 2026

- [ ] **Review API usage for deprecated endpoints**
  ```bash
  # Search codebase for deprecated endpoints
  grep -r "club.*activities\|club.*administrators\|club.*members\|segments.*explore" backend/ --include="*.py"
  ```
  - Expected result: No usage found (RabbitMiles doesn't use club/segment features)

- [ ] **Review Developer FAQ**
  - URL: Provided in Strava email
  - Subscribe to updates for Extended Access qualification criteria

### Before September 1, 2026

- [ ] **Confirm no deprecated endpoint usage**
- [ ] **Subscribe to Strava subscription** (if free trial expires)

### Before June 1, 2027

- [ ] **Complete all code changes** (Phase 1-3 above)
- [ ] **Deploy to staging environment** (April 2027)
- [ ] **Complete canary rollout** (May 2027)
- [ ] **Full production deployment** (May 15, 2027)

---

## Risk Assessment

### Low Risk
- ✅ **Authorization headers**: Already compliant, no changes needed
- ✅ **Direct integration**: Not using intermediary platforms
- ✅ **No deprecated endpoints**: RabbitMiles doesn't use club/segment APIs

### Medium Risk
- ⚠️ **API URL migration**: Straightforward but requires testing
  - **Mitigation**: Staged rollout with canary deployment
  - **Rollback**: Keep old URL as environment variable fallback

- ⚠️ **OAuth revoke implementation**: New code, needs testing
  - **Mitigation**: Graceful degradation (don't fail disconnect if revoke fails)
  - **Rollback**: Can deploy without revoke initially, add later

### High Risk
- 🚨 **Subscription lapse**: Would lose API access
  - **Mitigation**: Set calendar reminders
  - **Mitigation**: Set up billing alerts
  - **Mitigation**: Add subscription status check to monitoring

---

## Cost Implications

### Strava Subscription
- **3-month free trial**: June 30 - September 30, 2026
- **After trial**: $11.99/month or $79.99/year (as of 2026)
- **Annual cost**: ~$80-120/year for API access

### Development Time Estimate
- **Code changes**: 4-8 hours
- **Testing**: 8-16 hours
- **Staging deployment**: 4 hours
- **Production rollout**: 4 hours
- **Total**: 20-32 hours (~3-4 days)

### AWS Costs
- **No additional costs**: Same Lambda invocations, just different URLs
- **Staging environment**: Minimal (<$10 for testing period)

---

## Rollback Plan

### If New API URL Has Issues

1. **Immediate rollback** (< 5 minutes):
   ```bash
   # Update Lambda environment variable
   aws lambda update-function-configuration \
     --function-name <function-name> \
     --environment Variables={STRAVA_API_BASE=https://www.strava.com/api/v3}
   ```

2. **Redeploy previous version** (< 15 minutes):
   ```bash
   # Use Lambda version/alias system
   aws lambda update-alias \
     --function-name <function-name> \
     --name production \
     --function-version <previous-version>
   ```

3. **Communication**:
   - Post status update if user-facing issues
   - Monitor for reports of connection issues
   - Check Strava API status page

### Success Criteria for Go/No-Go

**Go ahead with rollout if:**
- ✅ All staging tests pass
- ✅ OAuth flows work end-to-end
- ✅ Activity fetching works
- ✅ Webhook processing works
- ✅ No increase in error rates during canary

**Do not proceed if:**
- ❌ Any OAuth flow fails
- ❌ API response times degrade >20%
- ❌ Error rates increase >1%
- ❌ Strava API status page shows issues

---

## Monitoring & Validation

### Post-Migration Checks

1. **CloudWatch Metrics** (Monitor for 7 days post-deployment):
   - Lambda error rates (target: <0.1%)
   - Lambda duration (target: <500ms p99)
   - API Gateway 4xx/5xx rates
   - Successful OAuth completions

2. **Application Metrics**:
   - User connection success rate
   - Activity fetch completion rate
   - Webhook processing rate
   - Token refresh success rate

3. **User-Facing Validation**:
   - Test new user signup + Strava connection
   - Test existing user activity refresh
   - Test disconnect + reconnect flow
   - Test webhook when new activity uploaded

### Alerts to Set Up

```yaml
# CloudWatch Alarms
- Lambda error rate >1% for any function
- Lambda duration >2000ms p99
- API Gateway 5xx rate >5%
- SQS dead letter queue depth >10

# Manual checks (weekly for first month)
- Review CloudWatch Logs for "strava" errors
- Check user feedback channels
- Monitor rate limit consumption
```

---

## Documentation Updates

After migration, update:

1. **README.md**
   - Update any Strava API references
   - Update environment variable examples

2. **CLAUDE.md** (if exists)
   - Document new Strava API URL
   - Document OAuth revoke flow

3. **Deployment docs**
   - Add new environment variables
   - Update Lambda configuration steps

4. **Runbooks**
   - Update troubleshooting guides
   - Update OAuth debugging steps

---

## Questions & Clarifications Needed

### For Strava Support
- [ ] Will there be a grace period after June 1, 2027?
- [ ] Will old URL redirect to new URL temporarily?
- [ ] Are there any other breaking changes not mentioned?
- [ ] What happens if Extended Access Tier qualification criteria change?

### For RabbitMiles
- [ ] Do we need/want Extended Access Tier?
  - Benefits: Higher rate limits, more users, partner APIs
  - Costs: No subscription required (saves $80-120/year)
  - Application process: Required

- [ ] Should we implement monitoring for subscription status?
- [ ] Should we add user-facing messaging about Strava API changes?

---

## Success Metrics

### Technical Success
- ✅ Zero increase in error rates post-migration
- ✅ Zero user-reported connection issues
- ✅ All OAuth flows functioning
- ✅ All activity fetching working
- ✅ All webhooks processing

### Business Success
- ✅ Maintain API access (subscription active)
- ✅ No user churn due to connection issues
- ✅ Migration completed before deadline

---

## References

- **Strava Email**: Received June 1, 2026
- **Strava Developer FAQ**: Check API settings dashboard for link
- **Strava API Settings**: https://www.strava.com/settings/api
- **API Agreement**: Updated June 1, 2026
- **API Policy**: New as of June 1, 2026

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | Tim Hibbard | Initial migration plan created |
| | | |

---

## Appendix A: Complete File List

### Backend Lambda Functions Requiring Changes

1. `backend/auth_callback/lambda_function.py` - OAuth token exchange
2. `backend/auth_start/lambda_function.py` - OAuth authorization initiation
3. `backend/auth_disconnect/lambda_function.py` - Token revocation (new logic)
4. `backend/scheduled_activity_update/lambda_function.py` - Scheduled updates
5. `backend/fetch_activities/lambda_function.py` - User-initiated fetch
6. `backend/backfill_athlete_count/lambda_function.py` - Historical backfill
7. `backend/update_activities/lambda_function.py` - Activity updates
8. `backend/webhook_processor/lambda_function.py` - Real-time webhooks
9. `backend/admin_update_activities/lambda_function.py` - Admin operations
10. `backend/user_update_activities/lambda_function.py` - User updates
11. `backend/admin_backfill_activities/lambda_function.py` - Admin backfill

### Frontend Files Requiring Changes

1. `src/pages/ConnectStrava.jsx` - OAuth authorization URL

### Total Files to Modify: 12

---

## Appendix B: Search/Replace Script

```bash
#!/bin/bash
# migrate_strava_urls.sh - Automated URL migration script
# Usage: ./migrate_strava_urls.sh [--dry-run]

DRY_RUN=false
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
    echo "DRY RUN MODE - No files will be modified"
fi

# Old and new URLs
OLD_URL="https://www.strava.com/api/v3"
NEW_URL="https://www.api-v3.strava.com"

# Find all Python files in backend directory
FILES=$(find backend -name "*.py" -type f)

echo "Files to process:"
echo "$FILES"
echo ""

for file in $FILES; do
    if grep -q "$OLD_URL" "$file"; then
        echo "Processing: $file"
        
        if [ "$DRY_RUN" = true ]; then
            echo "  Would replace: $OLD_URL -> $NEW_URL"
            grep -n "$OLD_URL" "$file"
        else
            # Create backup
            cp "$file" "$file.bak"
            
            # Perform replacement
            sed -i '' "s|$OLD_URL|$NEW_URL|g" "$file"
            
            echo "  ✓ Replaced URLs"
        fi
    fi
done

# Process frontend file
FRONTEND_FILE="src/pages/ConnectStrava.jsx"
if [ -f "$FRONTEND_FILE" ]; then
    if grep -q "www.strava.com/oauth/authorize" "$FRONTEND_FILE"; then
        echo "Processing: $FRONTEND_FILE"
        
        if [ "$DRY_RUN" = true ]; then
            echo "  Would replace OAuth authorize URL"
            grep -n "www.strava.com/oauth/authorize" "$FRONTEND_FILE"
        else
            cp "$FRONTEND_FILE" "$FRONTEND_FILE.bak"
            sed -i '' "s|https://www.strava.com/oauth/authorize|https://www.api-v3.strava.com/oauth/authorize|g" "$FRONTEND_FILE"
            echo "  ✓ Replaced OAuth URL"
        fi
    fi
fi

if [ "$DRY_RUN" = false ]; then
    echo ""
    echo "Migration complete! Backup files created with .bak extension"
    echo "Review changes with: git diff"
    echo "Remove backups with: find . -name '*.bak' -delete"
fi
```

---

## Appendix C: Testing Checklist

### Pre-Deployment Testing

- [ ] **OAuth Authorization Flow**
  - [ ] New user can connect Strava account
  - [ ] Authorization redirects correctly
  - [ ] Token exchange successful
  - [ ] User data fetched correctly

- [ ] **Token Refresh Flow**
  - [ ] Expired token refreshes automatically
  - [ ] Refresh token stored correctly
  - [ ] No authentication errors after refresh

- [ ] **Token Revocation Flow**
  - [ ] Disconnect button works
  - [ ] Strava token revoked via API
  - [ ] Local tokens cleared
  - [ ] User redirected correctly

- [ ] **Activity Fetching**
  - [ ] Manual refresh works
  - [ ] Scheduled updates work
  - [ ] Backfill historical activities works
  - [ ] Activity details fetched correctly

- [ ] **Webhook Processing**
  - [ ] New activity triggers webhook
  - [ ] Activity data fetched
  - [ ] Trail matching runs
  - [ ] Leaderboard updated

- [ ] **Error Handling**
  - [ ] Rate limit errors handled gracefully
  - [ ] Network errors retry correctly
  - [ ] Invalid tokens refresh automatically
  - [ ] User-facing error messages clear

### Post-Deployment Validation

- [ ] **Monitoring (Day 1)**
  - [ ] Check CloudWatch Logs for errors
  - [ ] Verify successful API calls
  - [ ] Check Lambda error metrics
  - [ ] Review API Gateway logs

- [ ] **User Testing (Day 1-3)**
  - [ ] Test with personal account
  - [ ] Test with 2-3 volunteer accounts
  - [ ] Monitor support channels
  - [ ] Check for user reports

- [ ] **Performance (Week 1)**
  - [ ] Compare API response times
  - [ ] Check Lambda duration metrics
  - [ ] Monitor rate limit usage
  - [ ] Verify no degradation

- [ ] **Business Metrics (Week 1-4)**
  - [ ] Track new user signups
  - [ ] Monitor connection success rate
  - [ ] Check activity sync completion rate
  - [ ] Verify no increase in churn

---

*End of Strava API Migration Plan*
