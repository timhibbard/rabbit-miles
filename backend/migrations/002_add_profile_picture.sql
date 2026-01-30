-- Add profile_picture column to users table
-- This allows us to store the Strava profile picture URL for display on the dashboard

ALTER TABLE users
ADD COLUMN IF NOT EXISTS profile_picture TEXT;

-- Add comment for documentation
COMMENT ON COLUMN users.profile_picture IS 'URL to the athlete profile picture from Strava';
