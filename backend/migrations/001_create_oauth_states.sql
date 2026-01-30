-- Create table for temporary OAuth state storage
-- This table stores OAuth state tokens during the authorization flow
-- States expire after 10 minutes (600 seconds)

CREATE TABLE IF NOT EXISTS oauth_states (
    state VARCHAR(255) PRIMARY KEY,
    expires_at BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create index on expires_at for cleanup queries
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON oauth_states(expires_at);

-- Optional: Add a cleanup function to delete expired states
-- This can be run periodically by a scheduled Lambda or cron job
-- DELETE FROM oauth_states WHERE expires_at < EXTRACT(EPOCH FROM NOW());
