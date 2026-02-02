-- Create webhook_events table to track processed webhook events
-- This table provides idempotency for webhook event processing
-- Events are deduplicated using the idempotency_key

CREATE TABLE IF NOT EXISTS webhook_events (
    id SERIAL PRIMARY KEY,
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    subscription_id BIGINT NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    object_id BIGINT NOT NULL,
    aspect_type VARCHAR(50) NOT NULL,
    owner_id BIGINT NOT NULL,
    event_time BIGINT NOT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_webhook_events_idempotency_key ON webhook_events(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_webhook_events_owner_id ON webhook_events(owner_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_object_id ON webhook_events(object_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_processed_at ON webhook_events(processed_at);

-- Add comments for documentation
COMMENT ON TABLE webhook_events IS 'Tracks processed Strava webhook events for idempotency';
COMMENT ON COLUMN webhook_events.idempotency_key IS 'Unique key: subscription_id:object_id:aspect_type:event_time';
COMMENT ON COLUMN webhook_events.object_type IS 'Type of object: activity or athlete';
COMMENT ON COLUMN webhook_events.aspect_type IS 'Type of change: create, update, or delete';
COMMENT ON COLUMN webhook_events.event_time IS 'Unix timestamp from Strava webhook event';
