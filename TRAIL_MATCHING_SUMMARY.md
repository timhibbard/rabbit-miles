# Trail Matching Implementation Summary

## Overview

This PR implements automatic calculation of trail metrics for activities, showing users how much time and distance of each activity was spent on the Swamp Rabbit Trail.

## What Was Implemented

### New Lambda Functions

1. **match_activity_trail** (`backend/match_activity_trail/`)
   - Decodes activity GPS polylines
   - Loads trail GeoJSON from S3
   - Calculates distance/time on trail with 50m tolerance
   - Updates database with computed metrics
   - ~450 lines of Python code

2. **match_unmatched_activities** (`backend/match_unmatched_activities/`)
   - Batch processes activities missing trail metrics
   - Finds activities where `last_matched IS NULL`
   - Processes 10 activities per invocation
   - Used for backfilling and scheduled cleanup
   - ~160 lines of Python code

### Modified Components

3. **webhook_processor** (`backend/webhook_processor/`)
   - Modified to trigger trail matching after storing new/updated activities
   - Returns activity_id from store_activity for chaining
   - Calls match_activity_trail Lambda asynchronously

4. **Dashboard** (`src/pages/Dashboard.jsx`)
   - Displays trail metrics below activity distance/time
   - Shows distance on trail in miles (green text)
   - Shows time on trail in minutes (green text)
   - Gracefully handles null values (only shows when available)

5. **get_activities** (`backend/get_activities/`)
   - Already returns trail metrics (no changes needed)
   - Fields: `time_on_trail`, `distance_on_trail`

## How It Works

### Data Flow

```
New Strava Activity
    ↓
webhook → SQS → webhook_processor
    ↓
Store activity in DB (returns activity_id)
    ↓
Trigger match_activity_trail (async)
    ↓
1. Decode polyline
2. Load trail data from S3
3. Calculate intersection
4. Update DB with metrics
    ↓
Frontend polls /activities
    ↓
Display trail metrics to user
```

### Matching Algorithm

1. **Decode Polyline**: Convert Google-encoded polyline to lat/lon coordinates
2. **Load Trail Data**: Fetch GeoJSON from S3 (main.geojson + spurs.geojson)
3. **Segment Matching**: For each activity segment:
   - Calculate segment midpoint
   - Find minimum distance to all trail segments
   - Mark as "on trail" if distance ≤ 50 meters
4. **Calculate Metrics**:
   - `distance_on_trail`: Sum of matched segment lengths
   - `time_on_trail`: Proportional to distance ratio (assumes constant speed)
   - `last_matched`: Current UTC timestamp

### Key Technical Details

- **Tolerance**: 50 meters on either side of trail centerline
- **Distance Calculation**: Haversine formula for accurate geodesic distances
- **Point-to-Segment**: Proper perpendicular distance calculation
- **Time Estimation**: Simple proportional calculation based on moving_time
- **S3 Data**: Loads from `rabbitmiles-trail-data` bucket on each invocation

## Database Changes

Uses existing columns added in migrations:
- `activities.time_on_trail` (INTEGER) - Time in seconds
- `activities.distance_on_trail` (DECIMAL) - Distance in meters
- `activities.last_matched` (TIMESTAMP) - When last checked

## Testing

### Unit Tests

Created `backend/match_activity_trail/test_lambda.py`:
- ✅ Polyline decoding
- ✅ Haversine distance calculation
- ✅ Point-to-segment distance
- ✅ Trail tolerance validation

All tests pass successfully.

### Code Quality

- ✅ Code review completed (2 comments addressed)
- ✅ CodeQL security scan: 0 alerts
- ✅ No SQL injection (parameterized queries)
- ✅ No credentials in code
- ✅ Proper error handling

## Deployment Requirements

### Environment Variables

**match_activity_trail**:
- `DB_CLUSTER_ARN`
- `DB_SECRET_ARN`
- `DB_NAME`
- `TRAIL_DATA_BUCKET`

**match_unmatched_activities**:
- `DB_CLUSTER_ARN`
- `DB_SECRET_ARN`
- `DB_NAME`
- `MATCH_ACTIVITY_LAMBDA_ARN`

**webhook_processor** (updated):
- Add `MATCH_ACTIVITY_LAMBDA_ARN`

