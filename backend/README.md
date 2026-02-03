# Backend Lambda Functions

This directory contains all AWS Lambda functions for the RabbitMiles backend API.

## Lambda Functions

### Authentication Functions

#### `auth_start/`
**Route:** `GET /auth/start`
**Purpose:** Initiates Strava OAuth flow
- Generates random state value
- Stores state in database for validation
- Redirects to Strava authorization page

#### `auth_callback/`
**Route:** `GET /auth/callback`
**Purpose:** Handles OAuth callback from Strava
- Validates state from database
- Exchanges code for access/refresh tokens
- Upserts user record in database
- Creates signed session cookie

#### `auth_disconnect/`
**Route:** `GET /auth/disconnect`
**Purpose:** Disconnects Strava account
- Clears tokens from database
- Clears session cookie
- Redirects to frontend

### User Functions

#### `me/`
**Route:** `GET /me`
**Purpose:** Returns authenticated user info
- Verifies session cookie
- Returns athlete_id and display_name

### Activity Functions

#### `fetch_activities/`
**Route:** `POST /fetch_activities`
**Purpose:** Manually fetches activities from Strava
- Requires authentication (session cookie)
- Fetches up to 30 most recent activities
- Stores in database
- Handles token refresh

#### `get_activities/`
**Route:** `GET /activities`
**Purpose:** Returns stored activities for authenticated user
- Requires authentication (session cookie)
- Returns activities from database

### Webhook Functions

#### `webhook/`
**Route:** `GET /strava/webhook` and `POST /strava/webhook`
**Purpose:** Strava webhook endpoint
- **GET:** Subscription validation (echoes hub.challenge)
- **POST:** Receives activity events, queues to SQS
- Must respond within 2 seconds
- See [WEBHOOK_SETUP.md](../WEBHOOK_SETUP.md) for setup

**Environment Variables:**
- `WEBHOOK_VERIFY_TOKEN`: Secret token for subscription validation
- `WEBHOOK_SQS_QUEUE_URL`: SQS queue URL for async processing

#### `webhook_processor/`
**Trigger:** SQS queue messages
**Purpose:** Processes webhook events asynchronously
- Fetches activity details from Strava API
- Updates activities table
- Handles token refresh
- Implements idempotency via webhook_events table

**Environment Variables:**
- `DB_CLUSTER_ARN`: Aurora cluster ARN
- `DB_SECRET_ARN`: Database credentials secret ARN
- `DB_NAME`: Database name (default: postgres)
- `STRAVA_CLIENT_ID`: Strava API client ID
- `STRAVA_CLIENT_SECRET`: Strava API client secret
- `STRAVA_SECRET_ARN`: Alternative to separate client_id/secret

### Trail Data Functions

#### `update_trail_data/`
**Trigger:** Manual invocation (on-demand)
**Purpose:** Updates trail GeoJSON data in S3
- Downloads main trail GeoJSON from greenvilleopenmap.info
- Downloads spur trail GeoJSON from greenvilleopenmap.info
- Stores both files in S3 bucket (overwrites existing)
- Can be invoked manually via AWS Console or CLI
- No authentication required (internal-only function)

**Environment Variables:**
- `TRAIL_DATA_BUCKET`: S3 bucket name for storing trail data

**S3 Storage:**
- Main trail: `trails/main.geojson`
- Spurs: `trails/spurs.geojson`
- Total size: ~116KB
- Used by trail matching logic to determine activity metrics

## Common Environment Variables

All Lambda functions may use:
- `DB_CLUSTER_ARN`: Aurora PostgreSQL cluster ARN
- `DB_SECRET_ARN`: Secrets Manager ARN for database credentials
- `DB_NAME`: Database name (default: postgres)
- `API_BASE_URL`: API Gateway base URL (e.g., https://xyz.execute-api.us-east-1.amazonaws.com/prod)
- `FRONTEND_URL`: Frontend URL (e.g., https://timhibbard.github.io/rabbit-miles)
- `APP_SECRET`: Secret for signing session cookies
- `STRAVA_CLIENT_ID`: Strava OAuth client ID
- `STRAVA_CLIENT_SECRET`: Strava OAuth client secret
- `STRAVA_SECRET_ARN`: Alternative to separate client_id/secret env vars
- `TRAIL_DATA_BUCKET`: S3 bucket for trail GeoJSON data (used by `update_trail_data`)

## Database Access

All Lambda functions use the **AWS RDS Data API** to access the Aurora PostgreSQL database:
- No VPC required
- No database drivers needed
- Automatic connection pooling
- IAM-based authentication

### Database Tables

See `migrations/` directory for table schemas:
- `users`: User accounts with Strava tokens
- `oauth_states`: Temporary OAuth state tokens
- `activities`: Activity data from Strava
- `webhook_events`: Processed webhook events (for idempotency)

## Deployment

Lambda functions are automatically deployed via GitHub Actions when changes are pushed to the `main` branch:

```yaml
# .github/workflows/deploy-lambdas.yml
```

Manual deployment:
```bash
cd backend/<function-name>
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name <lambda-function-name> \
  --zip-file fileb://function.zip
```

## Testing

Test individual functions locally:
```python
# Example: Test auth_callback
import sys
sys.path.insert(0, 'backend/auth_callback')
import lambda_function

event = {
    "queryStringParameters": {
        "code": "test-code",
        "state": "test-state"
    }
}
result = lambda_function.handler(event, None)
print(result)
```

## Security

- **No secrets in code**: All secrets stored in environment variables or Secrets Manager
- **Parameterized SQL**: All database queries use parameterized statements
- **Cookie security**: Cookies are httpOnly, Secure, SameSite=Lax
- **Token verification**: Session tokens are signed with HMAC-SHA256
- **CORS**: Configured for frontend origin only

## Architecture

```
Frontend (GitHub Pages)
    ↓ HTTPS
API Gateway (HTTP API)
    ↓ Lambda Proxy Integration
Lambda Functions
    ↓ RDS Data API
Aurora PostgreSQL
```

Webhook flow:
```
Strava API
    ↓ HTTPS POST
API Gateway
    ↓ Lambda Proxy
webhook Lambda
    ↓ SQS
Queue
    ↓ Trigger
webhook_processor Lambda
    ↓ RDS Data API
Aurora PostgreSQL
```

## Development

### Adding a New Lambda Function

1. Create directory: `backend/new_function/`
2. Create handler: `backend/new_function/lambda_function.py`
3. Add to deployment workflow: `.github/workflows/deploy-lambdas.yml`
4. Create Lambda in AWS Console or via IaC
5. Configure environment variables
6. Add API Gateway route (if needed)
7. Update this README

### Code Style

- Use Python 3.x standard library when possible
- Minimal dependencies (avoid installing packages)
- Clear error messages with context
- Log important events for CloudWatch
- Return consistent response format:
  ```python
  {
      "statusCode": 200,
      "headers": {"Content-Type": "application/json"},
      "body": json.dumps({"key": "value"})
  }
  ```

## Monitoring

All Lambda functions log to CloudWatch Logs:
- Log group: `/aws/lambda/<function-name>`
- Retention: Configured per function
- Metrics: Duration, errors, invocations

View logs:
```bash
aws logs tail /aws/lambda/<function-name> --follow
```

## Support

For webhook setup, see [WEBHOOK_SETUP.md](../WEBHOOK_SETUP.md)
For general deployment, see [LAMBDA_DEPLOYMENT.md](../LAMBDA_DEPLOYMENT.md)
