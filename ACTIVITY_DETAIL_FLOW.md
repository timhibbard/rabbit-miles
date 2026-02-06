# Activity Detail Page User Flow

## User Journey

```
1. Dashboard Page
   ┌─────────────────────────────────────────────────┐
   │ RabbitMiles Dashboard                           │
   │                                                 │
   │ Stats Cards: Total | Week | Month | Year       │
   │                                                 │
   │ Recent Activities:                              │
   │ ┌──────────────────────────────────────┐       │
   │ │ Morning Run          [Ride badge]     │←─── Clickable!
   │ │ Today, 8:00 AM                        │       │
   │ │ Distance: 5.2 mi (3.1 mi on trail)   │       │
   │ │ Duration: 42:15    Pace: 8:07/mi     │       │
   │ └──────────────────────────────────────┘       │
   │ ┌──────────────────────────────────────┐       │
   │ │ Evening Ride         [Ride badge]     │       │
   │ │ Yesterday, 6:30 PM                    │       │
   │ │ Distance: 12.4 mi (8.2 mi on trail)  │       │
   │ │ Duration: 1:15:30  Pace: 6:05/mi     │       │
   │ └──────────────────────────────────────┘       │
   └─────────────────────────────────────────────────┘
                      │
                      │ Click on activity
                      ▼
2. Activity Detail Page
   ┌─────────────────────────────────────────────────┐
   │ ← Back to Dashboard                             │
   │                                                 │
   │ Morning Run                    [Run] [View on   │
   │ Monday, February 4, 2026, 8:00 AM     Strava]  │
   │                                                 │
   │ Stats Grid:                                     │
   │ ┌──────────┬──────────┬──────────┬──────────┐ │
   │ │Distance  │Moving    │Pace      │Elevation │ │
   │ │5.2 mi    │Time      │8:07/mi   │125 ft    │ │
   │ │3.1 mi on │42:15     │          │          │ │
   │ │trail     │25:30 on  │          │          │ │
   │ │          │trail     │          │          │ │
   │ └──────────┴──────────┴──────────┴──────────┘ │
   │                                                 │
   │ Route Map                                       │
   │ ┌─────────────────────────────────────────────┐│
   │ │                                             ││
   │ │     ╱╲      ┌─────┐                        ││
   │ │    ╱  ╲     │     │    🟢 Green line       ││
   │ │   🟢   🟢   │ Map │    (on trail)          ││
   │ │  🟢     🟢  └─────┘                        ││
   │ │ 🟢       🔵          🔵 Blue line          ││
   │ │🟢         🔵         (off trail)           ││
   │ │           🔵                                ││
   │ │          🔵                                 ││
   │ │                                             ││
   │ └─────────────────────────────────────────────┘│
   │ 🟢 On trail  🔵 Off trail                      │
   └─────────────────────────────────────────────────┘
```

## Key Features

### Interactive Map
- **Leaflet-based** interactive map
- **Pan and zoom** to explore the route
- **Color-coded segments**:
  - Green (#10b981): Portions on the trail
  - Blue (#3b82f6): Portions off the trail
- **Automatic bounds fitting** to show entire route
- **OpenStreetMap tiles** for base layer

### Trail Segment Calculation
The frontend calculates which segments are on/off trail by:
1. Loading trail GeoJSON data (main trail + spurs)
2. For each point in the activity route:
   - Calculate distance to nearest trail segment
   - Mark as "on trail" if within 25 meters
3. Group consecutive on/off trail points into segments
4. Render each segment with appropriate color

### Activity Information
- **Complete statistics**: distance, moving time, pace, elevation gain
- **Trail metrics**: Shows distance and time on trail (when available)
- **Activity type badge**: Visual indicator (Run, Ride, Walk)
- **Strava link**: Direct link to view the original activity on Strava
- **Date/time display**: Full timestamp of activity

### Error Handling
- Loading states while fetching data
- Graceful handling of missing polyline data
- Fallback display for activities without trail matching
- Proper authentication flow (redirects to /connect if not logged in)

## Technical Implementation

### Data Flow
```
User clicks activity
       ↓
Frontend calls: GET /activities/:id
       ↓
Backend Lambda: get_activity_detail
       ↓
Validates session cookie
       ↓
Checks activity ownership
       ↓
Returns activity + polyline
       ↓
Frontend decodes polyline
       ↓
Loads trail GeoJSON
       ↓
Calculates trail segments
       ↓
Renders map with colored polylines
```

### Performance Considerations
- Trail GeoJSON files (~116KB total) loaded once per activity view
- Polyline decoding is efficient (O(n) where n = polyline length)
- Trail matching calculation optimized with spatial checks
- Map library (Leaflet) handles rendering performance
