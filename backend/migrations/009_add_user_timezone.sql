-- Add timezone preference to users table
-- This field stores the user's preferred timezone for date boundary calculations
-- Format: IANA timezone identifier (e.g., "America/New_York", "America/Los_Angeles")
-- Falls back to "America/New_York" (US Eastern) if not set

ALTER TABLE users
ADD COLUMN IF NOT EXISTS timezone VARCHAR(100);

-- Add index for timezone lookups
CREATE INDEX IF NOT EXISTS idx_users_timezone ON users(timezone);

-- Add comment to column
COMMENT ON COLUMN users.timezone IS 'IANA timezone identifier for date boundary calculations. Falls back to America/New_York if NULL.';
