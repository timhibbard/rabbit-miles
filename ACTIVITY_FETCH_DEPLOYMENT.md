# Activity Fetching Feature - Deployment Guide

## Overview

This feature adds the ability to:
1. Fetch past activities from Strava API and store them in the database
2. Display recent activities on the Dashboard screen

## Backend Changes

### 1. Database Migration

**File:** `backend/migrations/003_create_activities_table.sql`

Run this migration to create the activities table:

```bash
aws rds-data execute-statement \
  --resource-arn "arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:DATABASE_CLUSTER" \
  --secret-arn "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:SECRET_NAME" \
  --database "postgres" \
  --sql "$(cat backend/migrations/003_create_activities_table.sql)"
```

### 2. New Lambda Functions

#### fetch_activities Lambda

**Purpose:** Fetches activities from Strava API for all users and stores them in the database.

**Directory:** `backend/fetch_activities/`

**Handler:** `lambda_function.handler`

**Environment Variables Required:**
- `DB_CLUSTER_ARN` - RDS cluster ARN
- `DB_SECRET_ARN` - RDS secret ARN for database credentials
- `DB_NAME` - Database name (default: "postgres")
- `APP_SECRET` - Secret for session token verification (same as other authenticated endpoints)
- `STRAVA_CLIENT_ID` - Strava OAuth client ID
- `STRAVA_CLIENT_SECRET` - Strava OAuth client secret (or use STRAVA_SECRET_ARN)
- `STRAVA_SECRET_ARN` - Alternative to STRAVA_CLIENT_SECRET
- `FRONTEND_URL` - Frontend URL for CORS

**API Gateway Route:** `POST /activities/fetch`

**Features:**
- Requires authentication via session cookie
- Fetches activities only for the authenticated user
- Automatically refreshes expired Strava tokens (with 5-minute buffer)
- Fetches up to 30 most recent activities
- Handles errors gracefully with proper CORS headers
- Returns number of activities stored

**Usage:**
- Triggered by authenticated users via API Gateway (POST /activities/fetch)
- User must be logged in with valid session cookie
- Each user can only refresh their own activities

#### get_activities Lambda

**Purpose:** Returns activities for the authenticated user.

**Directory:** `backend/get_activities/`

**Handler:** `lambda_function.handler`

**Environment Variables Required:**
- `DB_CLUSTER_ARN` - RDS cluster ARN
- `DB_SECRET_ARN` - RDS secret ARN for database credentials
- `DB_NAME` - Database name (default: "postgres")
- `APP_SECRET` - Secret for session token verification
- `FRONTEND_URL` - Frontend URL for CORS

**API Gateway Route:** `GET /activities`

**Query Parameters:**
- `limit` - Number of activities to return (default: 10, max: 100)
- `offset` - Offset for pagination (default: 0)

**Response Format:**
```json
{
  "activities": [
    {
      "id": 123,
      "strava_activity_id": 456789,
      "name": "Morning Run",
      "distance": 5000.0,
      "moving_time": 1800,
      "elapsed_time": 1900,
      "total_elevation_gain": 50.0,
      "type": "Run",
      "start_date": "2024-01-31T10:00:00Z",
      "start_date_local": "2024-01-31T06:00:00-04:00",
      "timezone": "America/New_York"
    }
  ],
  "limit": 10,
  "offset": 0,
  "count": 1
}
```

### 3. Lambda Deployment

For each new Lambda function:

1. Create the Lambda function in AWS Console or via CLI
2. Set the runtime to Python (latest supported version)
3. Configure environment variables
4. Grant the Lambda execution role permissions to:
   - Access RDS Data API (`rds-data:ExecuteStatement`)
   - Read database secrets (`secretsmanager:GetSecretValue`)
   - Read Strava secrets if using STRAVA_SECRET_ARN
5. Add the Lambda to API Gateway routes
6. Deploy the API Gateway

## Frontend Changes

### 1. API Utility Updates

**File:** `src/utils/api.js`

Added `fetchActivities` function to call the `/activities` endpoint with pagination support.

### 2. Dashboard Updates

**File:** `src/pages/Dashboard.jsx`

