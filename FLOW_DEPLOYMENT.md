# Flow Improvements Deployment Guide

This deployment guide covers the changes made to implement profile picture display and disconnect functionality.

## Overview

This update adds:
1. Profile picture display on Dashboard
2. Disconnect functionality on Connect page when user is already connected
3. Better user experience flow

## Prerequisites

- AWS CLI configured with appropriate credentials
- Access to the RDS cluster and Lambda functions
- Node.js and npm installed for frontend build

## Deployment Steps

### 1. Run the Database Migration

The migration adds a `profile_picture` column to the `users` table.

#### Option A: Using AWS CLI (Recommended)

```bash
# Set your environment variables
export DB_CLUSTER_ARN="arn:aws:rds:us-east-1:ACCOUNT_ID:cluster:YOUR_CLUSTER"
export DB_SECRET_ARN="arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:YOUR_SECRET"
export DB_NAME="postgres"

# Run the migration
aws rds-data execute-statement \
  --resource-arn "$DB_CLUSTER_ARN" \
  --secret-arn "$DB_SECRET_ARN" \
  --database "$DB_NAME" \
  --sql "$(cat backend/migrations/002_add_profile_picture.sql)"
```

#### Option B: Using psql (if you have direct access)

```bash
psql -h YOUR_DATABASE_HOST -U YOUR_USERNAME -d postgres -f backend/migrations/002_add_profile_picture.sql
```

### 2. Deploy Backend Lambda Functions

Deploy the updated Lambda functions:

#### auth_callback

```bash
cd backend/auth_callback
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_AUTH_CALLBACK_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ../..
```

#### me

```bash
cd backend/me
zip -r function.zip lambda_function.py
aws lambda update-function-code \
  --function-name YOUR_ME_FUNCTION_NAME \
  --zip-file fileb://function.zip
cd ../..
```

### 3. Build and Deploy Frontend

```bash
# Install dependencies
npm install

# Build the frontend
npm run build

# Deploy to GitHub Pages (if using GitHub Actions)
git add dist
git commit -m "Deploy frontend with flow improvements"
git push origin main

# OR manually copy dist/ contents to your hosting service
```

### 4. Verify the Deployment

1. Visit your application URL
2. If not connected, verify you see the Connect page
3. Click "Connect with Strava" and authorize
4. Verify you're redirected to the Dashboard with your profile picture and name
5. Navigate back to the Connect page
6. Verify you see the disconnect UI with your profile picture
7. Click "Disconnect Strava"
8. Verify you're redirected back to the Connect page

## Changes Summary

### Backend Changes

**auth_callback/lambda_function.py:**
- Now captures profile picture URL from Strava OAuth response
- Stores `profile_medium` or `profile` in database (NULL if not available)
- Uses proper NULL handling instead of empty strings

**me/lambda_function.py:**
- Returns `profile_picture` field in response
- Handles NULL values gracefully

**Database:**
- Added `profile_picture` TEXT column to `users` table

### Frontend Changes

**src/pages/Dashboard.jsx:**
- Displays user profile picture next to welcome message
- Includes error handling and privacy features (referrerPolicy)
- Gracefully hides image if it fails to load

**src/pages/ConnectStrava.jsx:**
- Checks authentication status on page load
- Shows disconnect UI when user is connected:
  - Displays profile picture and name
  - Provides disconnect button
  - Shows info about disconnect action
- Shows original connect UI when not connected
- Hides marketing sections when user is connected

## Rollback Plan

If you need to rollback:

1. Deploy the previous version of Lambda functions
2. The database migration is backwards compatible
3. Deploy the previous version of the frontend
4. The `profile_picture` column can remain in the database (it won't cause issues)

## Troubleshooting

### Profile picture not showing

- Check CloudWatch Logs for auth_callback to see if Strava is providing profile picture
- Verify the database migration ran successfully
- Check browser console for image loading errors
- Verify CORS settings allow loading images from Strava

### Disconnect not working

- Check CloudWatch Logs for auth_disconnect Lambda
- Verify the disconnect endpoint is properly configured in API Gateway
- Check that cookies are being cleared properly

### User stuck in loading state

- Check CloudWatch Logs for /me endpoint
- Verify database connectivity
- Check that APP_SECRET is configured correctly

## Security Considerations

- Profile pictures are loaded with `referrerPolicy="no-referrer"` to prevent leaking referrer information
- Images have error handlers to prevent broken image displays
- NULL values are properly handled in database to distinguish "no picture" from errors
- Session cookies remain httpOnly and Secure

## Performance Notes

- Profile pictures are loaded from Strava's CDN
- No additional database queries are required (profile_picture added to existing /me query)
- Frontend build size increased by ~140 bytes (minimal impact)
