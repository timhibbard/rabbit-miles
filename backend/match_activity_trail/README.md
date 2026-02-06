# match_activity_trail Lambda Function

This Lambda function calculates how much of an activity was on the Swamp Rabbit Trail by comparing the activity's GPS path (polyline) against the trail GeoJSON data stored in S3.

## Purpose

When an activity is created or updated, this function:
1. Decodes the activity's Google-encoded polyline
2. Loads trail GeoJSON data from S3 (`rabbitmiles-trail-data` bucket)
3. Checks each activity segment against all trail segments with a 25-meter tolerance
4. Calculates distance and time spent on the trail
5. Updates the database with `distance_on_trail`, `time_on_trail`, and `last_matched` timestamp

## Invocation Methods

### 1. Direct Invocation (for testing)
```json
{
  "activity_id": 123
}
```

### 2. Via Query String
```
?activity_id=123
```

### 3. SQS Trigger (from webhook_processor)
The function can process SQS messages containing activity IDs for batch processing.

## Environment Variables

Required:
- `DB_CLUSTER_ARN`: Aurora PostgreSQL cluster ARN
- `DB_SECRET_ARN`: Database credentials secret ARN
- `DB_NAME`: Database name (default: postgres)
- `TRAIL_DATA_BUCKET`: S3 bucket containing trail GeoJSON files (default: rabbitmiles-trail-data)

## Algorithm

### Trail Matching Logic

1. **Polyline Decoding**: Decodes Google's encoded polyline format to lat/lon coordinates
2. **Distance Calculation**: Uses Haversine formula to calculate distances on Earth's surface
3. **Segment Matching**: For each activity segment:
   - Calculates the segment midpoint
   - Checks distance to all trail segments
   - Marks segment as "on trail" if within 25 meters of any trail segment
4. **Metric Calculation**:
   - `distance_on_trail`: Sum of all segments marked as "on trail"
   - `time_on_trail`: Proportional to distance ratio (assumes constant speed)

### Tolerance

- **25 meters** on either side of the trail centerline
- Chosen to accommodate GPS inaccuracies and path width variations
- At Greenville, SC latitude (34.85°N):
  - 25m ≈ 0.000225° latitude
  - 25m ≈ 0.000275° longitude

## S3 Trail Data Structure

Expected files in `s3://rabbitmiles-trail-data/`:
- `trails/main.geojson`: Main Swamp Rabbit Trail
- `trails/spurs.geojson`: Connector trails and spurs

Both files should be GeoJSON format with LineString or MultiLineString geometries.

## Response Format

```json
{
  "activity_id": 123,
  "distance_on_trail": 5234.56,
  "time_on_trail": 1847,
  "message": "Successfully matched"
}
```

## Error Handling

- Returns 404 if activity not found
- Returns 200 with 0 values if activity has no polyline data
- Continues processing on S3 errors (logs warning)
- Updates `last_matched` even when no polyline data exists

## Deployment

```bash
# Create deployment package
cd backend/match_activity_trail
zip -r function.zip lambda_function.py

# Deploy to AWS Lambda
aws lambda update-function-code \
  --function-name match_activity_trail \
  --zip-file fileb://function.zip

# Set environment variables
aws lambda update-function-configuration \
  --function-name match_activity_trail \
  --environment Variables={
    DB_CLUSTER_ARN=arn:aws:rds:us-east-1:...,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:...,
    DB_NAME=postgres,
    TRAIL_DATA_BUCKET=rabbitmiles-trail-data
  }
```

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:us-east-1:ACCOUNT:cluster:CLUSTER_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:SECRET_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::rabbitmiles-trail-data/trails/*"
    }
  ]
}
```

## Testing

Run the test suite:
```bash
cd backend/match_activity_trail
python3 test_lambda.py
```

Tests validate:
- Polyline decoding accuracy
- Haversine distance calculations
- Point-to-segment distance calculations
- Trail tolerance values

## Performance Considerations

- Trail data is loaded from S3 on each invocation (consider caching for high volume)
- Algorithm complexity is O(n*m) where n = activity segments, m = trail segments
- Typical activity: ~100-500 points
- Trail data: ~1000-2000 points
- Processing time: 1-5 seconds per activity

## Future Improvements

1. Cache trail data in Lambda /tmp or memory
2. Use spatial indexing (R-tree) for faster segment lookups
3. Add support for multi-sport activities with different speed profiles
4. Implement more sophisticated time calculation based on actual speeds
