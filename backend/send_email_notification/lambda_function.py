# rabbitmiles-send-email-notification (SQS -> Lambda)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# APP_SECRET (for unsubscribe token generation)
# FROM_EMAIL (e.g., notifications@rabbitmiles.com)
# FRONTEND_URL (e.g., https://rabbitmiles.com)

import os
import sys
import json
import hmac
import hashlib
import boto3

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

rds = boto3.client("rds-data")
ses = boto3.client("sesv2")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET_STR = os.environ.get("APP_SECRET", "")
APP_SECRET = APP_SECRET_STR.encode() if APP_SECRET_STR else b""
FROM_EMAIL = os.environ.get("FROM_EMAIL", "notifications@rabbitmiles.com")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://rabbitmiles.com").rstrip("/")
SES_CONFIG_SET = os.environ.get("SES_CONFIG_SET", "rabbitmiles-notifications")


def exec_sql(sql, parameters=None):
    """Execute SQL using RDS Data API"""
    kwargs = dict(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        sql=sql,
        database=DB_NAME
    )
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def generate_unsubscribe_token(athlete_id):
    """Generate HMAC-based unsubscribe token"""
    message = f"unsubscribe:{athlete_id}".encode()
    return hmac.new(APP_SECRET, message, hashlib.sha256).hexdigest()[:32]


def get_user(athlete_id):
    """Get user details from database"""
    sql = """
    SELECT athlete_id, email, email_verified, email_notifications_enabled,
           send_trail_milestone, send_ranking_change, min_trail_distance_miles, display_name
    FROM users
    WHERE athlete_id = :athlete_id
    """
    params = [{"name": "athlete_id", "value": {"longValue": athlete_id}}]
    result = exec_sql(sql, params)
    records = result.get("records", [])

    if not records or not records[0]:
        return None

    record = records[0]
    return {
        "athlete_id": record[0].get("longValue") if record[0] else None,
        "email": record[1].get("stringValue") if record[1] and not record[1].get("isNull") else None,
        "email_verified": record[2].get("booleanValue", False) if record[2] else False,
        "email_notifications_enabled": record[3].get("booleanValue", False) if record[3] else False,
        "send_trail_milestone": record[4].get("booleanValue", True) if record[4] else True,
        "send_ranking_change": record[5].get("booleanValue", True) if record[5] else True,
        "min_trail_distance_miles": record[6].get("doubleValue", 3.0) if record[6] else 3.0,
        "display_name": record[7].get("stringValue", "Runner") if record[7] else "Runner"
    }


def already_sent(athlete_id, activity_id, notification_type):
    """Check if notification was already sent"""
    if not activity_id:
        # Can't check for duplicate if no activity_id
        return False

    sql = """
    SELECT id FROM email_notifications
    WHERE athlete_id = :athlete_id
      AND activity_id = :activity_id
      AND notification_type = :notification_type
    LIMIT 1
    """
    params = [
        {"name": "athlete_id", "value": {"longValue": athlete_id}},
        {"name": "activity_id", "value": {"longValue": activity_id}},
        {"name": "notification_type", "value": {"stringValue": notification_type}}
    ]
    result = exec_sql(sql, params)
    records = result.get("records", [])
    return len(records) > 0


def record_notification(athlete_id, activity_id, notification_type, delivery_status, metadata):
    """Record notification in database"""
    sql = """
    INSERT INTO email_notifications
    (athlete_id, activity_id, notification_type, delivery_status, metadata, sent_at, created_at, updated_at)
    VALUES (:athlete_id, :activity_id, :notification_type, :delivery_status, :metadata::jsonb, NOW(), NOW(), NOW())
    """
    params = [
        {"name": "athlete_id", "value": {"longValue": athlete_id}},
        {"name": "notification_type", "value": {"stringValue": notification_type}},
        {"name": "delivery_status", "value": {"stringValue": delivery_status}},
        {"name": "metadata", "value": {"stringValue": json.dumps(metadata)}}
    ]

    if activity_id:
        params.append({"name": "activity_id", "value": {"longValue": activity_id}})
    else:
        params.append({"name": "activity_id", "value": {"isNull": True}})

    try:
        exec_sql(sql, params)
        print(f"LOG - Recorded notification: {notification_type} for athlete {athlete_id}, status {delivery_status}")
    except Exception as e:
        print(f"ERROR - Failed to record notification: {e}")


def send_email(notification_type, user, activity_id, metadata):
    """Send email via SES"""
    athlete_id = user["athlete_id"]
    email = user["email"]
    display_name = user["display_name"]

    # Generate unsubscribe token
    unsubscribe_token = generate_unsubscribe_token(athlete_id)
    unsubscribe_url = f"{FRONTEND_URL}/unsubscribe?token={unsubscribe_token}"
    settings_url = f"{FRONTEND_URL}/settings"

    # Build email based on notification type
    if notification_type == "trail_milestone":
        trail_distance_miles = metadata.get("trail_distance_miles", 0)
        trail_name = metadata.get("trail_name", "a trail")
        activity_name = metadata.get("activity_name", "your activity")
        activity_url = metadata.get("activity_url", f"{FRONTEND_URL}/dashboard")

        subject = f"🎉 {trail_distance_miles} new miles on {trail_name}!"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333;">Great job, {display_name}!</h1>
            <p style="font-size: 16px;">
                You just covered <strong>{trail_distance_miles} miles</strong> on <strong>{trail_name}</strong>!
            </p>
            <p style="color: #666;">Activity: {activity_name}</p>
            <p style="margin: 30px 0;">
                <a href="{activity_url}"
                   style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    View Activity
                </a>
            </p>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 40px 0;">
            <p style="color: #999; font-size: 12px;">
                <a href="{settings_url}" style="color: #999;">Email Preferences</a> |
                <a href="{unsubscribe_url}" style="color: #999;">Unsubscribe</a>
            </p>
        </body>
        </html>
        """

        text_body = f"""
