-- Add email notification support to users table
-- This enables users to receive email notifications for trail milestones and ranking changes

ALTER TABLE users
ADD COLUMN IF NOT EXISTS email TEXT,
ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS send_trail_milestone BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN IF NOT EXISTS send_ranking_change BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN IF NOT EXISTS min_trail_distance_miles DECIMAL(5, 2) NOT NULL DEFAULT 3.0;

-- Add index for email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;

-- Add index for notification queries (users who can receive notifications)
CREATE INDEX IF NOT EXISTS idx_users_email_notifications
ON users(email_notifications_enabled, email_verified)
WHERE email_notifications_enabled = true AND email_verified = true;

-- Add comments to document the columns
COMMENT ON COLUMN users.email IS 'User email address for notifications';
COMMENT ON COLUMN users.email_notifications_enabled IS 'Master switch for email notifications';
COMMENT ON COLUMN users.email_verified IS 'Whether email has been verified (via verification link)';
COMMENT ON COLUMN users.send_trail_milestone IS 'Send email when activity has significant trail miles';
COMMENT ON COLUMN users.send_ranking_change IS 'Send email when leaderboard ranking changes';
COMMENT ON COLUMN users.min_trail_distance_miles IS 'Minimum trail miles to trigger notification (default 3.0)';
