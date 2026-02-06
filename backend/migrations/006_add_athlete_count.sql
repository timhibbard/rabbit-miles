-- Add athlete_count column to activities table
-- This column stores the number of athletes who participated in a group activity
-- athlete_count > 1 indicates a group activity

ALTER TABLE activities 
ADD COLUMN athlete_count INTEGER DEFAULT 1;

-- Add comment for documentation
COMMENT ON COLUMN activities.athlete_count IS 'Number of athletes who participated in this activity (from Strava API). Values > 1 indicate group activities.';

-- Create index for filtering group activities
CREATE INDEX IF NOT EXISTS idx_activities_athlete_count ON activities(athlete_count);