Great job, {display_name}!

You just covered {trail_distance_miles} miles on {trail_name}!

Activity: {activity_name}

View Activity: {activity_url}

---
Email Preferences: {settings_url}
Unsubscribe: {unsubscribe_url}
        """.strip()

    elif notification_type == "ranking_change":
        old_rank = metadata.get("old_rank")
        new_rank = metadata.get("new_rank")
        window = metadata.get("window", "week")
        activity_type = metadata.get("activity_type", "Run")
        activity_name = metadata.get("activity_name", "your activity")
        trail_distance_miles = metadata.get("trail_distance_miles", 0)
        leaderboard_url = metadata.get("leaderboard_url", f"{FRONTEND_URL}/leaderboard")

        if old_rank:
            rank_text = f"from <strong>#{old_rank}</strong> to <strong>#{new_rank}</strong>"
            rank_text_plain = f"from #{old_rank} to #{new_rank}"
        else:
            rank_text = f"to <strong>#{new_rank}</strong>"
            rank_text_plain = f"to #{new_rank}"

        subject = f"🏆 You're now #{new_rank} on the {window} {activity_type} leaderboard!"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333;">Congratulations, {display_name}!</h1>
            <p style="font-size: 16px;">
                Your ranking improved {rank_text} on the <strong>{window} {activity_type} leaderboard</strong>!
            </p>
            <p style="color: #666;">
                Activity that moved you up: {activity_name} ({trail_distance_miles} miles on trails)
            </p>
            <p style="margin: 30px 0;">
                <a href="{leaderboard_url}"
                   style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    View Leaderboard
                </a>
            </p>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 40px 0;">
            <p style="color: #999; font-size: 12px;">
                <a href="{settings_url}" style="color: #999;">Email Preferences</a> |
                <a href="{unsubscribe_url}" style="color: #999;">Unsubscribe</a>
            </p>
        </body>
        </html>
        """

        text_body = f"""
Congratulations, {display_name}!

Your ranking improved {rank_text_plain} on the {window} {activity_type} leaderboard!

Activity that moved you up: {activity_name} ({trail_distance_miles} miles on trails)

View Leaderboard: {leaderboard_url}

---
Email Preferences: {settings_url}
Unsubscribe: {unsubscribe_url}
        """.strip()

    else:
        print(f"ERROR - Unknown notification type: {notification_type}")
        return False

    # Send email via SES
    try:
        ses.send_email(
            FromEmailAddress=FROM_EMAIL,
            Destination={'ToAddresses': [email]},
            Content={
                'Simple': {
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        },
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            },
            ConfigurationSetName=SES_CONFIG_SET
        )
        print(f"LOG - Email sent to {email}: {subject}")
        return True

    except Exception as e:
        print(f"ERROR - Failed to send email to {email}: {e}")
        return False


def handler(event, context):
    """Process email notifications from SQS queue"""
    print("=" * 80)
    print("SEND EMAIL NOTIFICATION - START")
    print("=" * 80)

    processed = 0
    failed = 0

    for record in event.get("Records", []):
        try:
            message = json.loads(record["body"])

            notification_type = message.get("notification_type")
            athlete_id = message.get("athlete_id")
            activity_id = message.get("activity_id")
            metadata = message.get("metadata", {})

            print(f"LOG - Processing {notification_type} notification for athlete {athlete_id}")

            # Get user details
            user = get_user(athlete_id)

            # Check if user exists and has notifications enabled
            if not user:
                print(f"LOG - User {athlete_id} not found, skipping")
                continue

            if not user["email"] or not user["email_verified"]:
                print(f"LOG - User {athlete_id} has no verified email, skipping")
                continue

            if not user["email_notifications_enabled"]:
                print(f"LOG - User {athlete_id} has notifications disabled, skipping")
                continue

            # Check notification-specific preferences
            if notification_type == "trail_milestone":
                if not user["send_trail_milestone"]:
                    print(f"LOG - User {athlete_id} has trail milestone notifications disabled, skipping")
                    continue

                # Check minimum distance threshold
                trail_distance = metadata.get("trail_distance_miles", 0)
                if trail_distance < user["min_trail_distance_miles"]:
                    print(f"LOG - Trail distance {trail_distance} below threshold {user['min_trail_distance_miles']}, skipping")
                    continue

            elif notification_type == "ranking_change":
                if not user["send_ranking_change"]:
                    print(f"LOG - User {athlete_id} has ranking change notifications disabled, skipping")
                    continue

            # Check for duplicate notifications
            if already_sent(athlete_id, activity_id, notification_type):
                print(f"LOG - Notification already sent for athlete {athlete_id}, activity {activity_id}, type {notification_type}")
                continue

            # Send email
            success = send_email(notification_type, user, activity_id, metadata)

            # Record notification
            if success:
                record_notification(athlete_id, activity_id, notification_type, "sent", metadata)
                processed += 1
            else:
                record_notification(athlete_id, activity_id, notification_type, "failed", metadata)
                failed += 1

        except Exception as e:
            print(f"ERROR - Failed to process SQS message: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"LOG - Processed {processed} notifications, {failed} failed")
    print("=" * 80)
    print("SEND EMAIL NOTIFICATION - COMPLETE")
    print("=" * 80)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": processed,
            "failed": failed
        })
    }
