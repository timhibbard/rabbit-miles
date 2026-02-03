# update_activities Lambda

Worker Lambda function to update activities in the database from Strava.

## Purpose

This Lambda function is designed for testing and manual data refresh scenarios. It allows you to:
- Fetch and store recent activities for a specific athlete
- Update a single activity by its Strava activity ID

## Usage

### Update Recent Activities for an Athlete

Fetch the 30 most recent activities for an athlete from Strava and store them in the database:

**JSON Body:**
```json
{
  "athlete_id": 123456
}
```

**Query String:**
```
?athlete_id=123456
```

**Response:**
```json
{
  "message": "Activities updated successfully",
  "athlete_id": 123456,
  "total_activities": 30,
  "stored": 30,
  "failed": 0
}
```

### Update a Single Activity

Fetch and update a specific activity:

**JSON Body:**
```json
{
  "athlete_id": 123456,
  "activity_id": 789012
}
```

**Query String:**
```
?athlete_id=123456&activity_id=789012
```

**Response:**
```json
{
  "message": "Activity updated successfully",
  "activity_id": 789012,
  "athlete_id": 123456
}
```

## Invocation Methods

### AWS Lambda Console

1. Go to AWS Lambda Console
2. Select `update_activities` function
3. Click "Test" tab
4. Create a test event with the JSON body format above
5. Click "Test" button

### AWS CLI

```bash
# Update activities for an athlete
aws lambda invoke \
  --function-name update_activities \
  --payload '{"athlete_id": 123456}' \
  response.json

# Update a specific activity
aws lambda invoke \
  --function-name update_activities \
  --payload '{"athlete_id": 123456, "activity_id": 789012}' \
  response.json
```

### API Gateway (if configured)

```bash
# Update activities for an athlete
curl -X POST https://your-api-gateway-url/update_activities \
  -H "Content-Type: application/json" \
  -d '{"athlete_id": 123456}'

# Update a specific activity
curl -X POST https://your-api-gateway-url/update_activities \
  -H "Content-Type: application/json" \
  -d '{"athlete_id": 123456, "activity_id": 789012}'
```

## Environment Variables

Required:
- `DB_CLUSTER_ARN` - Aurora PostgreSQL cluster ARN
- `DB_SECRET_ARN` - Secrets Manager ARN for database credentials
- `DB_NAME` - Database name (default: postgres)
- `STRAVA_CLIENT_ID` - Strava OAuth client ID
- `STRAVA_CLIENT_SECRET` - Strava OAuth client secret

Or alternatively:
- `STRAVA_SECRET_ARN` - Secrets Manager ARN containing client_id and client_secret

## How It Works

1. **Token Management**: Retrieves access and refresh tokens from database for the specified athlete
2. **Token Refresh**: Automatically refreshes expired tokens (with 5-minute buffer)
3. **Fetch from Strava**: Calls Strava API to get activity details
4. **Store in Database**: Upserts activities into the `activities` table using the same logic as `fetch_activities` and `webhook_processor`

## Error Handling

- **404**: Athlete not found or not connected to Strava
- **400**: Missing or invalid parameters
- **500**: Server configuration error or Strava API failure

## Testing

Run the test suite:

```bash
cd backend/update_activities
python3 test_lambda.py
```

All tests should pass:
- ✓ Handler correctly fails when environment variables are missing
- ✓ Handler correctly rejects requests without athlete_id
- ✓ Handler correctly rejects invalid athlete_id
- ✓ Handler correctly accepts query string parameters
- ✓ Handler correctly accepts JSON body with activity_id
- ✓ Polyline extraction correctly prefers full polyline

## Implementation Details

The function reuses code patterns from:
- `fetch_activities/` - For fetching multiple activities for an athlete
- `webhook_processor/` - For fetching single activity details

Key functions:
- `update_athlete_activities(athlete_id)` - Fetches recent activities
- `update_single_activity(athlete_id, activity_id)` - Updates one activity
- `store_activity(athlete_id, activity)` - Stores activity in database
- `ensure_valid_token(...)` - Handles token refresh

## Use Cases

1. **Testing**: Manually refresh activity data during development
2. **Backfilling**: Update historical activities after database changes
3. **Recovery**: Re-fetch activities that failed to sync via webhook
4. **Debugging**: Investigate specific activity data issues

## Notes

- This function does NOT require authentication (it's internal-only)
- The athlete must already exist in the database and be connected to Strava
- Activities are upserted (inserted if new, updated if existing)
- The function preserves existing `time_on_trail` and `distance_on_trail` values during updates
- Full polylines are preferred over summary polylines when available
