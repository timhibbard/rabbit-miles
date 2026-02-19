# Activity Type Filtering Feature - Visual Summary

## What Changed

### Frontend (Leaderboard Page)

#### Before:
```
🏆 Leaderboard (Admin Preview)

[Time Period Selector]
  [This Week] [This Month] [This Year]

[Leaderboard Table - showing ALL activities]
```

#### After:
```
🏆 Leaderboard (Admin Preview)

[Time Period Selector]
  [This Week] [This Month] [This Year]

[Activity Type Filter] ⬅️ NEW!
  [Bike] [Foot ✓]        ⬅️ Foot is selected by default

[Leaderboard Table - showing ONLY Foot activities (Run, Walk)]
```

### How the Filter Works

1. **Default State**: When page loads, only "Foot" activities are shown
   - selectedActivityType = 'foot'
   - Shows only Run and Walk activities

2. **Bike Button Clicked**:
   - If Foot was selected → Shows both Bike and Foot ('all')
   - If All was showing → Shows only Bike ('bike')

3. **Foot Button Clicked**:
   - If Bike was selected → Shows both Bike and Foot ('all')
   - If All was showing → Shows only Foot ('foot')

### Visual States

#### State 1: Foot Only (DEFAULT)
```
[Bike (gray)] [Foot (orange)]
Shows: Run, Walk
```

#### State 2: Bike Only
```
[Bike (orange)] [Foot (gray)]
Shows: Ride
```

#### State 3: Both (All)
```
[Bike (orange)] [Foot (orange)]
Shows: Run, Walk, Ride
```

## Backend Changes

### Webhook Processor
Now creates 3 aggregate rows per activity:
- 'all' → Total for all activity types
- 'foot' → Total for Run + Walk
- 'bike' → Total for Ride

Example for a Run activity (10 miles):
```
leaderboard_agg table:
- window_key='week_2026-02-09', activity_type='all', value=10
- window_key='week_2026-02-09', activity_type='foot', value=10
```

Example for a Ride activity (20 miles):
```
leaderboard_agg table:
- window_key='week_2026-02-09', activity_type='all', value=20
- window_key='week_2026-02-09', activity_type='bike', value=20
```

## API Flow

Frontend → Backend:
```javascript
// Default request (Foot only)
GET /leaderboard?window=week&activity_type=foot

// Backend queries:
SELECT * FROM leaderboard_agg 
WHERE activity_type = 'foot'
ORDER BY value DESC
```

## User Experience

1. User opens leaderboard
2. Sees only runners (Run/Walk activities) by default
3. Can toggle to see:
   - Only cyclists (Bike button)
   - All athletes (Both buttons)
   - Back to runners (Foot button)

This matches the Dashboard behavior where users can filter their own activities.
