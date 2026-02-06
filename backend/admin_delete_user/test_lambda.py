#!/usr/bin/env python3
"""
Test for admin_delete_user Lambda function

Tests the delete user functionality with proper authentication and authorization.
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
sys.path.insert(0, os.path.join(backend_dir, 'admin_delete_user'))
import lambda_function


def create_session_token(athlete_id, app_secret):
    """Helper to create a valid session token"""
    exp = int(time.time()) + 3600
    data = {"aid": athlete_id, "exp": exp}
    b64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    signature = hmac.new(app_secret, b64_data.encode(), hashlib.sha256).hexdigest()
    return f"{b64_data}.{signature}"


def test_delete_user_success():
    """Test successful user deletion"""
    print("Testing successful user deletion...")
    
    app_secret = b"test_secret"
    admin_id = 12345
    target_id = 99999
    
    # Update environment
    os.environ["DB_CLUSTER_ARN"] = "arn:aws:rds:us-east-1:123456789012:cluster:test-cluster"
    os.environ["DB_SECRET_ARN"] = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret"
    os.environ["ADMIN_ATHLETE_IDS"] = str(admin_id)
    
    # Create admin token
    token = create_session_token(admin_id, app_secret)
    
    # Create event
    event = {
        "cookies": [f"rm_session={token}"],
        "headers": {},
        "requestContext": {"http": {"method": "DELETE"}},
        "pathParameters": {"athlete_id": str(target_id)}
    }
    
    # Mock RDS client
    mock_rds = MagicMock()
    
    # Mock check query (user exists)
    mock_rds.execute_statement.side_effect = [
        {"records": [[{"longValue": target_id}, {"stringValue": "Test User"}]]},  # Check user exists
        {"numberOfRecordsUpdated": 5},  # Delete activities
        {"numberOfRecordsUpdated": 1},  # Delete user
    ]
    
    # Patch the rds client instance in the lambda_function module
    with patch.object(lambda_function, 'rds', mock_rds):
        response = lambda_function.handler(event, None)
    
    # Verify response
    assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert body["success"] == True, "Expected success=True"
    assert body["deleted"]["athlete_id"] == target_id, f"Expected athlete_id {target_id}"
    assert body["deleted"]["activities_count"] == 5, "Expected 5 activities deleted"
    
    print("✓ User deleted successfully")
    print("✅ test_delete_user_success passed\n")


def test_delete_user_not_authenticated():
    """Test deletion without authentication"""
    print("Testing deletion without authentication...")
    
    # Create event without session cookie
    event = {
        "headers": {},
        "requestContext": {"http": {"method": "DELETE"}},
        "pathParameters": {"athlete_id": "99999"}
    }
    
    response = lambda_function.handler(event, None)
    
    assert response["statusCode"] == 401, f"Expected 401, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, "Expected error in response"
    
    print("✓ Unauthenticated access rejected")
    print("✅ test_delete_user_not_authenticated passed\n")


def test_delete_user_not_admin():
    """Test deletion by non-admin user"""
    print("Testing deletion by non-admin user...")
    
    app_secret = b"test_secret"
    admin_id = 12345
    user_id = 55555
    target_id = 99999
    
    os.environ["ADMIN_ATHLETE_IDS"] = str(admin_id)
    
    # Create non-admin token
    token = create_session_token(user_id, app_secret)
    
    event = {
        "cookies": [f"rm_session={token}"],
        "headers": {},
        "requestContext": {"http": {"method": "DELETE"}},
        "pathParameters": {"athlete_id": str(target_id)}
    }
    
    response = lambda_function.handler(event, None)
    
    assert response["statusCode"] == 403, f"Expected 403, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, "Expected error in response"
    
    print("✓ Non-admin access rejected")
    print("✅ test_delete_user_not_admin passed\n")


def test_delete_user_not_found():
    """Test deletion of non-existent user"""
    print("Testing deletion of non-existent user...")
    
    app_secret = b"test_secret"
    admin_id = 12345
    target_id = 99999
    
    os.environ["ADMIN_ATHLETE_IDS"] = str(admin_id)
    
    token = create_session_token(admin_id, app_secret)
    
    event = {
        "cookies": [f"rm_session={token}"],
        "headers": {},
        "requestContext": {"http": {"method": "DELETE"}},
        "pathParameters": {"athlete_id": str(target_id)}
    }
    
    # Mock RDS client - user not found
    mock_rds = MagicMock()
    mock_rds.execute_statement.return_value = {"records": []}
    
    with patch.object(lambda_function, 'rds', mock_rds):
        response = lambda_function.handler(event, None)
    
    assert response["statusCode"] == 404, f"Expected 404, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, "Expected error in response"
    
    print("✓ Non-existent user handled correctly")
    print("✅ test_delete_user_not_found passed\n")


def test_delete_invalid_athlete_id():
    """Test deletion with invalid athlete_id"""
    print("Testing deletion with invalid athlete_id...")
    
    app_secret = b"test_secret"
    admin_id = 12345
    
    os.environ["ADMIN_ATHLETE_IDS"] = str(admin_id)
    
    token = create_session_token(admin_id, app_secret)
    
    event = {
        "cookies": [f"rm_session={token}"],
        "headers": {},
        "requestContext": {"http": {"method": "DELETE"}},
        "pathParameters": {"athlete_id": "invalid"}
    }
    
    response = lambda_function.handler(event, None)
    
    assert response["statusCode"] == 400, f"Expected 400, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, "Expected error in response"
    
    print("✓ Invalid athlete_id handled correctly")
    print("✅ test_delete_invalid_athlete_id passed\n")


def test_delete_missing_athlete_id():
    """Test deletion without athlete_id parameter"""
    print("Testing deletion without athlete_id parameter...")
    
    app_secret = b"test_secret"
    admin_id = 12345
    
    os.environ["ADMIN_ATHLETE_IDS"] = str(admin_id)
    
    token = create_session_token(admin_id, app_secret)
    
    event = {
        "cookies": [f"rm_session={token}"],
        "headers": {},
        "requestContext": {"http": {"method": "DELETE"}},
        "pathParameters": {}
    }
    
    response = lambda_function.handler(event, None)
    
    assert response["statusCode"] == 400, f"Expected 400, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, "Expected error in response"
    
    print("✓ Missing athlete_id handled correctly")
    print("✅ test_delete_missing_athlete_id passed\n")


def test_options_preflight():
    """Test OPTIONS preflight request"""
    print("Testing OPTIONS preflight request...")
    
    event = {
        "headers": {},
        "requestContext": {"http": {"method": "OPTIONS"}},
        "pathParameters": {}
    }
    
    response = lambda_function.handler(event, None)
    
    assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}"
    assert "Access-Control-Allow-Methods" in response["headers"], "Expected CORS headers"
    assert "DELETE" in response["headers"]["Access-Control-Allow-Methods"], "Expected DELETE in allowed methods"
    
    print("✓ OPTIONS preflight handled correctly")
    print("✅ test_options_preflight passed\n")


if __name__ == "__main__":
    print("=" * 80)
    print("Running admin_delete_user Lambda tests")
    print("=" * 80)
    print()
    
    try:
        test_delete_user_success()
        test_delete_user_not_authenticated()
        test_delete_user_not_admin()
        test_delete_user_not_found()
        test_delete_invalid_athlete_id()
        test_delete_missing_athlete_id()
        test_options_preflight()
        
        print("=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
