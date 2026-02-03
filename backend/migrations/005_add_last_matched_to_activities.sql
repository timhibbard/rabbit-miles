-- Add last_matched column to activities table
-- This column records when the activity was last checked against the trail matching database

ALTER TABLE activities 
ADD COLUMN IF NOT EXISTS last_matched TIMESTAMP DEFAULT NULL;

-- Add index for efficient queries
CREATE INDEX IF NOT EXISTS idx_activities_last_matched ON activities(last_matched);

-- Add comment for documentation
COMMENT ON COLUMN activities.last_matched IS 'Timestamp when activity was last checked against trail matching database';
