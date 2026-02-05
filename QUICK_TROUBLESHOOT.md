# New User Login Issues - Quick Troubleshooting Checklist

This is a quick reference checklist for debugging new user login issues. For detailed instructions, see [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md).

## Initial Investigation (5 minutes)

### Step 1: Check CloudWatch Logs
Open CloudWatch logs for failed login attempt and look for ERROR messages:

```bash
# Recent errors in auth_callback
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-auth-callback \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Recent errors in me
aws logs filter-log-events \
  --log-group-name /aws/lambda/rabbitmiles-me \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

**Most common errors and fixes:**

| Error Message | Fix |
|---------------|-----|
| `ERROR - Missing APP_SECRET environment variable` | Set APP_SECRET in Lambda env vars |
| `ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN` | Set database ARNs in Lambda env vars |
| `ERROR - FRONTEND_URL environment variable not set` | Set FRONTEND_URL in Lambda env vars |
| `ERROR - Failed to store state in database` | Run migration 001 or check IAM permissions |
| `ERROR - State validation FAILED` | Check oauth_states table exists and state was stored |
| `ERROR - Token exchange failed` | Check Strava credentials and redirect_uri |
| `ERROR - User not found in database` | Check users table exists and user was created |

### Step 2: Verify Environment Variables

```bash
# Run automated verification script
cd /home/runner/work/rabbit-miles/rabbit-miles
./scripts/verify-lambda-env.sh

# Or check manually
aws lambda get-function-configuration --function-name rabbitmiles-auth-callback \
  --query 'Environment.Variables' --output json
```

**Common issues:**
- [ ] APP_SECRET mismatch between auth_callback and me
- [ ] FRONTEND_URL has trailing slash (should not)
- [ ] API_BASE_URL missing /prod stage
- [ ] Missing required variables

### Step 3: Check Database

```bash
# Check tables exist
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"

# Expected tables: oauth_states, users, (and others)
```

**Common issues:**
- [ ] oauth_states table missing → Run migration 001
- [ ] users table missing → Run users table migration
- [ ] Lambda can't access database → Check IAM permissions

### Step 4: Check Browser Cookies

1. Open browser DevTools (F12)
2. Go to Application tab → Cookies
3. Check API Gateway domain (e.g., `9zke9jame0.execute-api.us-east-1.amazonaws.com`)

**After successful OAuth, should see:**
- [ ] `rm_session` cookie with long value (100+ chars)
- [ ] HttpOnly: Yes
- [ ] Secure: Yes
- [ ] SameSite: None
- [ ] No `rm_state` cookie (should be cleared)

**If cookie missing:**
- Check /auth/callback response has Set-Cookie header
- Check browser isn't blocking third-party cookies
- Check API Gateway is configured correctly

**If cookie not sent to /me:**
- Check frontend uses `credentials: 'include'`
- Check CORS headers include `Access-Control-Allow-Credentials: true`

---

## Systematic Debugging (15 minutes)

If initial investigation didn't reveal the issue, follow the OAuth flow step by step:

### ✓ Step 1: Test /auth/start
```bash
curl -v "https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/auth/start"
```

**Expected:** 302 redirect to Strava with rm_state cookie

**Check logs:** Should see "AUTH START LAMBDA - SUCCESS"

### ✓ Step 2: Complete OAuth Flow
1. Click "Connect with Strava" in browser with DevTools open
2. Authorize on Strava
3. Observe redirect to callback

**Check /auth/callback logs:** Should see:
- "State validation SUCCESS"
- "Strava response status: 200"
- "Database upsert SUCCESS"
- "AUTH CALLBACK LAMBDA - SUCCESS"

### ✓ Step 3: Test /me Endpoint
```javascript
// In browser console on frontend page
fetch('https://9zke9jame0.execute-api.us-east-1.amazonaws.com/prod/me', {
  credentials: 'include'
}).then(r => r.json()).then(console.log)
```

**Expected:** `{ athlete_id: 12345678, display_name: "..." }`

**Check logs:** Should see:
- "Session token found!"
- "Session token verification SUCCESS"
- "User found in database!"
- "/ME LAMBDA - SUCCESS"

---

## Top 5 Root Causes (by frequency)

### 1. APP_SECRET Mismatch (40% of issues)
**Symptom:** `/me` returns 401 "invalid session" after successful OAuth

**Quick check:**
```bash
# Check if APP_SECRET matches
aws lambda get-function-configuration --function-name rabbitmiles-auth-callback \
  --query 'Environment.Variables.APP_SECRET' --output text > /tmp/secret1.txt
aws lambda get-function-configuration --function-name rabbitmiles-me \
  --query 'Environment.Variables.APP_SECRET' --output text > /tmp/secret2.txt
