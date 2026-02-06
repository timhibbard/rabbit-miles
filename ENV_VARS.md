# Environment Variables - Complete Reference

This document provides a complete list of all environment variables required for RabbitMiles to function correctly. Use this checklist to verify your deployment configuration.

## Critical Notes

⚠️ **APP_SECRET MUST be the same across all Lambdas that use it** (auth_callback, me, auth_disconnect)
⚠️ **Do NOT commit secrets to GitHub** - use AWS Lambda environment variables or Secrets Manager
⚠️ **FRONTEND_URL must NOT have a trailing slash**
⚠️ **API_BASE_URL should NOT include the stage path when using custom domain** (e.g., `https://api.rabbitmiles.com` not `https://api.rabbitmiles.com/prod`)

---

## Frontend Environment Variables

Location: Root `.env` file (for Vite build)

### Required Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `https://api.rabbitmiles.com` | Full URL to API Gateway (custom domain) or AWS endpoint. Used by frontend to make API calls. |

### Validation
```bash
# Check if set in .env file
grep VITE_API_BASE_URL .env

# Should output something like:
# VITE_API_BASE_URL=https://api.rabbitmiles.com
```

---

## Backend Lambda Environment Variables

All backend Lambdas require environment variables set in AWS Lambda console or via IaC (Terraform, CloudFormation, SAM, etc.).

### 1. auth_start Lambda

**Purpose**: Initiates Strava OAuth flow, generates state token, redirects to Strava.

**Function Name**: `rabbitmiles-auth-start` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | ✅ Yes | `https://api.rabbitmiles.com` | API Gateway URL (custom domain). Used to construct redirect URIs. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL (NO trailing slash). Used for OAuth redirect_uri. |
| `STRAVA_CLIENT_ID` | ✅ Yes | `123456` | Strava application client ID from Strava API settings. |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. Required for OAuth state storage. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement` (for database operations)
- `secretsmanager:GetSecretValue` (for DB credentials)

**Database Requirements**:
- `oauth_states` table must exist (see migration 001)

---

### 2. auth_callback Lambda

**Purpose**: Handles OAuth callback from Strava, exchanges code for tokens, creates user session.

**Function Name**: `rabbitmiles-auth-callback` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | ✅ Yes | `https://api.rabbitmiles.com` | API Gateway URL. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL (NO trailing slash). **Must exactly match auth_start**. |
| `APP_SECRET` | ✅ Yes | `<long-random-string>` | Secret key for signing session tokens. **Must be same as me Lambda**. Generate with: `openssl rand -base64 32` |
| `STRAVA_CLIENT_ID` | ✅ Yes | `123456` | Strava application client ID. |
| `STRAVA_CLIENT_SECRET` | ✅ Yes* | `<secret>` | Strava application client secret. *Can use STRAVA_SECRET_ARN instead. |
| `STRAVA_SECRET_ARN` | ⚠️ Optional | `arn:aws:secretsmanager:...` | Alternative to STRAVA_CLIENT_SECRET. JSON: `{"client_id":"...","client_secret":"..."}` |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |
| `FETCH_ACTIVITIES_LAMBDA_ARN` | ⚠️ Optional | `arn:aws:lambda:us-east-1:123456789012:function:rabbitmiles-fetch-activities` | ARN of fetch_activities Lambda. If set, new users will have activities fetched automatically. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue` (for DB credentials and optionally Strava credentials)
- `lambda:InvokeFunction` (if FETCH_ACTIVITIES_LAMBDA_ARN is set, to trigger automatic activity fetch for new users)

**Database Requirements**:
- `oauth_states` table must exist (for state validation)
- `users` table must exist (for storing user data)

**Critical Configuration**:
- `APP_SECRET` must be identical to me Lambda
- `FRONTEND_URL` must exactly match auth_start Lambda
- Lambda must NOT be in a VPC (RDS Data API doesn't require VPC)

---

### 3. me Lambda

**Purpose**: Returns authenticated user information based on session cookie.

**Function Name**: `rabbitmiles-me` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `APP_SECRET` | ✅ Yes | `<long-random-string>` | Secret key for verifying session tokens. **Must match auth_callback exactly**. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL for CORS headers. Must match origin of frontend requests. |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |
| `ADMIN_ATHLETE_IDS` | ⚠️ Optional | `3519964,12345,67890` | Comma-separated list of Strava athlete IDs that have admin access. Used to set `is_admin` flag in response. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`

**Database Requirements**:
- `users` table must exist

