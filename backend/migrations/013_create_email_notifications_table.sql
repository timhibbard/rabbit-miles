-- Create table to track sent email notifications
-- This prevents duplicate notifications and allows monitoring delivery status

CREATE TABLE IF NOT EXISTS email_notifications (
    id BIGSERIAL PRIMARY KEY,
    athlete_id BIGINT NOT NULL REFERENCES users(athlete_id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    notification_type TEXT NOT NULL CHECK (notification_type IN ('trail_milestone', 'ranking_change')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'sent', 'failed', 'bounced')),
    metadata JSONB,  -- Store details like old_rank, new_rank, trail_distance, window, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_email_notifications_athlete_id ON email_notifications(athlete_id);
CREATE INDEX IF NOT EXISTS idx_email_notifications_activity_id ON email_notifications(activity_id);
CREATE INDEX IF NOT EXISTS idx_email_notifications_sent_at ON email_notifications(sent_at);
CREATE INDEX IF NOT EXISTS idx_email_notifications_status ON email_notifications(delivery_status);

-- Prevent duplicate notifications for same activity
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_notifications_unique_activity
ON email_notifications(athlete_id, activity_id, notification_type)
WHERE activity_id IS NOT NULL;

-- Add comments to document the table and columns
COMMENT ON TABLE email_notifications IS 'Tracks sent email notifications to prevent duplicates and monitor delivery';
COMMENT ON COLUMN email_notifications.notification_type IS 'Type of notification: trail_milestone or ranking_change';
COMMENT ON COLUMN email_notifications.delivery_status IS 'Email delivery status tracked via SES callbacks';
COMMENT ON COLUMN email_notifications.metadata IS 'Additional context (e.g., {"old_rank": 5, "new_rank": 3, "window": "week", "trail_distance_miles": 4.2})';
