#!/usr/bin/env python3
"""
Test for admin_all_activities Lambda function

Tests the fetch all activities functionality with proper authentication and authorization.
"""

import sys
import os
import json
import time
import base64
import hmac
import hashlib
from unittest.mock import Mock, MagicMock, patch

# Set up environment before importing Lambda
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["DB_CLUSTER_ARN"] = "test-arn"
os.environ["DB_SECRET_ARN"] = "test-secret-arn"
os.environ["DB_NAME"] = "postgres"
os.environ["APP_SECRET"] = "test_secret"
os.environ["FRONTEND_URL"] = "https://example.com"
os.environ["ADMIN_ATHLETE_IDS"] = "12345"

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

# Import the Lambda function
sys.path.insert(0, os.path.join(backend_dir, 'admin_all_activities'))
import lambda_function


def create_session_token(athlete_id, app_secret):
    """Helper to create a valid session token"""
    exp = int(time.time()) + 3600
    data = {"aid": athlete_id, "exp": exp}
    b64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    signature = hmac.new(app_secret, b64_data.encode(), hashlib.sha256).hexdigest()
    return f"{b64_data}.{signature}"


def test_all_activities_success():
    """Test successful fetching of all activities"""
    print("Testing successful fetching of all activities...")
    
    app_secret = b"test_secret"
    admin_id = 12345
    
    # Create session token
    token = create_session_token(admin_id, app_secret)
    
    # Mock event
    event = {
        "requestContext": {
            "http": {
                "method": "GET"
            }
        },
        "cookies": [f"rm_session={token}"],
        "queryStringParameters": {
            "limit": "50",
            "offset": "0"
        }
    }
    
    # Mock RDS client
    mock_rds = MagicMock()
    
    # Mock activities query response
    mock_rds.execute_statement.side_effect = [
        # First call - get activities
        {
            "records": [
                [
                    {"longValue": 1},  # id
                    {"longValue": 12345},  # athlete_id
                    {"longValue": 98765},  # strava_activity_id
                    {"stringValue": "Morning Run"},  # name
                    {"doubleValue": 5000.0},  # distance
                    {"longValue": 1800},  # moving_time
                    {"longValue": 2000},  # elapsed_time
                    {"doubleValue": 100.0},  # total_elevation_gain
                    {"stringValue": "Run"},  # type
                    {"stringValue": "2026-02-01T08:00:00Z"},  # start_date
                    {"stringValue": "2026-02-01T08:00:00Z"},  # start_date_local
                    {"stringValue": "2026-02-01T08:00:00Z"},  # created_at
                    {"stringValue": "2026-02-01T08:00:00Z"},  # updated_at
                    {"isNull": True},  # time_on_trail
                    {"isNull": True},  # distance_on_trail
                    {"stringValue": "Test User"},  # athlete_name
                ]
            ]
        },
        # Second call - get total count
        {
            "records": [
                [{"longValue": 1}]
            ]
        }
    ]
    
    context = {}
    
    # Patch boto3 client
    with patch('lambda_function.rds', mock_rds):
        response = lambda_function.handler(event, context)
    
    # Verify response
    assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}"
    
    body = json.loads(response["body"])
    assert len(body["activities"]) == 1, f"Expected 1 activity, got {len(body['activities'])}"
    assert body["activities"][0]["name"] == "Morning Run"
    assert body["activities"][0]["athlete_name"] == "Test User"
    assert body["total_count"] == 1
    
    print("✓ Test passed: Successfully fetched all activities")


def test_all_activities_unauthorized():
    """Test unauthorized access (non-admin user)"""
    print("Testing unauthorized access...")
    
    app_secret = b"test_secret"
    non_admin_id = 99999  # Not in ADMIN_ATHLETE_IDS
    
    # Create session token for non-admin
    token = create_session_token(non_admin_id, app_secret)
    
    # Mock event
    event = {
        "requestContext": {
            "http": {
                "method": "GET"
            }
        },
        "cookies": [f"rm_session={token}"],
        "queryStringParameters": {}
    }
    
    context = {}
    
    # Mock RDS client
    mock_rds = MagicMock()
    
    with patch('lambda_function.rds', mock_rds):
        response = lambda_function.handler(event, context)
    
    # Verify response
    assert response["statusCode"] == 403, f"Expected 403, got {response['statusCode']}"
    
    body = json.loads(response["body"])
    assert body["error"] == "forbidden"
    
    print("✓ Test passed: Unauthorized access properly rejected")


def test_all_activities_not_authenticated():
    """Test unauthenticated access"""
    print("Testing unauthenticated access...")
    
    # Mock event without session cookie
    event = {
        "requestContext": {
            "http": {
                "method": "GET"
            }
        },
        "cookies": [],
        "queryStringParameters": {}
    }
    
    context = {}
    
    # Mock RDS client
    mock_rds = MagicMock()
    
    with patch('lambda_function.rds', mock_rds):
        response = lambda_function.handler(event, context)
    
    # Verify response
    assert response["statusCode"] == 401, f"Expected 401, got {response['statusCode']}"
    
    body = json.loads(response["body"])
    assert body["error"] == "not authenticated"
    
    print("✓ Test passed: Unauthenticated access properly rejected")


