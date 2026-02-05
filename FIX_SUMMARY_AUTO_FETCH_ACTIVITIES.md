# Fix Summary: Automatic Activity Fetch for New Users

## Problem Statement
When a new user logs in to RabbitMiles via Strava OAuth, their activities are not automatically fetched. Users must manually click the "Fetch Activities" button, which creates friction in the onboarding experience.

## Solution
Implemented automatic activity fetching during the OAuth callback flow for new users only. The system detects if a user is logging in for the first time and automatically triggers activity fetching in the background.

## Technical Implementation

### Changes Made

#### 1. auth_callback Lambda (`backend/auth_callback/lambda_function.py`)
- **Added Lambda client**: Initialized `boto3.client("lambda")` to enable lambda-to-lambda invocations
- **Added environment variable**: `FETCH_ACTIVITIES_LAMBDA_ARN` (optional)
- **New user detection**: Query database before upsert to determine if user exists
- **Automatic invocation**: Asynchronously invoke `fetch_activities` lambda for new users with credentials
- **Graceful degradation**: Login succeeds even if activity fetch fails (non-blocking)

#### 2. fetch_activities Lambda (`backend/fetch_activities/lambda_function.py`)
- **Dual invocation support**: Handler now supports both:
  - API Gateway invocation (existing behavior with cookies)
  - Direct Lambda invocation (new behavior with credentials in payload)
- **Event detection**: Checks for `athlete_id` and `access_token` keys to distinguish invocation types
- **Backward compatibility**: Existing API Gateway behavior unchanged

#### 3. Tests (`backend/fetch_activities/test_direct_invoke.py`)
- Created unit tests to validate event detection logic
- Tests cover direct invocation, API Gateway invocation, and incomplete payloads
- All tests use idiomatic Python assertions

#### 4. Documentation
- **DEPLOYMENT_AUTO_FETCH_ACTIVITIES.md**: Complete deployment guide with:
  - Step-by-step deployment instructions
  - Environment variable configuration
  - IAM permission setup
  - Verification procedures
  - Troubleshooting guide
  - Rollback plan
- **ENV_VARS.md**: Updated to document new `FETCH_ACTIVITIES_LAMBDA_ARN` variable

## How It Works

