# webhook Lambda function (API Gateway HTTP API -> Lambda proxy)
# Handler: lambda_function.handler
#
# Env vars required:
# WEBHOOK_VERIFY_TOKEN (string for Strava subscription validation)
# WEBHOOK_SQS_QUEUE_URL (SQS queue URL for async event processing)
#
# Routes:
# GET /strava/webhook - Subscription validation handshake
# POST /strava/webhook - Event delivery from Strava

import os
import json
import boto3

sqs = boto3.client("sqs")

VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "")
SQS_QUEUE_URL = os.environ.get("WEBHOOK_SQS_QUEUE_URL", "")


def handle_subscription_validation(event):
    """
    Handle GET request for Strava subscription validation.
    Strava sends: ?hub.mode=subscribe&hub.challenge=XXX&hub.verify_token=YYY
    We must respond within 2 seconds with {"hub.challenge":"XXX"} and status 200
    """
    qs = event.get("queryStringParameters") or {}
    
    hub_mode = qs.get("hub.mode")
    hub_challenge = qs.get("hub.challenge")
    hub_verify_token = qs.get("hub.verify_token")
    
    print(f"Subscription validation request: mode={hub_mode}, challenge={hub_challenge}, verify_token={hub_verify_token}")
    
    # Validate the request
    if hub_mode != "subscribe":
        print(f"ERROR: Invalid hub.mode: {hub_mode}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "invalid hub.mode"})
        }
    
    if not hub_challenge:
        print("ERROR: Missing hub.challenge")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "missing hub.challenge"})
        }
    
    # Verify the token matches our expected value
    if hub_verify_token != VERIFY_TOKEN:
        print(f"ERROR: Invalid verify_token. Expected: {VERIFY_TOKEN}, Got: {hub_verify_token}")
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "invalid verify_token"})
        }
    
    print(f"Subscription validation successful, echoing challenge: {hub_challenge}")
    
    # Echo the challenge back as required by Strava
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"hub.challenge": hub_challenge})
    }


def handle_webhook_event(event):
    """
    Handle POST request with webhook event from Strava.
    Must respond within 2 seconds with 200 OK.
    Event processing happens asynchronously via SQS.
    """
    try:
        # Parse the event body
        body = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            import base64
            body = base64.b64decode(body).decode()
        
        webhook_event = json.loads(body)
        
        print(f"Received webhook event: {json.dumps(webhook_event)}")
        
        # Validate event has required fields
        object_type = webhook_event.get("object_type")
        aspect_type = webhook_event.get("aspect_type")
        object_id = webhook_event.get("object_id")
        owner_id = webhook_event.get("owner_id")
        subscription_id = webhook_event.get("subscription_id")
        event_time = webhook_event.get("event_time")
        
        if not all([object_type, aspect_type, object_id, owner_id, subscription_id, event_time]):
            print(f"WARNING: Event missing required fields: {webhook_event}")
            # Still return 200 to avoid retries for malformed events
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "received"})
            }
        
        # Only process activity events (ignore athlete events for now)
        if object_type != "activity":
            print(f"Ignoring non-activity event: {object_type}")
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "received"})
            }
        
        # Send event to SQS for async processing
        if not SQS_QUEUE_URL:
            print("WARNING: WEBHOOK_SQS_QUEUE_URL not configured, event will not be processed")
            # Still return 200 to Strava
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "received"})
            }
        
        # Create idempotency key for event
        idempotency_key = f"{subscription_id}:{object_id}:{aspect_type}:{event_time}"
        
        message_attributes = {
            "object_type": {"DataType": "String", "StringValue": str(object_type)},
            "aspect_type": {"DataType": "String", "StringValue": str(aspect_type)},
            "object_id": {"DataType": "Number", "StringValue": str(object_id)},
            "owner_id": {"DataType": "Number", "StringValue": str(owner_id)},
            "idempotency_key": {"DataType": "String", "StringValue": idempotency_key}
        }
        
        # Build SQS message parameters
        sqs_params = {
            "QueueUrl": SQS_QUEUE_URL,
            "MessageBody": json.dumps(webhook_event),
            "MessageAttributes": message_attributes
        }
        
        # Add FIFO-specific parameters if using a FIFO queue (URL ends with .fifo)
        if SQS_QUEUE_URL.endswith(".fifo"):
            sqs_params["MessageDeduplicationId"] = idempotency_key
            sqs_params["MessageGroupId"] = str(owner_id)
        
        sqs.send_message(**sqs_params)
        
        print(f"Event sent to SQS: {idempotency_key}")
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "received"})
        }
        
    except Exception as e:
        print(f"ERROR processing webhook event: {e}")
        import traceback
        traceback.print_exc()
        
        # Still return 200 to avoid retries for errors we can't handle
        # The event will be logged and can be investigated
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "received"})
        }


def handler(event, context):
    """
    Main Lambda handler for Strava webhook events.
    Routes GET requests to subscription validation.
    Routes POST requests to event processing.
    """
    print(f"Webhook handler invoked")
    print(f"Event: {json.dumps(event, default=str)}")
    
    # Validate required environment variables
    if not VERIFY_TOKEN:
        print("ERROR: WEBHOOK_VERIFY_TOKEN not configured")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "server configuration error"})
        }
    
    # Get HTTP method from API Gateway event
    http_method = event.get("requestContext", {}).get("http", {}).get("method")
    
    if not http_method:
        print("ERROR: Could not determine HTTP method from event")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "invalid request"})
        }
    
    if http_method == "GET":
        return handle_subscription_validation(event)
    elif http_method == "POST":
        return handle_webhook_event(event)
    else:
        print(f"ERROR: Unsupported HTTP method: {http_method}")
        return {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "method not allowed"})
        }
