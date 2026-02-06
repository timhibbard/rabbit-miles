# Backfill Athlete Count Lambda

This Lambda function backfills the `athlete_count` field for existing activities in the database by fetching the data from the Strava API.

## Purpose

When new fields are added to the activities table (like `athlete_count`), existing activities don't have this data populated. This function:

1. Fetches all activities from the database
2. Queries the Strava API for each activity to get the current `athlete_count` value
3. Updates the database with the values from Strava, overwriting any existing data

## Usage

### Batch Mode (All Users)

Invoke the Lambda without any parameters to process all users:

```bash
aws lambda invoke \
  --function-name backfill_athlete_count \
  --payload '{}' \
  response.json
```

### Single User Mode

Invoke with a specific `athlete_id` to process only that user:

```bash
aws lambda invoke \
  --function-name backfill_athlete_count \
  --payload '{"athlete_id": 123456}' \
  response.json
```

## Environment Variables

This function requires the same environment variables as other backend Lambdas:

- `DB_CLUSTER_ARN` - ARN of the RDS Aurora Cluster
- `DB_SECRET_ARN` - ARN of the Secrets Manager secret for database credentials
- `DB_NAME` - Database name (default: "postgres")

## Response

The function returns a JSON response with:

```json
{
  "message": "Backfill completed",
  "users_processed": 5,
  "activities_processed": 150,
  "activities_updated": 143
}
```

## Notes

- The function processes up to 100 activities per user by default
- All activities are updated with the latest value from Strava, regardless of current database value
- Rate limiting: Be aware of Strava API rate limits (100 requests per 15 minutes, 1000 per day)
- For large backlogs, you may need to run this multiple times or increase the limit
