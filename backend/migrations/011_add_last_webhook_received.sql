-- Add last_webhook_received_at column to users table
-- This records the timestamp of the most recent successfully-processed Strava
-- webhook event for each user, allowing the hourly scheduled_activity_update
-- backstop to skip users whose data is already being kept current via webhooks.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_webhook_received_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_last_webhook_received_at
    ON users(last_webhook_received_at);

COMMENT ON COLUMN users.last_webhook_received_at IS 'Timestamp of the last successfully-processed Strava webhook event for this user. Used by the hourly scheduled poll to skip users already covered by webhooks.';
