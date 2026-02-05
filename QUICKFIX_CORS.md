# Quick Fix Instructions

## The Problem
Frontend is at `https://rabbitmiles.com` but API Lambda functions still think it's at the old GitHub Pages URL. This causes CORS to block requests.

## The Solution  
Run this one command:

```bash
cd scripts && ./update-lambda-frontend-url.sh
```

## What it does
Updates `FRONTEND_URL` environment variable in these Lambda functions:
- rabbitmiles-auth-start
- rabbitmiles-auth-callback
- rabbitmiles-auth-disconnect
- rabbitmiles-me
- rabbitmiles-get-activities  
- rabbitmiles-get-activity-detail
- rabbitmiles-fetch-activities
- rabbitmiles-reset-last-matched

## Requirements
- AWS CLI installed
- AWS credentials configured with Lambda update permissions
- jq installed (for JSON processing)

## After running
Visit https://rabbitmiles.com/activity/363 - the CORS error should be gone.

## More details
See [CORS_DOMAIN_FIX.md](./CORS_DOMAIN_FIX.md) for complete documentation.
