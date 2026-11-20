-- Add last_metadata_refresh_at column to users table
-- Strava mutates activity fields after upload: athlete_count grows as the other
-- participants upload their copy of a group activity, and athletes rename or
-- re-type activities long after the fact. Webhooks cover most of this, but a
-- missed webhook leaves the row permanently stale because the hourly poll only
-- looks back 24 hours and skips webhook-fresh users entirely.
--
-- This column lets scheduled_activity_update sweep *every* connected user on a
-- fixed 6-hour cadence, replacing the old rule that polled every webhook-stale
-- user each hour. One list request per user per sweep covers a multi-day
-- window, so the total scheduled cost is 4 read requests per user per day.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_metadata_refresh_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_last_metadata_refresh_at
    ON users(last_metadata_refresh_at);

COMMENT ON COLUMN users.last_metadata_refresh_at IS 'Timestamp of the last successful activity-metadata refresh sweep for this user. Used by scheduled_activity_update to poll every connected user on a slow cadence, independent of webhook freshness.';
