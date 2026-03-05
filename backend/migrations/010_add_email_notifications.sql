-- Add email address and notification preference columns to users table
-- email: user-provided email for notifications
-- notify_activity: opt-in for new-activity / mile-threshold alerts
-- notify_weekly_summary: opt-in for weekly summary emails

ALTER TABLE users
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

ALTER TABLE users
ADD COLUMN IF NOT EXISTS notify_activity BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS notify_weekly_summary BOOLEAN NOT NULL DEFAULT false;

-- Add index for quick lookup of users who want notifications
CREATE INDEX IF NOT EXISTS idx_users_notify_activity ON users(notify_activity) WHERE notify_activity = true;
CREATE INDEX IF NOT EXISTS idx_users_notify_weekly ON users(notify_weekly_summary) WHERE notify_weekly_summary = true;

COMMENT ON COLUMN users.email IS 'User-provided email address for notification emails';
COMMENT ON COLUMN users.notify_activity IS 'Opt-in for new activity / mile-threshold alert emails (default: false)';
COMMENT ON COLUMN users.notify_weekly_summary IS 'Opt-in for weekly summary emails (default: false)';
