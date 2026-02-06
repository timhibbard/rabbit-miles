# Group Badge Feature - Implementation Summary

## Overview
This PR adds support for displaying a group badge on activities where multiple athletes participated together (based on Strava's `athlete_count` field).

## What Changed

### 1. Database Schema
- Added `athlete_count` column to the `activities` table
- Default value: 1 (solo activity)
- Indexed for efficient queries
- Migration file: `backend/migrations/006_add_athlete_count.sql`

### 2. Backend - Data Collection
**fetch_activities Lambda** (`backend/fetch_activities/lambda_function.py`)
- Extracts `athlete_count` from Strava API response
- Stores it in the database when creating/updating activities
- Defaults to 1 if not provided by Strava

**get_activities Lambda** (`backend/get_activities/lambda_function.py`)
- Returns `athlete_count` field in API response
- Properly handles NULL values with default of 1

### 3. Backend - Data Backfill
**backfill_athlete_count Lambda** (`backend/backfill_athlete_count/`)
- Standalone Lambda function to populate `athlete_count` for existing activities
- Fetches activity details from Strava API
- Can run in batch mode (all users) or single-user mode
- Only processes activities with NULL `athlete_count` to avoid unnecessary API calls
- Respects Strava API rate limits

Usage:
```bash
# Backfill all users
aws lambda invoke --function-name backfill_athlete_count --payload '{}' response.json

# Backfill single user
aws lambda invoke --function-name backfill_athlete_count --payload '{"athlete_id": 123456}' response.json
```

### 4. Frontend - UI Display
**Dashboard** (`src/pages/Dashboard.jsx`)
- Shows blue group badge with icon when `athlete_count > 1`
- Badge displays the athlete count number
- Positioned next to the activity type badge
- Uses Heroicons "users" icon

**Activity Detail Page** (`src/pages/ActivityDetail.jsx`)
- Shows blue group badge with icon and text (e.g., "5 people")
- Positioned next to the activity type badge
- Uses same styling as Dashboard for consistency

### 5. Testing
- Added unit test: `backend/fetch_activities/test_athlete_count.py`
- Tests athlete_count extraction logic
- Tests display logic (when to show/hide badge)
- All tests passing ✓

## Visual Design

### Badge Appearance
- **Color**: Blue (bg-blue-100, text-blue-800)
- **Icon**: SVG group/users icon
- **Text**: 
  - Dashboard: Just the number (e.g., "5")
  - Detail page: Number + "people" (e.g., "5 people")

### When Badge Shows
- `athlete_count === null` → No badge (treated as solo)
- `athlete_count === 1` → No badge (solo activity)
- `athlete_count === 2` → Badge shows "2" (Dashboard) or "2 people" (Detail)
- `athlete_count > 2` → Badge shows count (Dashboard) or count + "people" (Detail)

## Database Migration Instructions

After deploying, run the migration:

```bash
# Using RDS Data API (AWS CLI)
aws rds-data execute-statement \
  --resource-arn "arn:aws:rds:REGION:ACCOUNT:cluster:CLUSTER_ID" \
  --secret-arn "arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET_NAME" \
  --database "postgres" \
  --sql "$(cat backend/migrations/006_add_athlete_count.sql)"

# Then run the backfill Lambda to populate existing activities
aws lambda invoke \
  --function-name backfill_athlete_count \
  --payload '{}' \
  response.json
```

## Strava API Field
The `athlete_count` field is provided by Strava's Activity API:
- Available in both list activities endpoint (GET /athlete/activities)
- Available in detailed activity endpoint (GET /activities/:id)
- Represents the number of athletes who participated in the activity
- Not always present in Strava's response (we default to 1)

## Security & Code Quality
- ✅ All tests passing
- ✅ Frontend builds successfully
- ✅ ESLint passes with no errors
- ✅ CodeQL security scan: 0 vulnerabilities
- ✅ Code review feedback addressed

## Benefits
1. **User Value**: Users can now see at a glance which activities were group rides/runs
2. **Social Context**: Adds social dimension to activity tracking
3. **Reusable Pattern**: The backfill Lambda provides a template for future field additions
4. **Minimal Impact**: Changes are surgical and don't affect existing functionality
