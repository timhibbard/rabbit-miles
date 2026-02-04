# match_unmatched_activities Lambda function
# Finds activities where last_matched IS NULL and triggers matching for them
# 
# This Lambda can be invoked:
# 1. Manually (for backfilling existing activities)
# 2. On a schedule (e.g., daily) to catch any missed activities
#
# Env vars required:
# DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME=postgres
# MATCH_ACTIVITY_LAMBDA_ARN (ARN of match_activity_trail Lambda)

import os
import json
import boto3

rds = boto3.client("rds-data")
lambda_client = boto3.client("lambda")

# Get environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "postgres")
MATCH_ACTIVITY_LAMBDA_ARN = os.environ.get("MATCH_ACTIVITY_LAMBDA_ARN", "")

# Batch size for processing activities
BATCH_SIZE = 10


def _exec_sql(sql, parameters=None):
    """Execute SQL statement using RDS Data API"""
    kwargs = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)


def get_unmatched_activities(limit=100):
    """Get activities where last_matched IS NULL"""
    sql = """
    SELECT id, strava_activity_id, name
    FROM activities
    WHERE last_matched IS NULL
    ORDER BY start_date DESC
    LIMIT :limit
    """
    
    params = [{"name": "limit", "value": {"longValue": limit}}]
    
    result = _exec_sql(sql, params)
    records = result.get("records", [])
    
    activities = []
    for record in records:
        activities.append({
            "id": int(record[0].get("longValue", 0)),
            "strava_activity_id": int(record[1].get("longValue", 0)),
            "name": record[2].get("stringValue", "")
        })
    
    return activities


def invoke_match_activity(activity_id):
    """
    Invoke match_activity_trail Lambda for a single activity.
    
    Note: Uses async invocation (Event type), which returns True if the invocation
    was successfully queued, NOT if the actual matching succeeded. The matching
    happens asynchronously in the background.
    
    Returns:
        bool: True if invocation was queued, False if invocation failed
    """
    payload = json.dumps({"activity_id": activity_id})
    
    try:
        response = lambda_client.invoke(
            FunctionName=MATCH_ACTIVITY_LAMBDA_ARN,
            InvocationType='Event',  # Async invocation - returns immediately after queuing
            Payload=payload
        )
        print(f"Queued match_activity_trail for activity {activity_id}: {response['StatusCode']}")
        return True
    except Exception as e:
        print(f"Failed to queue match_activity_trail for activity {activity_id}: {e}")
        return False


def handler(event, context):
    """
    Lambda handler for matching unmatched activities.
    
    Finds activities where last_matched IS NULL and triggers matching for them.
    Processes in batches to avoid overwhelming the match_activity_trail Lambda.
    """
    print(f"match_unmatched_activities handler invoked")
    print(f"Event: {json.dumps(event, default=str)}")
    
    # Validate required environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Missing DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }
    
    if not MATCH_ACTIVITY_LAMBDA_ARN:
        print("ERROR: Missing MATCH_ACTIVITY_LAMBDA_ARN")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server configuration error"})
        }
    
    try:
        # Get unmatched activities
        print(f"Fetching up to {BATCH_SIZE} unmatched activities...")
        unmatched_activities = get_unmatched_activities(limit=BATCH_SIZE)
        
        if not unmatched_activities:
            print("No unmatched activities found")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "No unmatched activities found",
                    "processed": 0
                })
            }
        
        print(f"Found {len(unmatched_activities)} unmatched activities")
        
        # Invoke match_activity_trail for each activity
        # Note: These are async invocations - they queue the work but don't wait for completion
        queued_count = 0
        failed_to_queue_count = 0
        
        for activity in unmatched_activities:
            activity_id = activity["id"]
            if invoke_match_activity(activity_id):
                queued_count += 1
            else:
                failed_to_queue_count += 1
        
        print(f"Queued matching for {queued_count} activities ({failed_to_queue_count} failed to queue)")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Queued matching for {queued_count} activities (async - check database for actual results)",
                "total_found": len(unmatched_activities),
                "queued": queued_count,
                "failed_to_queue": failed_to_queue_count
            })
        }
        
    except Exception as e:
        print(f"Error in match_unmatched_activities handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error"})
        }
