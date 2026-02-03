-- Create activities table to store Strava activity data
-- This table stores activities fetched from Strava API

CREATE TABLE IF NOT EXISTS activities (
    id SERIAL PRIMARY KEY,
    athlete_id BIGINT NOT NULL REFERENCES users(athlete_id) ON DELETE CASCADE,
    strava_activity_id BIGINT NOT NULL,
    name TEXT,
    distance DECIMAL(10, 2),  -- in meters
    moving_time INTEGER,       -- in seconds
    elapsed_time INTEGER,      -- in seconds
    total_elevation_gain DECIMAL(10, 2),  -- in meters
    type TEXT,                 -- Run, Ride, Walk, etc.
    start_date TIMESTAMP,
    start_date_local TIMESTAMP,
    timezone TEXT,
    polyline TEXT,             -- encoded polyline
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (athlete_id, strava_activity_id)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_activities_athlete_id ON activities(athlete_id);
CREATE INDEX IF NOT EXISTS idx_activities_start_date ON activities(start_date);
CREATE INDEX IF NOT EXISTS idx_activities_strava_activity_id ON activities(strava_activity_id);

-- Add comment for documentation
COMMENT ON TABLE activities IS 'Stores Strava activity data for athletes';
COMMENT ON COLUMN activities.polyline IS 'Google encoded polyline from Strava (full polyline when available, otherwise summary_polyline)';
COMMENT ON COLUMN activities.distance IS 'Activity distance in meters';
COMMENT ON COLUMN activities.moving_time IS 'Moving time in seconds (excludes pauses)';
COMMENT ON COLUMN activities.elapsed_time IS 'Elapsed time in seconds (includes pauses)';