**Critical Configuration**:
- `APP_SECRET` must be identical to auth_callback Lambda
- Lambda must NOT be in a VPC

---

### 4. auth_disconnect Lambda

**Purpose**: Clears user tokens from database and session cookie.

**Function Name**: `rabbitmiles-auth-disconnect` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | ✅ Yes | `https://api.rabbitmiles.com` | API Gateway URL. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL (NO trailing slash). |
| `APP_SECRET` | ✅ Yes | `<long-random-string>` | Secret key for verifying session tokens. **Must match auth_callback and me**. |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`

---

### 5. fetch_activities Lambda

**Purpose**: Fetches activities from Strava API and stores them in the database. Can be invoked via API Gateway (user-initiated) or directly from auth_callback (for new users).

**Function Name**: `rabbitmiles-fetch-activities` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `APP_SECRET` | ✅ Yes | `<long-random-string>` | Secret key for verifying session tokens (for API Gateway invocations). **Must match auth_callback and me**. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL for CORS headers. |
| `STRAVA_CLIENT_ID` | ✅ Yes | `123456` | Strava application client ID. |
| `STRAVA_CLIENT_SECRET` | ✅ Yes* | `<secret>` | Strava application client secret. *Can use STRAVA_SECRET_ARN instead. |
| `STRAVA_SECRET_ARN` | ⚠️ Optional | `arn:aws:secretsmanager:...` | Alternative to STRAVA_CLIENT_SECRET. JSON: `{"client_id":"...","client_secret":"..."}` |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |
| `MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN` | ⚠️ Optional | `arn:aws:lambda:us-east-1:123456789012:function:rabbitmiles-match-unmatched-activities` | ARN of match_unmatched_activities Lambda. If set, trail matching will be triggered automatically after fetching activities. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement` (for database operations)
- `secretsmanager:GetSecretValue` (for DB credentials and optionally Strava credentials)
- `lambda:InvokeFunction` (if MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN is set, to trigger trail matching)

**Database Requirements**:
- `users` table must exist (for token refresh)
- `activities` table must exist (for storing activities)

**Critical Configuration**:
- Lambda must NOT be in a VPC (RDS Data API doesn't require VPC)
- If MATCH_UNMATCHED_ACTIVITIES_LAMBDA_ARN is set, trail matching will run automatically after activities are fetched

---

### 6. admin_list_users Lambda

**Purpose**: Admin-only endpoint that lists all users in the system (excluding sensitive tokens).

**Function Name**: `rabbitmiles-admin-list-users` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `APP_SECRET` | ✅ Yes | `<long-random-string>` | Secret key for verifying session tokens. **Must match auth_callback and me**. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL for CORS headers. |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |
| `ADMIN_ATHLETE_IDS` | ✅ Yes | `3519964,12345,67890` | Comma-separated list of Strava athlete IDs with admin access. Only these users can access this endpoint. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`

**Database Requirements**:
- `users` table must exist

**Security Notes**:
- Returns 403 Forbidden if authenticated user is not in admin allowlist
- Access/refresh tokens are NOT included in response
- All responses include `Cache-Control: no-store` header
- All access attempts are audit logged to CloudWatch

---

### 7. admin_user_activities Lambda

**Purpose**: Admin-only endpoint that lists activities for a specific user.

**Function Name**: `rabbitmiles-admin-user-activities` (adjust to your naming)

**Handler**: `lambda_function.handler`

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `APP_SECRET` | ✅ Yes | `<long-random-string>` | Secret key for verifying session tokens. **Must match auth_callback and me**. |
| `FRONTEND_URL` | ✅ Yes | `https://rabbitmiles.com` | Frontend URL for CORS headers. |
| `DB_CLUSTER_ARN` | ✅ Yes | `arn:aws:rds:us-east-1:123456789012:cluster:rabbitmiles-db` | Aurora Serverless cluster ARN. |
| `DB_SECRET_ARN` | ✅ Yes | `arn:aws:secretsmanager:us-east-1:123456789012:secret:rabbitmiles-db-abc123` | Secrets Manager ARN containing DB credentials. |
| `DB_NAME` | ⚠️ Optional | `postgres` | Database name. Defaults to `postgres` if not set. |
| `ADMIN_ATHLETE_IDS` | ✅ Yes | `3519964,12345,67890` | Comma-separated list of Strava athlete IDs with admin access. Only these users can access this endpoint. |

**IAM Permissions Required**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`

**Database Requirements**:
- `activities` table must exist

**Security Notes**:
- Returns 403 Forbidden if authenticated user is not in admin allowlist
- All responses include `Cache-Control: no-store` header
- All access attempts are audit logged to CloudWatch

---

### Other Backend Lambdas

For completeness, other Lambdas in the system (activities, trails, webhooks) require similar database and API configuration:

**Common variables across all backend Lambdas**:
- `DB_CLUSTER_ARN` - Database cluster ARN
- `DB_SECRET_ARN` - Database credentials secret ARN
- `DB_NAME` - Database name (default: postgres)
- `API_BASE_URL` - API Gateway URL with stage (if needed)
- `FRONTEND_URL` - Frontend URL for CORS (if Lambda is called from frontend)

**Activity/webhook-specific variables**:
- May require `APP_SECRET` if they verify session tokens
- May require Strava tokens if they call Strava API

---

## How to Set Environment Variables

### AWS Console
1. Go to AWS Lambda console
2. Select your function
3. Go to Configuration → Environment variables
4. Click Edit
5. Add/update variables
6. Click Save

### AWS CLI
```bash
aws lambda update-function-configuration \
  --function-name rabbitmiles-auth-callback \
  --environment Variables="{
    API_BASE_URL=https://api.rabbitmiles.com,
    FRONTEND_URL=https://rabbitmiles.com,
    APP_SECRET=your-secret-here,
    STRAVA_CLIENT_ID=123456,
    STRAVA_CLIENT_SECRET=your-secret,
    DB_CLUSTER_ARN=arn:aws:rds:...,
    DB_SECRET_ARN=arn:aws:secretsmanager:...,
    DB_NAME=postgres
  }"
