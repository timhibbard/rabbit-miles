# rabbitmiles-handle-email-bounces (SNS -> Lambda)
# Handler: lambda_function.handler
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
#
# This Lambda is triggered by SNS notifications from SES when:
# - Emails bounce (hard or soft bounces)
# - Users complain (mark as spam)
#
# Actions taken:
# - Hard bounce: Set email_verified = false (user must re-verify)
# - Complaint: Set email_notifications_enabled = false (auto-unsubscribe)
# - Update email_notifications table with bounce/complaint status

import os
import json
import boto3

rds = boto3.client("rds-data")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")


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


def get_athlete_id_by_email(email):
    """Look up athlete_id by email address"""
    sql = "SELECT athlete_id FROM users WHERE email = :email"
    params = [{"name": "email", "value": {"stringValue": email}}]

    try:
        result = exec_sql(sql, params)
        records = result.get("records", [])

        if records and records[0]:
            return records[0][0].get("longValue")

        return None

    except Exception as e:
        print(f"ERROR: Failed to lookup athlete_id for email {email}: {e}")
        return None


def handle_bounce(bounce_message):
    """Handle email bounce notification"""
    bounce_type = bounce_message.get("bounceType")  # "Transient" or "Permanent"
    bounce_subtype = bounce_message.get("bounceSubType", "")
    bounced_recipients = bounce_message.get("bouncedRecipients", [])

    print(f"Processing bounce: type={bounce_type}, subtype={bounce_subtype}, "
          f"recipients={len(bounced_recipients)}")

    for recipient in bounced_recipients:
        email = recipient.get("emailAddress")
        if not email:
            continue

        print(f"Processing bounce for {email}")

        # Get athlete_id
        athlete_id = get_athlete_id_by_email(email)
        if not athlete_id:
            print(f"WARNING: No user found with email {email}")
            continue

        # Handle permanent (hard) bounces
        if bounce_type == "Permanent":
            print(f"Hard bounce for {email} - setting email_verified=false")

            # Set email_verified = false so user must re-verify
            sql = """
            UPDATE users
            SET email_verified = false, updated_at = now()
            WHERE athlete_id = :athlete_id AND email = :email
            """
            params = [
                {"name": "athlete_id", "value": {"longValue": athlete_id}},
                {"name": "email", "value": {"stringValue": email}}
            ]

            try:
                exec_sql(sql, params)
                print(f"Set email_verified=false for athlete {athlete_id}")
            except Exception as e:
                print(f"ERROR: Failed to update email_verified for athlete {athlete_id}: {e}")

            # Note: We don't update email_notifications table here because:
            # 1. SES bounce events don't reliably identify which specific notification bounced
            # 2. The user-level email_verified flag is sufficient to prevent future sends
            # 3. Updating all pending notifications would incorrectly mark unrelated emails
            # The delivery_status will remain 'pending' but won't be sent due to email_verified=false

        # Log transient (soft) bounces but don't take action
        elif bounce_type == "Transient":
            print(f"Soft bounce for {email} - no action taken")

            # Optionally: track soft bounce count and disable after N bounces
            # For now, just log it


def handle_complaint(complaint_message):
    """Handle spam complaint notification"""
    complained_recipients = complaint_message.get("complainedRecipients", [])
    complaint_feedback_type = complaint_message.get("complaintFeedbackType", "")

    print(f"Processing complaint: type={complaint_feedback_type}, "
          f"recipients={len(complained_recipients)}")

    for recipient in complained_recipients:
        email = recipient.get("emailAddress")
        if not email:
            continue

        print(f"Processing complaint for {email}")

        # Get athlete_id
        athlete_id = get_athlete_id_by_email(email)
        if not athlete_id:
            print(f"WARNING: No user found with email {email}")
            continue

        # User marked email as spam - disable all notifications
        print(f"Spam complaint for {email} - disabling notifications")

        sql = """
        UPDATE users
        SET email_notifications_enabled = false, updated_at = now()
        WHERE athlete_id = :athlete_id AND email = :email
        """
        params = [
            {"name": "athlete_id", "value": {"longValue": athlete_id}},
            {"name": "email", "value": {"stringValue": email}}
        ]

        try:
            exec_sql(sql, params)
            print(f"Disabled notifications for athlete {athlete_id}")
        except Exception as e:
            print(f"ERROR: Failed to disable notifications for athlete {athlete_id}: {e}")

        # Note: We don't update email_notifications table here for the same reason as bounces


def handler(event, context):
    """Process SNS notifications from SES about bounces and complaints"""
    print("=" * 80)
    print("HANDLE EMAIL BOUNCES - START")
    print("=" * 80)
    print(f"Event: {json.dumps(event, default=str)}")

    # Validate environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }

    processed = 0
    failed = 0

    try:
        # SNS sends messages in Records array
        for record in event.get("Records", []):
            try:
                # Parse SNS message
                sns_message = json.loads(record.get("Sns", {}).get("Message", "{}"))

                notification_type = sns_message.get("notificationType")
                print(f"Notification type: {notification_type}")

                if notification_type == "Bounce":
                    bounce = sns_message.get("bounce", {})
                    handle_bounce(bounce)
                    processed += 1

                elif notification_type == "Complaint":
                    complaint = sns_message.get("complaint", {})
                    handle_complaint(complaint)
                    processed += 1

                else:
                    print(f"WARNING: Unknown notification type: {notification_type}")

            except Exception as e:
                print(f"ERROR: Failed to process SNS record: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

        print(f"Processed {processed} bounce/complaint notifications, {failed} failed")
        print("=" * 80)
        print("HANDLE EMAIL BOUNCES - COMPLETE")
        print("=" * 80)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "processed": processed,
                "failed": failed
            })
        }

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to process bounce/complaint event")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("HANDLE EMAIL BOUNCES - FAILED")
        print("=" * 80)

        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error"})
        }
