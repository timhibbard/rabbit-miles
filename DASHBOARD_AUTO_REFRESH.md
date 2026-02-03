# Dashboard Auto-Refresh Feature

## Overview
The Dashboard component now automatically refreshes activities every 30 seconds without requiring manual user refresh. This ensures that when new activities are added or updated in the database (via Strava webhooks), they appear on the dashboard automatically.

## Implementation Details

### Key Changes
1. **Polling Mechanism**: Added `startPolling()` and `stopPolling()` functions that manage a `setInterval` to automatically refresh activities every 30 seconds.

2. **Silent Refresh**: The `loadActivities()` function now accepts a `silent` parameter that controls whether to show the loading spinner. During automatic polling, silent refresh is used to avoid disrupting the user experience.

3. **Overlapping Request Prevention**: Added `isLoadingRef` to prevent multiple concurrent API requests from being triggered if a previous request is still in progress.

4. **Visual Indicator**: Added a green "Auto-updating" badge with an animated pulse indicator next to the "Recent Activities" heading to show users that the dashboard is actively monitoring for updates.

5. **Lifecycle Management**: Polling starts automatically when the user is authenticated and stops on component unmount to prevent memory leaks.

6. **Error Handling**: Silent refresh failures are logged to the console but don't disrupt the UI or clear existing activities, ensuring a smooth user experience even during transient network issues.

### Technical Implementation

#### Constants
```javascript
const ACTIVITY_POLL_INTERVAL = 30000; // Poll every 30 seconds
```

#### State Management
- `isPolling`: Boolean state indicating if polling is active
- `pollingIntervalRef`: Ref to store the interval ID for cleanup
- `isLoadingRef`: Ref to track if a request is in progress (prevents overlapping requests)

#### Key Functions
- `loadActivities(silent)`: Fetches activities with optional silent mode
- `startPolling()`: Initiates automatic polling
- `stopPolling()`: Cleans up polling interval

#### React Hooks
- Uses `useCallback` to memoize functions and prevent unnecessary re-renders
- Uses `useEffect` with proper cleanup to manage polling lifecycle
- Uses `useRef` to store interval ID and loading state without triggering re-renders

### User Experience

1. **Initial Load**: When the dashboard loads and the user is authenticated, activities are fetched immediately and polling starts.

2. **Automatic Updates**: Every 30 seconds, the dashboard silently checks for new or updated activities in the background.

3. **Visual Feedback**: A green "Auto-updating" badge with a pulsing dot appears next to "Recent Activities" to indicate the feature is active.

4. **Manual Refresh**: Users can still manually refresh activities using the "Refresh Activities" button, which triggers a full refresh from Strava.

5. **Seamless Operation**: Silent refreshes don't show loading spinners or clear the current activity list, providing a smooth, non-disruptive experience.

### Integration with Webhooks

This feature works seamlessly with the existing Strava webhook integration:

1. User creates/updates activity in Strava
2. Strava sends webhook event to the backend
3. Webhook processor updates the database
4. Within 30 seconds, the dashboard polling detects the new/updated activity and displays it

### Performance Considerations

- **Lightweight Requests**: Only fetches the 10 most recent activities on each poll
- **No Overlapping**: Prevents multiple concurrent requests using a ref-based flag
- **Silent Operation**: Background polling doesn't trigger loading states or animations
- **Proper Cleanup**: Interval is cleared on component unmount to prevent memory leaks

### Error Handling

- **Silent Failures**: Background polling failures are logged but don't disrupt the UI
- **Existing Activities Preserved**: On silent refresh failure, the current activity list remains displayed
- **Manual Refresh**: Users can always trigger a manual refresh if automatic polling encounters issues

## Configuration

The polling interval can be adjusted by modifying the `ACTIVITY_POLL_INTERVAL` constant:

```javascript
const ACTIVITY_POLL_INTERVAL = 30000; // 30 seconds (in milliseconds)
```

## Future Enhancements

Potential improvements for future iterations:

1. **Configurable Interval**: Allow users to configure the polling interval in settings
2. **Smart Polling**: Implement exponential backoff or pause polling after periods of inactivity
3. **WebSocket Alternative**: Consider WebSocket connection for true real-time updates (would require backend changes)
4. **Activity Notifications**: Add toast notifications when new activities are detected
5. **Pause/Resume Control**: Add UI control to pause and resume automatic polling

## Testing

- ✅ Build passes successfully
- ✅ ESLint shows no errors or warnings
- ✅ No security vulnerabilities detected (CodeQL)
- ✅ No breaking changes to existing functionality
- ✅ Proper cleanup prevents memory leaks
- ✅ Overlapping requests are prevented
- ✅ Silent failures are handled gracefully

## Related Files

- `src/pages/Dashboard.jsx` - Main implementation
- `src/utils/api.js` - API utility functions for fetching activities
- `backend/get_activities/lambda_function.py` - Backend endpoint for fetching activities
- `backend/webhook_processor/lambda_function.py` - Webhook processor that updates activities in the database