def test_all_activities_from_multiple_users():
    """Test that activities from multiple users are returned (not filtered to admin only)"""
    print("Testing that activities from multiple users are returned...")
    
    app_secret = b"test_secret"
    admin_id = 12345  # The admin user
    
    # Create session token
    token = create_session_token(admin_id, app_secret)
    
    # Mock event
    event = {
        "requestContext": {
            "http": {
                "method": "GET"
            }
        },
        "cookies": [f"rm_session={token}"],
        "queryStringParameters": {
            "limit": "50",
            "offset": "0"
        }
    }
    
    # Mock RDS client
    mock_rds = MagicMock()
    
    # Mock activities query response with activities from DIFFERENT users (not just admin)
    mock_rds.execute_statement.side_effect = [
        # First call - get activities from multiple users
        {
            "records": [
                [
                    {"longValue": 1},  # id
                    {"longValue": 99999},  # athlete_id - DIFFERENT USER (not admin 12345)
                    {"longValue": 11111},  # strava_activity_id
                    {"stringValue": "User 1 Run"},  # name
                    {"doubleValue": 5000.0},  # distance
                    {"longValue": 1800},  # moving_time
                    {"longValue": 2000},  # elapsed_time
                    {"doubleValue": 100.0},  # total_elevation_gain
                    {"stringValue": "Run"},  # type
                    {"stringValue": "2026-02-09T10:00:00Z"},  # start_date
                    {"stringValue": "2026-02-09T10:00:00Z"},  # start_date_local
                    {"stringValue": "2026-02-09T10:00:00Z"},  # created_at
                    {"stringValue": "2026-02-09T10:00:00Z"},  # updated_at
                    {"isNull": True},  # time_on_trail
                    {"isNull": True},  # distance_on_trail
                    {"stringValue": "Alice Runner"},  # athlete_name
                ],
                [
                    {"longValue": 2},  # id
                    {"longValue": 88888},  # athlete_id - ANOTHER DIFFERENT USER
                    {"longValue": 22222},  # strava_activity_id
                    {"stringValue": "User 2 Ride"},  # name
                    {"doubleValue": 25000.0},  # distance
                    {"longValue": 3600},  # moving_time
                    {"longValue": 4000},  # elapsed_time
                    {"doubleValue": 300.0},  # total_elevation_gain
                    {"stringValue": "Ride"},  # type
                    {"stringValue": "2026-02-09T09:00:00Z"},  # start_date
                    {"stringValue": "2026-02-09T09:00:00Z"},  # start_date_local
                    {"stringValue": "2026-02-09T09:00:00Z"},  # created_at
                    {"stringValue": "2026-02-09T09:00:00Z"},  # updated_at
                    {"isNull": True},  # time_on_trail
                    {"isNull": True},  # distance_on_trail
                    {"stringValue": "Bob Cyclist"},  # athlete_name
                ],
                [
                    {"longValue": 3},  # id
                    {"longValue": 12345},  # athlete_id - THIS IS THE ADMIN
                    {"longValue": 33333},  # strava_activity_id
                    {"stringValue": "Admin Run"},  # name
                    {"doubleValue": 10000.0},  # distance
                    {"longValue": 3000},  # moving_time
                    {"longValue": 3200},  # elapsed_time
                    {"doubleValue": 200.0},  # total_elevation_gain
                    {"stringValue": "Run"},  # type
                    {"stringValue": "2026-02-09T08:00:00Z"},  # start_date
                    {"stringValue": "2026-02-09T08:00:00Z"},  # start_date_local
                    {"stringValue": "2026-02-09T08:00:00Z"},  # created_at
                    {"stringValue": "2026-02-09T08:00:00Z"},  # updated_at
                    {"isNull": True},  # time_on_trail
                    {"isNull": True},  # distance_on_trail
                    {"stringValue": "Admin User"},  # athlete_name
                ]
            ]
        },
        # Second call - get total count
        {
            "records": [
                [{"longValue": 3}]
            ]
        }
    ]
    
    context = {}
    
    # Patch boto3 client
    with patch('lambda_function.rds', mock_rds):
        response = lambda_function.handler(event, context)
    
    # Verify response
    assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}"
    
    body = json.loads(response["body"])
    assert len(body["activities"]) == 3, f"Expected 3 activities, got {len(body['activities'])}"
    
    # Verify we have activities from different users (not just the admin)
    athlete_ids = [activity["athlete_id"] for activity in body["activities"]]
    athlete_names = [activity["athlete_name"] for activity in body["activities"]]
    
    # Check that we have activities from at least 2 different users
    unique_athlete_ids = set(athlete_ids)
    assert len(unique_athlete_ids) > 1, f"Expected activities from multiple users, but only got from: {unique_athlete_ids}"
    
    # Verify specific athletes are included
    assert 99999 in athlete_ids, "Expected activity from athlete 99999 (Alice Runner)"
    assert 88888 in athlete_ids, "Expected activity from athlete 88888 (Bob Cyclist)"  
    assert 12345 in athlete_ids, "Expected activity from athlete 12345 (Admin User)"
    
    # Verify athlete names are populated correctly
    assert "Alice Runner" in athlete_names
    assert "Bob Cyclist" in athlete_names
    assert "Admin User" in athlete_names
    
    assert body["total_count"] == 3
    
    print("✓ Test passed: Activities from multiple users returned (not filtered to admin only)")


if __name__ == "__main__":
    try:
        test_all_activities_success()
        test_all_activities_from_multiple_users()
        test_all_activities_unauthorized()
        test_all_activities_not_authenticated()
        print("\n✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
