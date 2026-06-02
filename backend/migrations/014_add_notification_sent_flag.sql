-- Add flag to track whether email notifications have been sent for an activity
-- This prevents notifications for:
-- 1. Historical activities uploaded during backfills
-- 2. Activities that existed before the email feature was deployed
-- 3. Re-processing/recomputation of existing activities
--
-- Strategy: The match_activity_trail Lambda will check this flag before queueing notifications.
-- It only sends notifications if:
--   - notifications_sent = false (haven't sent yet)
--   - created_at is recent (within last 10 minutes, indicating a fresh webhook event)
--
-- This dual-check ensures we only notify for truly NEW activities from webhooks,
-- not backfills, historical imports, or reprocessing.

ALTER TABLE activities
ADD COLUMN IF NOT EXISTS notifications_sent BOOLEAN NOT NULL DEFAULT false;

-- Add index for querying activities that need notifications
CREATE INDEX IF NOT EXISTS idx_activities_notifications_sent
ON activities(athlete_id, notifications_sent, created_at)
WHERE notifications_sent = false;

-- Add comment to document the column
COMMENT ON COLUMN activities.notifications_sent IS 'Whether email notifications have been sent for this activity. Set to true after notifications are queued to prevent duplicates on reprocessing. Combined with created_at timestamp check to only notify for fresh webhook activities.';

-- Set notifications_sent = true for all existing activities
-- This ensures we don't send notifications for historical data when the feature launches
UPDATE activities SET notifications_sent = true WHERE notifications_sent = false;
