-- Add last_strava_fetch column to users table
-- This records the timestamp of the most recent successful Strava activity
-- fetch for each user, enabling a per-user cooldown to avoid hitting the
-- Strava API rate limit.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_strava_fetch TIMESTAMP;

COMMENT ON COLUMN users.last_strava_fetch IS 'Timestamp of the last successful Strava activities fetch for this user. Used to enforce a per-user fetch cooldown.';