### Flow for New Users
1. User clicks "Connect to Strava" on frontend
2. OAuth flow redirects to Strava
3. User authorizes RabbitMiles
4. Strava redirects to `auth_callback` with code
5. `auth_callback` checks if user exists in database
6. **NEW**: If user doesn't exist (new user):
   - Upsert user to database
   - Asynchronously invoke `fetch_activities` with credentials
   - Return success response to user (don't wait for fetch)
7. User sees "Successfully connected" page
8. Activities are fetched in the background

### Flow for Existing Users
1-5. Same as above
6. If user exists (returning user):
   - Update user tokens in database
   - **Do NOT** trigger automatic activity fetch
7. User sees "Successfully connected" page
8. User must manually click "Fetch Activities" if desired

## Key Design Decisions

### 1. Check Before Upsert
Instead of checking the SQL result after upsert, we query the database first. This is necessary because:
- `ON CONFLICT DO UPDATE` doesn't return a way to distinguish insert vs update
- We need to know if this is a new user before the upsert happens
- Minimal performance impact (single SELECT query)

### 2. Asynchronous Invocation
Used `InvocationType='Event'` for async invocation because:
- Login flow shouldn't wait for activity fetch (could take 5-30 seconds)
- Better user experience (faster login completion)
- Failure isolation (login succeeds even if fetch fails)

### 3. Direct Invocation with Credentials
Passed credentials directly in payload instead of using cookies because:
- Simpler than setting up cookie forwarding between lambdas
- More reliable (no cookie parsing issues)
- Credentials are already available in `auth_callback`
- Lambda-to-lambda invocation is secure within AWS

### 4. Graceful Degradation
If `FETCH_ACTIVITIES_LAMBDA_ARN` is not set:
- System logs a warning
- Login still succeeds
- User can manually fetch activities
- No breaking changes

## Security Considerations

### What We Checked
- ✅ No secrets in code or logs
- ✅ Credentials passed securely via Lambda invocation payload
- ✅ No sensitive data in error messages
- ✅ CodeQL scan passed with 0 alerts
- ✅ IAM permissions follow least privilege principle

### IAM Permissions Required
`auth_callback` Lambda needs:
```json
{
  "Effect": "Allow",
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:FETCH_ACTIVITIES_LAMBDA_NAME"
}
```

## Testing

### Unit Tests
- ✅ `test_direct_invoke.py`: Event detection logic
- ✅ `test_polyline.py`: Existing polyline extraction (unchanged)
- ✅ All tests pass

### Integration Testing Needed
After deployment, test:
1. **New user flow**: Create new Strava test account, connect, verify activities fetched automatically
2. **Existing user flow**: Disconnect and reconnect, verify no duplicate fetch
3. **Error handling**: Remove `FETCH_ACTIVITIES_LAMBDA_ARN`, verify graceful degradation
4. **CloudWatch logs**: Verify proper logging at each step

## Deployment Requirements

### Environment Variables
Add to `auth_callback` Lambda:
```
FETCH_ACTIVITIES_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT:function:FETCH_ACTIVITIES_NAME
```

### IAM Policy
Update `auth_callback` Lambda execution role with lambda:InvokeFunction permission.

### Lambda Deployment
Deploy updated code to:
- `auth_callback`
- `fetch_activities`

See `DEPLOYMENT_AUTO_FETCH_ACTIVITIES.md` for detailed instructions.

## Rollback Plan
To disable automatic fetching:
1. Remove `FETCH_ACTIVITIES_LAMBDA_ARN` environment variable from `auth_callback`
2. System will log warning but continue working normally
3. Users must manually click "Fetch Activities"

Or revert to commit before these changes.

## Monitoring

### CloudWatch Logs to Watch

#### auth_callback
Success indicators:
```
LOG - New user detected: ATHLETE_ID (Name)
LOG - Triggering automatic activity fetch for new user ATHLETE_ID
LOG - Successfully triggered activity fetch lambda: status 202
```

Warning indicators:
```
WARNING - FETCH_ACTIVITIES_LAMBDA_ARN not configured, skipping automatic activity fetch
WARNING - Failed to trigger activity fetch: [error]
```

#### fetch_activities
Success indicators:
```
Direct lambda invocation detected
Direct invocation for athlete_id: ATHLETE_ID
Direct invocation completed: N activities stored
```

### Metrics to Track
- Number of new user signups
- Activity fetch success rate
- Time to first activity (for new users)
- CloudWatch Lambda invocation counts

## Benefits

### User Experience
- ✅ Seamless onboarding - activities automatically appear after login
- ✅ Reduces friction - no manual "Fetch Activities" step for new users
- ✅ Faster time to value - users see their data immediately

### System Design
- ✅ Non-blocking - login completes quickly
- ✅ Backward compatible - existing users unaffected
- ✅ Graceful degradation - system works without the feature enabled
- ✅ Minimal changes - surgical code updates only

## Files Changed

### Code
- `backend/auth_callback/lambda_function.py` - 51 lines added
- `backend/fetch_activities/lambda_function.py` - 54 lines added
- `backend/fetch_activities/test_direct_invoke.py` - 72 lines added (new file)

### Documentation
- `DEPLOYMENT_AUTO_FETCH_ACTIVITIES.md` - new file
- `ENV_VARS.md` - updated

## Conclusion

This fix provides a seamless onboarding experience for new users by automatically fetching their activities during login. The implementation is minimal, backward-compatible, and follows AWS best practices for serverless architectures.

---

**Author**: GitHub Copilot  
**Date**: 2026-02-05  
**Status**: Ready for Review and Deployment
