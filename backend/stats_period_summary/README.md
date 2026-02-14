# stats_period_summary Lambda Function

## Purpose

Returns period statistics with projections for distance on trail for the authenticated user.

## Endpoint

`GET /stats/period_summary`

## Response

Returns JSON object with three period keys: `week`, `month`, `year`.

Each period contains:
- `current`: number - Actual distance on trail so far this period (miles)
- `previous`: number | null - Distance from previous period (null if no data)
- `projected`: number - Linear extrapolation of current distance to end of period (miles)
- `trend`: "up" | "down" | null - Trend direction (null if no previous or equal)
- `remaining_to_beat`: number | null - Miles needed to beat previous (null if no previous)

Example response:
```json
{
  "week": {
    "current": 10.5,
    "previous": 12.3,
    "projected": 18.2,
    "trend": "up",
    "remaining_to_beat": 1.8
  },
  "month": {
    "current": 45.2,
    "previous": null,
    "projected": 62.1,
    "trend": null,
    "remaining_to_beat": null
  },
  "year": {
    "current": 156.8,
    "previous": 324.5,
    "projected": 298.3,
    "trend": "down",
    "remaining_to_beat": 167.7
  }
}
```

## Period Definitions

- **Week**: Monday 00:00:00 through Sunday 23:59:59
- **Month**: First day 00:00:00 through last day 23:59:59
- **Year**: January 1 00:00:00 through December 31 23:59:59

All calculations use the `start_date_local` field from activities to match Dashboard behavior.

## Projection Formula

```
projected = (current_distance / elapsed_days) * total_days
```

Where:
- `elapsed_days` = days elapsed in period including current day (minimum 1)
- `total_days` = total days in the period (7 for week, varies for month/year)

## Trend Logic

- `"up"` if `projected > previous`
- `"down"` if `projected < previous`
- `null` if `previous is null` or `projected == previous`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_CLUSTER_ARN` | Yes | Aurora cluster ARN |
| `DB_SECRET_ARN` | Yes | Database credentials secret ARN |
| `DB_NAME` | Yes | Database name (default: postgres) |
| `APP_SECRET` | Yes | Secret key for session token verification |
| `FRONTEND_URL` | Yes | Frontend URL for CORS |

## Authentication

Uses cookie-based authentication with signed session tokens. Must match the same `APP_SECRET` used by other authenticated endpoints.

## Testing

Run unit tests:
```bash
cd backend/stats_period_summary
python3 test_lambda.py
```

Tests cover:
- Period boundary calculations
- Monday week start
- Linear projection calculation
- Trend calculation
- Remaining to beat calculation
- Leap year handling
- Elapsed days minimum

## Deployment

Deployed automatically via GitHub Actions when changes are pushed to `main` branch.

Lambda function name is configured via the `LAMBDA_STATS_PERIOD_SUMMARY` secret.
