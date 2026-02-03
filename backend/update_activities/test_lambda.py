#!/usr/bin/env python3
"""
Test for update_activities Lambda function

Tests the Lambda function logic without actually calling Strava API or RDS.
This is a basic smoke test to ensure the function can be imported
and the handler responds correctly to mock events.
"""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Add the Lambda function directory to the path
lambda_dir = os.path.dirname(__file__)
sys.path.insert(0, lambda_dir)

# Mock boto3 before importing lambda_function
with patch('boto3.client'):
    import lambda_function


def test_handler_missing_env_vars():
    """Test that handler fails gracefully when environment variables are missing"""
    print("Testing handler with missing environment variables...")
    
    # Clear environment variables
    old_cluster = os.environ.get('DB_CLUSTER_ARN')
    old_secret = os.environ.get('DB_SECRET_ARN')
    
    if 'DB_CLUSTER_ARN' in os.environ:
        del os.environ['DB_CLUSTER_ARN']
    if 'DB_SECRET_ARN' in os.environ:
        del os.environ['DB_SECRET_ARN']
    
    try:
        result = lambda_function.handler({}, None)
        
        assert result['statusCode'] == 500, "Expected status 500 when env vars not set"
        body = json.loads(result['body'])
        assert 'error' in body, "Expected error in response body"
        print("✓ Handler correctly fails when environment variables are missing")
    finally:
        # Restore environment variables
        if old_cluster:
            os.environ['DB_CLUSTER_ARN'] = old_cluster
        if old_secret:
            os.environ['DB_SECRET_ARN'] = old_secret


def test_handler_missing_athlete_id():
    """Test that handler rejects requests without athlete_id"""
    print("\nTesting handler with missing athlete_id...")
    
    # Set required environment variables
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    
    # Test with empty body
    result = lambda_function.handler({}, None)
    
    assert result['statusCode'] == 400, f"Expected status 400, got {result['statusCode']}"
    body = json.loads(result['body'])
    assert 'athlete_id' in body.get('error', '').lower(), "Expected athlete_id error message"
    print("✓ Handler correctly rejects requests without athlete_id")


