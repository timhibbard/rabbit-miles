# Quick Start: Trail Data Update

## What This Does

Downloads trail GeoJSON data from greenvilleopenmap.info and stores it in S3 for trail matching logic.

## Setup (5 Minutes)

### 1. Create S3 Bucket
```bash
aws s3 mb s3://rabbitmiles-trail-data --region us-east-1
```

### 2. Create IAM Policy
```bash
cat > trail-s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:PutObjectAcl"],
    "Resource": "arn:aws:s3:::rabbitmiles-trail-data/trails/*"
  }]
}
EOF

aws iam create-policy \
  --policy-name RabbitMiles-TrailDataS3Access \
  --policy-document file://trail-s3-policy.json
```

### 3. Create IAM Role
```bash
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name RabbitMiles-UpdateTrailDataRole \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name RabbitMiles-UpdateTrailDataRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
  --role-name RabbitMiles-UpdateTrailDataRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/RabbitMiles-TrailDataS3Access
```

### 4. Create Lambda Function
```bash
cd backend/update_trail_data
zip -r function.zip lambda_function.py

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

### 5. Test It
```bash
aws lambda invoke \
  --function-name rabbitmiles-update-trail-data \
  --payload '{}' \
  response.json && cat response.json
```

### 6. Add GitHub Secret
Go to: Settings → Secrets and variables → Actions

Add secret:
- Name: `LAMBDA_UPDATE_TRAIL_DATA`
- Value: `rabbitmiles-update-trail-data`

## Usage

### Manual Update
```bash
aws lambda invoke \
  --function-name rabbitmiles-update-trail-data \
  --payload '{}' \
  response.json
```

### Check Files
```bash
aws s3 ls s3://rabbitmiles-trail-data/trails/
```

## When to Run

- Trail network is extended
- New spurs added
- Routes are changed
- Data source updated

## Files Stored

- `s3://rabbitmiles-trail-data/trails/main.geojson` (~76KB)
- `s3://rabbitmiles-trail-data/trails/spurs.geojson` (~40KB)

## Cost

~$0.001/month (essentially free)

## Full Documentation

See `TRAIL_DATA_SETUP.md` for complete instructions and troubleshooting.
