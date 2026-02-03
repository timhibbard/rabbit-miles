# Trail Data Update Setup Guide

This guide walks through setting up the `update_trail_data` Lambda function and S3 bucket to store trail GeoJSON data.

## Overview

The trail data update system:
1. Downloads trail GeoJSON files from greenvilleopenmap.info
2. Stores them in an S3 bucket
3. Makes them available for trail matching logic
4. Can be invoked on-demand when trail data changes

## Prerequisites

- AWS account with admin access
- AWS CLI configured (optional, for testing)
- GitHub repository secrets access (for deployment)

## Step 1: Create S3 Bucket

### Via AWS Console

1. Go to **S3** in AWS Console
2. Click **Create bucket**
3. Configure:
   - **Bucket name**: `rabbitmiles-trail-data` (or your preferred name)
   - **Region**: `us-east-1` (same as your Lambda functions)
   - **Block all public access**: ✅ Enabled (trail data is private)
   - **Bucket Versioning**: Optional but recommended (enables rollback)
4. Click **Create bucket**

### Via AWS CLI

```bash
aws s3 mb s3://rabbitmiles-trail-data --region us-east-1

# Optional: Enable versioning
aws s3api put-bucket-versioning \
  --bucket rabbitmiles-trail-data \
  --versioning-configuration Status=Enabled
```

## Step 2: Create IAM Policy for S3 Access

### Via AWS Console

