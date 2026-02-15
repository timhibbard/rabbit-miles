-- Create leaderboard_agg table for storing aggregated leaderboard data
-- This table stores pre-computed leaderboard rankings by time window
-- Updated incrementally by webhook processor when activities are created/updated

CREATE TABLE IF NOT EXISTS leaderboard_agg (
    id BIGSERIAL PRIMARY KEY,
    window TEXT NOT NULL,                    -- 'week', 'month', 'year'
    window_key TEXT NOT NULL,                -- canonical period id: 'week_2026-02-09', 'month_2026-02', 'year_2026'
    metric TEXT NOT NULL,                    -- 'distance' initially, extensible for future metrics
    activity_type TEXT NOT NULL,             -- 'all' initially, extensible for specific types
    athlete_id BIGINT NOT NULL REFERENCES users(athlete_id) ON DELETE CASCADE,
    value NUMERIC NOT NULL,                  -- aggregated value (e.g., total distance in meters)
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for efficient leaderboard queries (ordered by value desc)
CREATE INDEX IF NOT EXISTS idx_leaderboard_agg_ranking 
ON leaderboard_agg(window_key, metric, activity_type, value DESC);

-- Index for efficient user-specific queries
CREATE INDEX IF NOT EXISTS idx_leaderboard_agg_user 
ON leaderboard_agg(athlete_id, window_key, metric, activity_type);

-- Index for cleanup/maintenance queries
CREATE INDEX IF NOT EXISTS idx_leaderboard_agg_window_key 
ON leaderboard_agg(window_key);

-- Add comments for documentation
COMMENT ON TABLE leaderboard_agg IS 'Pre-computed leaderboard aggregations by time window, updated incrementally by webhook processor';
COMMENT ON COLUMN leaderboard_agg.window IS 'Time window type: week, month, or year';
COMMENT ON COLUMN leaderboard_agg.window_key IS 'Canonical period identifier for efficient querying';
COMMENT ON COLUMN leaderboard_agg.metric IS 'Metric being aggregated (distance, etc.)';
COMMENT ON COLUMN leaderboard_agg.activity_type IS 'Activity type filter (all, Run, Ride, etc.)';
COMMENT ON COLUMN leaderboard_agg.value IS 'Aggregated metric value (e.g., total distance in meters)';
