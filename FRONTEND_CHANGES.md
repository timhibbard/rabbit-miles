# Frontend Changes - Dashboard Activity Cards

## What Changed

The Dashboard component now displays trail metrics for each activity when available.

## Visual Changes

### Before:
```
┌─────────────────────────────────────┐
│ Morning Run          [Run]          │
│ Mon, Jan 15, 2024                   │
│                                     │
│ Distance    Duration    Pace        │
│ 6.50 mi     52:30      8:05/mi      │
└─────────────────────────────────────┘
```

### After:
```
┌─────────────────────────────────────┐
│ Morning Run          [Run]          │
│ Mon, Jan 15, 2024                   │
│                                     │
│ Distance         Duration    Pace   │
│ 6.50 mi          52:30      8:05/mi │
│ 3.25 mi on trail 26 min on trail    │
│ (green text)     (green text)       │
└─────────────────────────────────────┘
```

## Implementation Details

### Code Changes (Dashboard.jsx)

```javascript
// Calculate trail metrics if available
const distanceOnTrailMiles = activity.distance_on_trail 
  ? (activity.distance_on_trail / METERS_TO_MILES).toFixed(2)
  : null;
const timeOnTrailMinutes = activity.time_on_trail 
  ? Math.floor(activity.time_on_trail / 60)
  : null;

// In the Distance column:
<div>
  <p className="text-gray-500">Distance</p>
  <p className="font-semibold text-gray-900">{distanceMiles} mi</p>
  {distanceOnTrailMiles && (
    <p className="text-xs text-green-600 mt-0.5">
      {distanceOnTrailMiles} mi on trail
    </p>
  )}
</div>

// In the Duration column:
<div>
  <p className="text-gray-500">Duration</p>
  <p className="font-semibold text-gray-900">
    {durationMinutes}:{durationSeconds.toString().padStart(2, '0')}
  </p>
  {timeOnTrailMinutes !== null && (
    <p className="text-xs text-green-600 mt-0.5">
      {timeOnTrailMinutes} min on trail
    </p>
  )}
</div>
```

## User Experience

1. **Initial State**: Activities without trail metrics show as before (no trail info)
2. **After Matching**: Green text appears below distance/duration showing trail metrics
3. **Graceful Degradation**: If trail data is missing, the UI doesn't break
4. **Auto-Update**: Dashboard polls every 30 seconds, so metrics appear automatically
5. **Visual Hierarchy**: Green color distinguishes trail metrics from total metrics

## Display Rules

- Distance on trail: Only shown if `distance_on_trail` > 0
- Time on trail: Only shown if `time_on_trail` is not null
- Units: Miles for distance, minutes for time
- Formatting: 2 decimal places for distance, whole minutes for time
- Color: Green (#059669) to indicate trail-specific metric

## Responsive Design

The existing 3-column grid layout remains:
- Mobile: Stacks vertically (handled by Tailwind)
- Tablet/Desktop: 3 columns (Distance, Duration, Pace)
- Trail metrics appear inline below main metrics

## Accessibility

- Uses semantic HTML structure
- Maintains proper heading hierarchy
- Color is supplementary (text also communicates meaning)
- Screen readers will announce "X mi on trail" after main distance

## Example Scenarios

### Scenario 1: Activity entirely on trail
```
Distance
8.20 mi
8.20 mi on trail  ← 100% on trail

Duration
65:30
65 min on trail   ← All time on trail
```

### Scenario 2: Partial trail activity
```
Distance
10.50 mi
3.75 mi on trail  ← ~36% on trail

Duration
84:12
30 min on trail   ← ~36% of time
```

### Scenario 3: Activity not on trail
```
Distance
5.20 mi
(no trail metric shown)

Duration
41:15
(no trail metric shown)
```

### Scenario 4: Activity not yet matched
```
Distance
6.50 mi
(no trail metric shown - will appear after matching)

Duration
52:30
(no trail metric shown - matching in progress)
```

## Testing Checklist

- [x] Code compiles without errors
- [x] Build succeeds (`npm run build`)
- [ ] Activities without trail metrics display correctly (requires AWS)
- [ ] Activities with trail metrics show green text (requires AWS)
- [ ] Trail metrics format correctly (decimal places, minutes) (requires AWS)
- [ ] Responsive layout works on mobile (requires AWS)
- [ ] Auto-refresh updates trail metrics (requires AWS)

## Browser Compatibility

Uses standard React and Tailwind CSS:
- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)
