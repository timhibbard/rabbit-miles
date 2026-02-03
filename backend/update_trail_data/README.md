# Update Trail Data Lambda Function

This Lambda function downloads trail GeoJSON data from greenvilleopenmap.info and stores it in S3 for use by the trail matching system.

## Purpose

The function downloads two GeoJSON files that define the Swamp Rabbit Trail network:
- **Main trail**: The primary Swamp Rabbit Way trail (~30 miles)
- **Spurs**: Connector trails that branch from the main trail

This data is used to determine which parts of user activities occur on designated trails, enabling accurate distance and time tracking for trail usage.

## Invocation

This is an **on-demand** function that should be invoked manually when trail data needs to be updated (e.g., when the trail network changes or is extended).

### Manual Invocation via AWS Console

1. Go to AWS Lambda console
2. Select the `update_trail_data` function
3. Click "Test" tab
4. Create a new test event with any name and empty JSON `{}`
5. Click "Test" to invoke

### Manual Invocation via AWS CLI

```bash
aws lambda invoke \
  --function-name <lambda-function-name> \
  --payload '{}' \
  response.json

cat response.json
```

## Environment Variables

The function requires one environment variable:

- **`TRAIL_DATA_BUCKET`** (required): The S3 bucket name where trail GeoJSON files will be stored

Example: `rabbitmiles-trail-data`

## S3 Storage

The function stores files in S3 with the following keys:

- `trails/main.geojson` - Main Swamp Rabbit Way trail
- `trails/spurs.geojson` - Connector/spur trails

Files are stored with:
- Content-Type: `application/geo+json`
- Metadata: `updated_at` (ISO 8601 timestamp), `source` (greenvilleopenmap.info)

## Response Format

### Success (Status 200)
```json
{
  "message": "All trail data updated successfully",
  "results": {
    "main_trail": {
      "status": "success",
      "size_bytes": 78890,
      "s3_key": "trails/main.geojson"
    },
    "spurs_trail": {
      "status": "success",
      "size_bytes": 39980,
      "s3_key": "trails/spurs.geojson"
    }
  },
  "bucket": "rabbitmiles-trail-data",
  "timestamp": "2024-02-03T15:30:00.000Z"
}
```

### Partial Success (Status 207)
```json
{
  "message": "Trail data partially updated",
  "results": {
    "main_trail": {
      "status": "success",
      "size_bytes": 78890,
      "s3_key": "trails/main.geojson"
    },
    "spurs_trail": {
      "status": "error",
      "error": "Network timeout"
    }
  },
  "bucket": "rabbitmiles-trail-data",
  "timestamp": "2024-02-03T15:30:00.000Z"
}
```

### Error (Status 500)
```json
{
  "error": "TRAIL_DATA_BUCKET environment variable not set"
}
```

## Required AWS Permissions

The Lambda execution role must have:

1. **S3 permissions** to write to the bucket:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:PutObject",
    "s3:PutObjectAcl"
  ],
  "Resource": "arn:aws:s3:::rabbitmiles-trail-data/trails/*"
}
```

2. **Internet access** to download from greenvilleopenmap.info:
   - Lambda must not be in a VPC, OR
   - Lambda must be in a VPC with NAT Gateway for internet access

## Testing

Run the test suite:

```bash
cd backend/update_trail_data
python3 test_lambda.py
```

The test suite validates:
- Missing environment variable handling
- Successful download and upload
- Partial failure scenarios
- Individual function behavior

## Deployment

The function is automatically deployed via GitHub Actions when changes are pushed to `main`:

1. Add Lambda function name as a GitHub secret: `LAMBDA_UPDATE_TRAIL_DATA`
2. Push changes to `main` branch
3. GitHub Actions will package and deploy the function

Manual deployment:
```bash
cd backend/update_trail_data
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name <lambda-function-name> \
  --zip-file fileb://function.zip
```

## Setup Checklist

- [ ] Create S3 bucket for trail data (e.g., `rabbitmiles-trail-data`)
- [ ] Create Lambda function in AWS Console
- [ ] Set `TRAIL_DATA_BUCKET` environment variable
- [ ] Attach IAM role with S3 write permissions
- [ ] Ensure Lambda has internet access (no VPC or VPC with NAT)
- [ ] Add `LAMBDA_UPDATE_TRAIL_DATA` secret to GitHub repository
- [ ] Test function invocation
- [ ] Verify files appear in S3 bucket

## Data Sources

Trail data is downloaded from:
- Main trail: https://greenvilleopenmap.info/SwampRabbitWays.geojson
- Spurs: https://greenvilleopenmap.info/SwampRabbitConnectors.geojson

These URLs are maintained by Greenville Open Map and contain the authoritative trail network data.

## Why S3 Instead of Database?

S3 is the recommended storage for trail GeoJSON data because:

✅ **Simpler**: Direct storage and retrieval without schema complexity  
✅ **Cost-effective**: Cheaper for static data that changes infrequently  
✅ **Versioning**: S3 versioning provides automatic rollback capability  
✅ **Performance**: Fast downloads for Lambda functions  
✅ **Separation**: Keeps static geographic data separate from transactional data  

Database storage would require:
- PostGIS extension for spatial operations
- Complex JSONB queries
- More database resources and costs
- More difficult versioning and rollback

## Notes

- The function overwrites existing files in S3 (no versioning unless S3 versioning is enabled)
- Total data size is ~120KB, well within Lambda and S3 limits
- Function timeout should be set to at least 30 seconds to allow for downloads
- CloudWatch Logs capture all function output for troubleshooting
