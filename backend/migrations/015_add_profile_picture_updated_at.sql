-- Add profile_picture_updated_at column to users table
-- This records when a user's profile_picture was last refreshed from Strava.
-- Strava versions its avatar URLs, so a URL captured at login goes stale (404s)
-- once the athlete changes their photo. The hourly scheduled poll uses this
-- column to refresh each athlete's picture at most once per PROFILE_PIC_REFRESH
-- window, keeping the extra Strava read requests negligible.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS profile_picture_updated_at TIMESTAMP;

COMMENT ON COLUMN users.profile_picture_updated_at IS 'Timestamp of the last successful profile_picture refresh from Strava. Used by the scheduled poll to throttle per-user avatar refreshes.';