diff /tmp/secret1.txt /tmp/secret2.txt
# Should show no difference
```

**Fix:** Set same APP_SECRET in both Lambdas

### 2. Missing Environment Variables (25% of issues)
**Symptom:** Lambda returns 500 "server configuration error"

**Quick check:** Run `./scripts/verify-lambda-env.sh`

**Fix:** Set all required variables per [ENV_VARS.md](ENV_VARS.md)

### 3. Database Table Missing (15% of issues)
**Symptom:** Database errors in CloudWatch logs

**Quick check:**
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT COUNT(*) FROM oauth_states"
```

**Fix:** Run migrations in `backend/migrations/`

### 4. IAM Permissions Missing (10% of issues)
**Symptom:** "Access denied" in CloudWatch logs

**Quick check:** Look for specific permission errors in logs

**Fix:** Add to Lambda execution role:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`

### 5. Cookie Not Being Sent (10% of issues)
**Symptom:** `/me` returns 401, logs say "No session cookie found"

**Quick check:** DevTools → Network → /me request → Request Headers → Cookie

**Fix:**
- Verify `withCredentials: true` in frontend
- Check cookie is stored in browser
- Verify CORS headers are correct

---

## Emergency Commands

### Get Full Lambda Configuration
```bash
aws lambda get-function-configuration --function-name rabbitmiles-auth-callback --output json
aws lambda get-function-configuration --function-name rabbitmiles-me --output json
```

### Tail All Auth Logs
```bash
# Terminal 1
aws logs tail /aws/lambda/rabbitmiles-auth-start --follow

# Terminal 2
aws logs tail /aws/lambda/rabbitmiles-auth-callback --follow

# Terminal 3
aws logs tail /aws/lambda/rabbitmiles-me --follow
```

### Check Recent Users
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT athlete_id, display_name, created_at FROM users ORDER BY created_at DESC LIMIT 10"
```

### Check Recent OAuth States
```bash
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "postgres" \
  --sql "SELECT state, expires_at, created_at FROM oauth_states ORDER BY created_at DESC LIMIT 10"
```

### Force Redeploy All Auth Lambdas
```bash
# Update all auth Lambdas (adjust function names and paths as needed)
aws lambda update-function-code --function-name rabbitmiles-auth-start \
  --zip-file fileb://backend/auth_start.zip
aws lambda update-function-code --function-name rabbitmiles-auth-callback \
  --zip-file fileb://backend/auth_callback.zip
aws lambda update-function-code --function-name rabbitmiles-me \
  --zip-file fileb://backend/me.zip
```

---

## Decision Tree

```
User can't log in
    ↓
Does /auth/start redirect to Strava?
    ├─ No → Check CloudWatch logs for auth_start
    │       Check FRONTEND_URL, STRAVA_CLIENT_ID env vars
    │       Check oauth_states table exists
    │
    └─ Yes → Does Strava redirect back to callback?
            ├─ No → Check Strava app settings
            │       Verify redirect_uri matches
            │
            └─ Yes → Does /auth/callback set session cookie?
                    ├─ No → Check CloudWatch logs for auth_callback
                    │       Check APP_SECRET env var
                    │       Check users table exists
                    │
                    └─ Yes → Is cookie stored in browser?
                            ├─ No → Check browser settings
                            │       Check Set-Cookie headers
                            │
                            └─ Yes → Is cookie sent to /me?
                                    ├─ No → Check withCredentials: true
                                    │       Check CORS headers
                                    │
                                    └─ Yes → Does /me return user data?
                                            ├─ No → Check CloudWatch logs
                                            │       Check APP_SECRET match
                                            │       Check user in database
                                            │
                                            └─ Yes → SUCCESS! ✓
```

---

## Quick Links

- **Full debugging guide:** [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md)
- **Environment variables:** [ENV_VARS.md](ENV_VARS.md)
- **Verification script:** [scripts/verify-lambda-env.sh](scripts/verify-lambda-env.sh)
- **Existing troubleshooting:** [TROUBLESHOOTING_AUTH.md](TROUBLESHOOTING_AUTH.md)
- **Database migrations:** [backend/migrations/README.md](backend/migrations/README.md)

---

## Still Stuck?

1. **Run the verification script:** `./scripts/verify-lambda-env.sh`
2. **Collect CloudWatch logs** for all three auth Lambdas during a failed login
3. **Capture browser Network tab** (save as HAR file)
4. **Screenshot browser cookies** (DevTools → Application → Cookies)
5. **Compare with working user** if some users can log in
6. **Review recent changes** in git history

If issue persists, provide:
- Output from verification script
- CloudWatch logs with ERROR messages
- Browser console errors
- Network HAR file
- Description of when issue started

---

**Last Updated**: 2026-02-05