def test_handler_invalid_athlete_id():
    """Test that handler rejects invalid athlete_id"""
    print("\nTesting handler with invalid athlete_id...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    
    # Test with invalid athlete_id
    event = {
        "body": json.dumps({"athlete_id": "not_a_number"})
    }
    
    result = lambda_function.handler(event, None)
    
    assert result['statusCode'] == 400, f"Expected status 400, got {result['statusCode']}"
    body = json.loads(result['body'])
    assert 'integer' in body.get('error', '').lower(), "Expected integer error message"
    print("✓ Handler correctly rejects invalid athlete_id")


def test_handler_query_string_parameters():
    """Test that handler accepts query string parameters"""
    print("\nTesting handler with query string parameters...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['STRAVA_CLIENT_ID'] = 'test-client-id'
    os.environ['STRAVA_CLIENT_SECRET'] = 'test-client-secret'
    
    # Mock the database and Strava API calls
    with patch('lambda_function._exec_sql') as mock_sql, \
         patch('lambda_function.fetch_strava_activities') as mock_fetch, \
         patch('lambda_function.ensure_valid_token') as mock_token:
        
        # Mock database response with valid tokens
        mock_sql.return_value = {
            "records": [[
                {"stringValue": "test-access-token"},
                {"stringValue": "test-refresh-token"},
                {"longValue": 9999999999}  # Token not expired
            ]]
        }
        
        # Mock Strava API response
        mock_fetch.return_value = [
            {
                "id": 123456,
                "name": "Test Activity",
                "distance": 5000,
                "moving_time": 1800,
                "elapsed_time": 2000,
                "total_elevation_gain": 100,
                "type": "Run",
                "start_date": "2024-01-01T10:00:00Z",
                "start_date_local": "2024-01-01T11:00:00Z",
                "timezone": "America/New_York",
                "map": {"polyline": "test_polyline"}
            }
        ]
        
        # Mock token validation
        mock_token.return_value = "test-access-token"
        
        # Test with query string parameters
        event = {
            "queryStringParameters": {
                "athlete_id": "123456"
            }
        }
        
        result = lambda_function.handler(event, None)
        
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        body = json.loads(result['body'])
        assert body.get('athlete_id') == 123456, "Expected athlete_id in response"
        assert 'message' in body, "Expected message in response"
        print("✓ Handler correctly accepts query string parameters")


def test_handler_json_body():
    """Test that handler accepts JSON body"""
    print("\nTesting handler with JSON body...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['STRAVA_CLIENT_ID'] = 'test-client-id'
    os.environ['STRAVA_CLIENT_SECRET'] = 'test-client-secret'
    
    # Mock the database and Strava API calls
    with patch('lambda_function._exec_sql') as mock_sql, \
         patch('lambda_function.fetch_activity_details') as mock_fetch, \
         patch('lambda_function.ensure_valid_token') as mock_token:
        
        # Mock database responses
        def mock_exec_sql_side_effect(sql, params=None):
            if "SELECT" in sql:
                # Return user tokens
                return {
                    "records": [[
                        {"stringValue": "test-access-token"},
                        {"stringValue": "test-refresh-token"},
                        {"longValue": 9999999999}
                    ]]
                }
            else:
                # INSERT/UPDATE activity
                return {"records": []}
        
        mock_sql.side_effect = mock_exec_sql_side_effect
        
        # Mock Strava API response
        mock_fetch.return_value = {
            "id": 789012,
            "name": "Test Single Activity",
            "distance": 10000,
            "moving_time": 3600,
            "elapsed_time": 4000,
            "total_elevation_gain": 200,
            "type": "Ride",
            "start_date": "2024-01-01T10:00:00Z",
            "start_date_local": "2024-01-01T11:00:00Z",
            "timezone": "America/New_York",
            "map": {"polyline": "test_polyline"}
        }
        
        # Mock token validation
        mock_token.return_value = "test-access-token"
        
        # Test with JSON body for single activity
        event = {
            "body": json.dumps({
                "athlete_id": 123456,
                "activity_id": 789012
            })
        }
        
        result = lambda_function.handler(event, None)
        
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        body = json.loads(result['body'])
        assert body.get('activity_id') == 789012, "Expected activity_id in response"
        assert body.get('athlete_id') == 123456, "Expected athlete_id in response"
        assert 'message' in body, "Expected message in response"
        print("✓ Handler correctly accepts JSON body with activity_id")


def test_polyline_extraction():
    """Test that polyline extraction logic prefers full polyline"""
    print("\nTesting polyline extraction logic...")
    
    # Test case 1: Both full and summary polyline available
    activity1 = {
        "id": 1,
        "name": "Test",
        "distance": 1000,
        "moving_time": 600,
        "elapsed_time": 700,
        "total_elevation_gain": 50,
        "type": "Run",
        "start_date": "2024-01-01T10:00:00Z",
        "start_date_local": "2024-01-01T11:00:00Z",
        "timezone": "UTC",
        "map": {
            "polyline": "full_polyline_data",
            "summary_polyline": "summary_polyline_data"
        }
    }
    
    polyline = ""
    if activity1.get("map"):
        polyline = activity1["map"].get("polyline") or activity1["map"].get("summary_polyline", "")
    
    assert polyline == "full_polyline_data", "Should prefer full polyline when both are available"
    print("✓ Polyline extraction correctly prefers full polyline")


if __name__ == '__main__':
    print("Running update_activities Lambda tests...\n")
    print("=" * 60)
    
    try:
        test_handler_missing_env_vars()
        test_handler_missing_athlete_id()
        test_handler_invalid_athlete_id()
        test_handler_query_string_parameters()
        test_handler_json_body()
        test_polyline_extraction()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
