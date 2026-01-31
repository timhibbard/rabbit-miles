-- Create users table
-- This is the main table that stores user information from Strava OAuth
-- athlete_id is the primary key from Strava

CREATE TABLE IF NOT EXISTS users (
    athlete_id BIGINT PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    profile_picture TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL CHECK (expires_at > 0),  -- Unix timestamp in seconds (not milliseconds)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create index on updated_at for tracking recent activity
CREATE INDEX IF NOT EXISTS idx_users_updated_at ON users(updated_at);

-- Add comment for documentation
COMMENT ON TABLE users IS 'Stores user information and Strava OAuth tokens';
COMMENT ON COLUMN users.athlete_id IS 'Strava athlete ID (primary key)';
COMMENT ON COLUMN users.display_name IS 'User display name from Strava (firstname + lastname)';
COMMENT ON COLUMN users.profile_picture IS 'URL to the athlete profile picture from Strava';
COMMENT ON COLUMN users.access_token IS 'Strava OAuth access token';
COMMENT ON COLUMN users.refresh_token IS 'Strava OAuth refresh token';
COMMENT ON COLUMN users.expires_at IS 'Unix timestamp in seconds (not milliseconds) when the access token expires';
COMMENT ON COLUMN users.created_at IS 'Timestamp when the user first connected';
COMMENT ON COLUMN users.updated_at IS 'Timestamp when the user last updated their connection';
