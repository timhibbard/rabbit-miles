-- Add show_on_leaderboards column to users table for leaderboard privacy control
-- This column controls whether a user's data appears on the leaderboard
-- Default is true (opt-in by default) and all existing users are backfilled to true

-- Add the column with default value
ALTER TABLE users
ADD COLUMN IF NOT EXISTS show_on_leaderboards BOOLEAN NOT NULL DEFAULT true;

-- Backfill existing records to true (though DEFAULT handles this for new inserts)
UPDATE users SET show_on_leaderboards = true WHERE show_on_leaderboards IS NULL;

-- Add index for efficient filtering in leaderboard queries
CREATE INDEX IF NOT EXISTS idx_users_show_on_leaderboards ON users(show_on_leaderboards) WHERE show_on_leaderboards = true;

-- Add comment for documentation
COMMENT ON COLUMN users.show_on_leaderboards IS 'Controls whether user appears on leaderboards (default: true, opt-in by default)';