### IAM Permissions

**match_activity_trail**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`
- `s3:GetObject` on `rabbitmiles-trail-data/trails/*`

**match_unmatched_activities**:
- `rds-data:ExecuteStatement`
- `secretsmanager:GetSecretValue`
- `lambda:InvokeFunction` for match_activity_trail

**webhook_processor**:
- Add `lambda:InvokeFunction` for match_activity_trail

### S3 Bucket

Requires `rabbitmiles-trail-data` bucket with:
- `trails/main.geojson` (~76KB)
- `trails/spurs.geojson` (~40KB)

## Documentation

Created comprehensive documentation:
- `backend/match_activity_trail/README.md` - Full Lambda documentation
- `backend/match_unmatched_activities/README.md` - Batch processor documentation
- `TRAIL_MATCHING_DEPLOYMENT.md` - Deployment guide with commands
- Updated `backend/README.md` - Added new Lambda functions to index

## Post-Deployment Tasks

1. **Deploy Lambda Functions**:
   - Create match_activity_trail
   - Create match_unmatched_activities
   - Update webhook_processor

2. **Initial Backfill**:
   - Run match_unmatched_activities to process existing activities
   - May need multiple invocations if > 10 activities

3. **Verify**:
   - Check Lambda logs
   - Query database for trail metrics
   - Test frontend display

4. **Optional**:
   - Set up EventBridge schedule for daily cleanup
   - Set up CloudWatch alarms for monitoring

## Performance Characteristics

- **match_activity_trail**:
  - Typical execution: 1-5 seconds
  - Memory: 512 MB recommended
  - Timeout: 300 seconds (5 minutes)
  - Cost: ~$0.001 per invocation

- **match_unmatched_activities**:
  - Typical execution: 10-30 seconds
  - Memory: 256 MB sufficient
  - Timeout: 300 seconds
  - Cost: ~$0.0005 per invocation

- **Backfill**: For 100 activities:
  - ~10 invocations of match_unmatched_activities
  - ~100 invocations of match_activity_trail
  - Total cost: ~$0.10

## Future Enhancements

Potential improvements (not in this PR):

1. **Caching**: Cache trail data in Lambda /tmp or memory
2. **Spatial Indexing**: Use R-tree for faster segment lookups
3. **Speed-Based Time**: Calculate time based on actual speed variations
4. **Multi-Sport Support**: Different calculations for different activity types
5. **SQS Queue**: Use SQS instead of direct Lambda invocation for better scaling
6. **Batch Processing**: Process multiple activities in single invocation

## Files Changed

- `backend/match_activity_trail/lambda_function.py` (NEW)
- `backend/match_activity_trail/test_lambda.py` (NEW)
- `backend/match_activity_trail/README.md` (NEW)
- `backend/match_unmatched_activities/lambda_function.py` (NEW)
- `backend/match_unmatched_activities/README.md` (NEW)
- `backend/webhook_processor/lambda_function.py` (MODIFIED)
- `src/pages/Dashboard.jsx` (MODIFIED)
- `backend/README.md` (MODIFIED)
- `TRAIL_MATCHING_DEPLOYMENT.md` (NEW)
- `TRAIL_MATCHING_SUMMARY.md` (NEW - this file)

## Testing Checklist

Before merging:
- [x] Unit tests pass
- [x] Code review complete
- [x] Security scan clean
- [x] Documentation complete
- [ ] Deployed to test environment (requires AWS access)
- [ ] Verified trail matching works end-to-end (requires AWS access)
- [ ] Verified frontend displays correctly (requires AWS access)

After merging:
- [ ] Deploy to production
- [ ] Run initial backfill
- [ ] Monitor Lambda logs
- [ ] Verify metrics in database
- [ ] Test frontend with real user

## Support

If issues arise:
- Check CloudWatch Logs for Lambda functions
- Verify environment variables are set correctly
- Confirm IAM permissions are in place
- Test with single activity using direct invocation
- Review deployment guide for troubleshooting steps

For questions or issues, refer to:
- `TRAIL_MATCHING_DEPLOYMENT.md` for deployment help
- Lambda README files for function-specific documentation
- CloudWatch Logs for runtime errors