1. Go to **IAM** → **Policies** → **Create policy**
2. Select **JSON** tab
3. Paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::rabbitmiles-trail-data/trails/*"
    }
  ]
}
```

4. Name: `RabbitMiles-TrailDataS3Access`
5. Click **Create policy**

### Via AWS CLI

```bash
cat > trail-s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::rabbitmiles-trail-data/trails/*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name RabbitMiles-TrailDataS3Access \
  --policy-document file://trail-s3-policy.json
```

## Step 3: Create IAM Role for Lambda

### Via AWS Console

1. Go to **IAM** → **Roles** → **Create role**
2. Select **AWS service** → **Lambda**
3. Attach policies:
   - `AWSLambdaBasicExecutionRole` (for CloudWatch Logs)
   - `RabbitMiles-TrailDataS3Access` (from Step 2)
4. Name: `RabbitMiles-UpdateTrailDataRole`
5. Click **Create role**

### Via AWS CLI

```bash
# Create trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name RabbitMiles-UpdateTrailDataRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name RabbitMiles-UpdateTrailDataRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
  --role-name RabbitMiles-UpdateTrailDataRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/RabbitMiles-TrailDataS3Access
```

## Step 4: Create Lambda Function

### Via AWS Console

1. Go to **Lambda** → **Create function**
2. Choose **Author from scratch**
3. Configure:
   - **Function name**: `rabbitmiles-update-trail-data`
   - **Runtime**: Python 3.12 (or latest Python 3.x)
   - **Architecture**: x86_64
   - **Execution role**: Use existing role → `RabbitMiles-UpdateTrailDataRole`
4. Click **Create function**
5. In **Configuration** → **General configuration**:
   - **Timeout**: 30 seconds (to allow for downloads)
   - **Memory**: 128 MB (sufficient for this task)
6. In **Configuration** → **Environment variables**:
   - Add: `TRAIL_DATA_BUCKET` = `rabbitmiles-trail-data`
7. **Important**: Ensure Lambda is **NOT in a VPC** (needs internet access)
   - Go to **Configuration** → **VPC**
   - Verify it shows "No VPC"

### Via AWS CLI

```bash
# Package the Lambda
cd backend/update_trail_data
zip -r function.zip lambda_function.py

# Create Lambda function
aws lambda create-function \
  --function-name rabbitmiles-update-trail-data \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/RabbitMiles-UpdateTrailDataRole \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 128 \
  --environment Variables={TRAIL_DATA_BUCKET=rabbitmiles-trail-data}
```

## Step 5: Test the Lambda Function

### Via AWS Console

1. Go to your Lambda function
2. Click **Test** tab
3. Create new test event:
   - **Event name**: `TestUpdate`
   - **Event JSON**: `{}`
4. Click **Test**
5. Check **Execution result**:
   - Should see status 200
   - Response should show both trails updated successfully
6. Verify in S3:
   - Go to S3 bucket
   - Check for `trails/main.geojson` and `trails/spurs.geojson`

### Via AWS CLI

```bash
# Invoke Lambda
aws lambda invoke \
  --function-name rabbitmiles-update-trail-data \
  --payload '{}' \
  response.json

# View response
cat response.json

# Check S3 files
aws s3 ls s3://rabbitmiles-trail-data/trails/
```

Expected output:
```
trails/main.geojson
trails/spurs.geojson
```

## Step 6: Add to GitHub Secrets for Deployment

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Add new repository secret:
   - **Name**: `LAMBDA_UPDATE_TRAIL_DATA`
   - **Value**: `rabbitmiles-update-trail-data`
4. Click **Add secret**

Now, when you push changes to the `backend/update_trail_data/` directory on the `main` branch, GitHub Actions will automatically deploy the Lambda.

## Step 7: Verify Deployment

After pushing to main:

1. Go to **Actions** tab in GitHub
2. Check **Deploy Lambda Functions** workflow
3. Verify `update_trail_data` job succeeds
4. Test the Lambda function again to ensure deployment worked

## Maintenance

### When to Update Trail Data

Run the Lambda function manually when:
- Trail network is extended or modified
- New spurs or connectors are added
- Trail routes are rerouted
- Data source is updated

### How to Update

**Option 1: AWS Console**
1. Go to Lambda function
2. Click **Test** button
3. Verify success in response

**Option 2: AWS CLI**
```bash
aws lambda invoke \
  --function-name rabbitmiles-update-trail-data \
  --payload '{}' \
  response.json && cat response.json
```

### Monitoring

- **CloudWatch Logs**: View logs at `/aws/lambda/rabbitmiles-update-trail-data`
- **S3 Metadata**: Each file has `updated_at` timestamp in metadata
- **Lambda Metrics**: Monitor invocations, errors, duration in CloudWatch

## Troubleshooting

### "TRAIL_DATA_BUCKET environment variable not set"
- Verify environment variable in Lambda configuration
- Check spelling: `TRAIL_DATA_BUCKET`

### "Access Denied" S3 error
- Verify IAM role has `RabbitMiles-TrailDataS3Access` policy attached
- Check S3 bucket name matches policy resource ARN
- Ensure bucket exists in same region

### "Network timeout" downloading trails
- Verify Lambda is NOT in a VPC, or has NAT Gateway
- Check timeout is at least 30 seconds
- Verify greenvilleopenmap.info is accessible

### Lambda invocation succeeds but no files in S3
- Check CloudWatch Logs for detailed error messages
- Verify bucket name in environment variable
- Test S3 access with AWS CLI

## Cost Estimate

**S3 Storage**: ~$0.001/month (for 120KB at $0.023/GB)  
**Lambda**: ~$0.0000002 per invocation (free tier: 1M requests/month)  
**Data Transfer**: Negligible (120KB downloads)  

**Total monthly cost**: Essentially free (<$0.01/month)

## Security Considerations

- ✅ S3 bucket is private (no public access)
- ✅ Lambda execution role follows least privilege
- ✅ No credentials stored in code
- ✅ Trail data source is trusted (greenvilleopenmap.info)
- ✅ Function only writes to `trails/` prefix in bucket

## Next Steps

After setup:
1. ✅ Lambda function is ready to use
2. ✅ Trail data is stored in S3
3. ⏭️ Implement trail matching logic to use the S3 data
4. ⏭️ Add API endpoint to trigger updates (optional)
5. ⏭️ Set up scheduled updates via EventBridge (optional)

## Support

For issues or questions:
- Check CloudWatch Logs for detailed error messages
- Review function README: `backend/update_trail_data/README.md`
- Check Lambda configuration in AWS Console
