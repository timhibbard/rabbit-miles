-- Add time_on_trail and distance_on_trail columns to activities table
-- These columns track how much time (seconds) and distance (meters) 
-- of the activity occurred on designated trails

ALTER TABLE activities
ADD COLUMN IF NOT EXISTS time_on_trail INTEGER,
ADD COLUMN IF NOT EXISTS distance_on_trail DECIMAL(10, 2);

-- Add comments for documentation
COMMENT ON COLUMN activities.time_on_trail IS 'Time spent on trail in seconds (subset of moving_time)';
COMMENT ON COLUMN activities.distance_on_trail IS 'Distance covered on trail in meters (subset of total distance)';

-- Create index for efficient queries on trail metrics
CREATE INDEX IF NOT EXISTS idx_activities_time_on_trail ON activities(time_on_trail) WHERE time_on_trail IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activities_distance_on_trail ON activities(distance_on_trail) WHERE distance_on_trail IS NOT NULL;