```

### Terraform/IaC
```hcl
resource "aws_lambda_function" "auth_callback" {
  # ... other config ...
  
  environment {
    variables = {
      API_BASE_URL        = "https://api.rabbitmiles.com"
      FRONTEND_URL        = "https://rabbitmiles.com"
      APP_SECRET          = var.app_secret
      STRAVA_CLIENT_ID    = var.strava_client_id
      STRAVA_CLIENT_SECRET = var.strava_client_secret
      DB_CLUSTER_ARN      = aws_rds_cluster.main.arn
      DB_SECRET_ARN       = aws_secretsmanager_secret.db.arn
      DB_NAME             = "postgres"
    }
  }
}
```

---

## Verification Checklist

Use this checklist to verify all environment variables are set correctly:

### ✅ Frontend
- [ ] `.env` file exists in project root
- [ ] `VITE_API_BASE_URL` is set to custom domain or AWS endpoint
- [ ] URL points to correct API Gateway endpoint
- [ ] After changing, rebuild frontend: `npm run build`

### ✅ auth_start Lambda
- [ ] `API_BASE_URL` set (includes stage)
- [ ] `FRONTEND_URL` set (no trailing slash)
- [ ] `STRAVA_CLIENT_ID` set
- [ ] `DB_CLUSTER_ARN` set
- [ ] `DB_SECRET_ARN` set
- [ ] Lambda has `rds-data:ExecuteStatement` permission
- [ ] Lambda has `secretsmanager:GetSecretValue` permission
- [ ] `oauth_states` table exists in database

### ✅ auth_callback Lambda
- [ ] `API_BASE_URL` set (includes stage)
- [ ] `FRONTEND_URL` set (matches auth_start exactly)
- [ ] `APP_SECRET` set (long random string)
- [ ] `STRAVA_CLIENT_ID` set
- [ ] `STRAVA_CLIENT_SECRET` or `STRAVA_SECRET_ARN` set
- [ ] `DB_CLUSTER_ARN` set
- [ ] `DB_SECRET_ARN` set
- [ ] `FETCH_ACTIVITIES_LAMBDA_ARN` set (optional, for automatic activity fetch)
- [ ] Lambda has required IAM permissions (including `lambda:InvokeFunction` if using auto-fetch)
- [ ] `users` and `oauth_states` tables exist

### ✅ me Lambda
- [ ] `APP_SECRET` set (matches auth_callback)
- [ ] `FRONTEND_URL` set (for CORS)
- [ ] `DB_CLUSTER_ARN` set
- [ ] `DB_SECRET_ARN` set
- [ ] Lambda has required IAM permissions
- [ ] `users` table exists

### ✅ auth_disconnect Lambda
- [ ] `API_BASE_URL` set
- [ ] `FRONTEND_URL` set
- [ ] `APP_SECRET` set (matches auth_callback and me)
- [ ] `DB_CLUSTER_ARN` set
- [ ] `DB_SECRET_ARN` set
- [ ] Lambda has required IAM permissions

### ✅ Cross-Lambda Consistency
- [ ] `APP_SECRET` is identical in auth_callback, me, and auth_disconnect
- [ ] `FRONTEND_URL` is identical across all Lambdas (no trailing slash)
- [ ] `API_BASE_URL` is identical in auth_start, auth_callback, auth_disconnect
- [ ] `DB_CLUSTER_ARN` is identical across all Lambdas
- [ ] `DB_SECRET_ARN` is identical across all Lambdas
- [ ] `DB_NAME` is identical across all Lambdas (or all use default)

---

## Troubleshooting

### Problem: "Server configuration error"
**Symptom**: Lambda returns 500 with "server configuration error" in response

**Solution**: Check CloudWatch logs for specific missing environment variable:
```
ERROR - Missing APP_SECRET environment variable
ERROR - Missing DB_CLUSTER_ARN or DB_SECRET_ARN environment variable
ERROR - FRONTEND_URL environment variable not set
ERROR - STRAVA_CLIENT_ID environment variable not set
```

### Problem: "Invalid session" or "Not authenticated"
**Symptom**: `/me` returns 401

**Solution**: 
1. Verify `APP_SECRET` is identical in auth_callback and me Lambda
2. Check CloudWatch logs for specific error
3. Verify session cookie is being sent (check browser DevTools → Network → Request Headers)

### Problem: OAuth fails with "invalid state"
**Symptom**: Callback returns 400 "invalid state"

**Solution**:
1. Verify `oauth_states` table exists (run migration 001)
2. Check auth_start logs to confirm state was stored in database
3. Verify DB permissions are correct

### Problem: User not found after successful OAuth
**Symptom**: `/me` returns 404 after completing OAuth

**Solution**:
1. Check auth_callback logs for database errors during user upsert
2. Verify `users` table exists and has correct schema
3. Check Lambda has `rds-data:ExecuteStatement` permission

---

## Quick Validation Script

You can validate environment variables are set correctly by checking CloudWatch logs when each Lambda starts up. Each Lambda now logs its configuration on startup:

```
LOG - Environment variables OK
LOG -   DB_CLUSTER_ARN: arn:aws:rds:us-east-1:...
LOG -   DB_SECRET_ARN: arn:aws:secretsmanager:...
LOG -   DB_NAME: postgres
LOG -   APP_SECRET length: 44 bytes
LOG -   FRONTEND_URL: https://rabbitmiles.com
```

If any required variable is missing, you'll see:
```
ERROR - Missing APP_SECRET environment variable
```

---

## Security Best Practices

1. **Never commit secrets**: Use AWS Secrets Manager or Lambda environment variables
2. **Rotate APP_SECRET**: If compromised, generate new secret and update all Lambdas
3. **Use HTTPS only**: All URLs should use https://
4. **Limit IAM permissions**: Grant only required permissions to Lambda execution roles
5. **Enable CloudWatch Logs**: Keep logs enabled for debugging and security monitoring
6. **Secure cookies**: Cookies use HttpOnly, Secure, SameSite=None, and Partitioned attributes

---

## Generating Secrets

### Generate APP_SECRET
```bash
# Generate a secure random string (44 characters base64)
openssl rand -base64 32

# Or in Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Store in AWS Secrets Manager (Optional)
```bash
# Create secret
aws secretsmanager create-secret \
  --name rabbitmiles-app-secret \
  --secret-string "$(openssl rand -base64 32)"

# Get ARN
aws secretsmanager describe-secret \
  --secret-id rabbitmiles-app-secret \
  --query ARN --output text
```

Then in Lambda, you can fetch it:
```python
import boto3
sm = boto3.client('secretsmanager')
response = sm.get_secret_value(SecretId='rabbitmiles-app-secret')
APP_SECRET = response['SecretString'].encode()
```

But for simplicity, using Lambda environment variables is fine for APP_SECRET since it's already encrypted at rest by AWS.

---

## Additional Resources

- [TROUBLESHOOTING_AUTH.md](TROUBLESHOOTING_AUTH.md) - Detailed auth flow debugging
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment instructions
- [backend/migrations/README.md](backend/migrations/README.md) - Database schema setup

---

**Last Updated**: 2026-02-05
**Maintained by**: RabbitMiles Team