**Changes:**
- Fetches activities on component mount after authentication
- Displays activities with:
  - Activity name and date
  - Distance in miles
  - Duration in MM:SS format
  - Pace in MM:SS/mi format (with N/A for zero distance/time)
  - Activity type badge
- Shows loading state while fetching
- Shows error state if fetch fails
- Shows empty state if no activities

**Features:**
- Automatic conversion from meters to miles (using METERS_TO_MILES constant)
- Proper zero handling for pace calculation
- Responsive grid layout for activity stats
- Hover effects for better UX

## Deployment Steps

### Backend Deployment

1. **Run the database migration:**
   ```bash
   aws rds-data execute-statement \
     --resource-arn "$DB_CLUSTER_ARN" \
     --secret-arn "$DB_SECRET_ARN" \
     --database "postgres" \
     --sql "$(cat backend/migrations/003_create_activities_table.sql)"
   ```

2. **Deploy fetch_activities Lambda:**
   ```bash
   cd backend/fetch_activities
   zip -r lambda.zip lambda_function.py
   aws lambda create-function \
     --function-name rabbitmiles-fetch-activities \
     --runtime python3.x \
     --role arn:aws:iam::ACCOUNT_ID:role/lambda-rds-role \
     --handler lambda_function.handler \
     --zip-file fileb://lambda.zip \
     --environment Variables="{DB_CLUSTER_ARN=$DB_CLUSTER_ARN,DB_SECRET_ARN=$DB_SECRET_ARN,...}"
   ```

3. **Deploy get_activities Lambda:**
   ```bash
   cd backend/get_activities
   zip -r lambda.zip lambda_function.py
   aws lambda create-function \
     --function-name rabbitmiles-get-activities \
     --runtime python3.x \
     --role arn:aws:iam::ACCOUNT_ID:role/lambda-rds-role \
     --handler lambda_function.handler \
     --zip-file fileb://lambda.zip \
     --environment Variables="{DB_CLUSTER_ARN=$DB_CLUSTER_ARN,DB_SECRET_ARN=$DB_SECRET_ARN,...}"
   ```

4. **Add routes to API Gateway:**
   - `POST /activities/fetch` → rabbitmiles-fetch-activities
   - `GET /activities` → rabbitmiles-get-activities

5. **Deploy API Gateway**

**Note:** The `fetch_activities` endpoint now requires authentication and only syncs activities for the authenticated user. CloudWatch-based scheduled syncing for all users would require a separate Lambda function or modified implementation.

### Frontend Deployment

The frontend changes will be automatically deployed by GitHub Actions when merged to main.

## Initial Activity Sync

After deployment, users can trigger activity fetch by clicking the "Refresh Activities" button on the Dashboard. This requires the user to be authenticated.

Alternatively, you can test the endpoint directly:

```bash
curl -X POST https://YOUR-API-GATEWAY-URL/prod/activities/fetch \
  -H "Content-Type: application/json" \
  -H "Cookie: rm_session=YOUR_SESSION_TOKEN" \
  --cookie-jar cookies.txt \
  --cookie cookies.txt
```

## Testing

1. **Test authentication:** Visit the Dashboard and verify you're logged in
2. **Trigger activity fetch:** Use the curl command above
3. **Verify activities appear:** Refresh the Dashboard to see activities
4. **Test pagination:** Check that the limit/offset parameters work on the API
5. **Test error handling:** Disconnect from Strava and verify graceful error messages

## Monitoring

Monitor the Lambda functions in CloudWatch:
- Check for errors in CloudWatch Logs
- Monitor duration and memory usage
- Set up alarms for failures

## Security Notes

- All endpoints use cookie-based authentication
- Session tokens are verified before accessing or refreshing data
- Users can only refresh their own activities (not other users')
- Strava tokens are automatically refreshed when expired
- 5-minute buffer prevents token expiration during API calls
- No sensitive data is exposed to the frontend
- Proper CORS headers returned even on authentication failures

## Future Enhancements

Potential improvements:
1. Paginated activity list on Dashboard
2. Activity detail view with map
3. Trail matching (identify activities on Swamp Rabbit Trail)
4. Activity statistics (weekly/monthly totals)
5. Webhook support for real-time activity sync
6. Activity filtering by type, date range
