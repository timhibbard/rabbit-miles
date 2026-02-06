"""
Backfill athlete_count for existing activities.

This Lambda function fetches activities from Strava API that are already
stored in the database but missing the athlete_count field, and updates
them with the correct value from Strava.

It can be triggered manually or via a schedule to ensure all activities
have the athlete_count field populated.
"""

import json
import os
import boto3
from urllib.request import Request, urlopen
from botocore.exceptions import ClientError


# Environment variables
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
DB_NAME = os.environ.get("DB_NAME", "postgres")
STRAVA_API_BASE = "https://www.strava.com/api/v3"

rds_client = boto3.client("rds-data")


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
    
    try:
        response = rds_client.execute_statement(**kwargs)
        return response
    except ClientError as e:
        print(f"Database error: {e}")
        raise


def get_user_tokens():
    """Get all users with valid access tokens"""
    sql = """
    SELECT athlete_id, access_token, refresh_token
    FROM users
    WHERE access_token IS NOT NULL
    """
    
    result = _exec_sql(sql)
    users = []
    
    for record in result.get("records", []):
        athlete_id = record[0].get("longValue")
        access_token = record[1].get("stringValue")
        refresh_token = record[2].get("stringValue")
        
        if athlete_id and access_token:
            users.append({
                "athlete_id": athlete_id,
                "access_token": access_token,
                "refresh_token": refresh_token
            })
    
    return users


def get_activities_missing_athlete_count(athlete_id, limit=100):
    """Get all activities to update athlete_count from Strava API"""
    sql = """
    SELECT strava_activity_id
    FROM activities
    WHERE athlete_id = :aid
    ORDER BY start_date DESC
    LIMIT :limit
    """
    
    params = [
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "limit", "value": {"longValue": limit}},
    ]
    
    result = _exec_sql(sql, params)
    
    activity_ids = []
    for record in result.get("records", []):
        strava_id = record[0].get("longValue")
        if strava_id:
            activity_ids.append(strava_id)
    
    return activity_ids


def fetch_activity_from_strava(access_token, activity_id):
    """Fetch a single activity detail from Strava API"""
    url = f"{STRAVA_API_BASE}/activities/{activity_id}"
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    try:
        with urlopen(req, timeout=10) as resp:
            activity = json.loads(resp.read().decode())
            return activity
    except Exception as e:
        print(f"Failed to fetch activity {activity_id} from Strava: {e}")
        return None


def update_activity_athlete_count(athlete_id, strava_activity_id, athlete_count):
    """Update athlete_count for a specific activity"""
    sql = """
    UPDATE activities
    SET athlete_count = :ac, updated_at = now()
    WHERE athlete_id = :aid AND strava_activity_id = :sid
    """
    
    params = [
        {"name": "ac", "value": {"longValue": athlete_count}},
        {"name": "aid", "value": {"longValue": athlete_id}},
        {"name": "sid", "value": {"longValue": strava_activity_id}},
    ]
    
    try:
        _exec_sql(sql, params)
        return True
    except Exception as e:
        print(f"Failed to update activity {strava_activity_id}: {e}")
        return False


def handler(event, context):
    """
    Lambda handler for backfilling athlete_count.
    
    Can be invoked in two modes:
    1. Batch mode (default): Process all users and their activities
    2. Single user mode: Pass athlete_id in event to process only that user
    """
    
    try:
        # Check if processing a single user
        athlete_id = event.get("athlete_id") if event else None
        
        if athlete_id:
            # Single user mode
            users = [{"athlete_id": athlete_id}]
            # Need to fetch token for this user
            sql = "SELECT access_token FROM users WHERE athlete_id = :aid"
            result = _exec_sql(sql, [{"name": "aid", "value": {"longValue": athlete_id}}])
            if result.get("records"):
                users[0]["access_token"] = result["records"][0][0].get("stringValue")
            else:
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": f"User {athlete_id} not found"})
                }
        else:
            # Batch mode - get all users
            users = get_user_tokens()
        
        total_processed = 0
        total_updated = 0
        
        for user in users:
            athlete_id = user["athlete_id"]
            access_token = user["access_token"]
            
            if not access_token:
                print(f"No access token for athlete {athlete_id}, skipping")
                continue
            
            print(f"Processing athlete {athlete_id}")
            
            # Get activities missing athlete_count
            activity_ids = get_activities_missing_athlete_count(athlete_id)
            print(f"Found {len(activity_ids)} activities to process for athlete {athlete_id}")
            
            for strava_activity_id in activity_ids:
                total_processed += 1
                
                # Fetch activity details from Strava
                activity = fetch_activity_from_strava(access_token, strava_activity_id)
                
                if activity:
                    athlete_count = activity.get("athlete_count", 1)
                    
                    # Update database
                    if update_activity_athlete_count(athlete_id, strava_activity_id, athlete_count):
                        total_updated += 1
                        print(f"Updated activity {strava_activity_id} with athlete_count={athlete_count}")
                    else:
                        print(f"Failed to update activity {strava_activity_id}")
                else:
                    print(f"Could not fetch activity {strava_activity_id} from Strava")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Backfill completed",
                "users_processed": len(users),
                "activities_processed": total_processed,
                "activities_updated": total_updated,
            })
        }
    
    except Exception as e:
        print(f"Error during backfill: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
