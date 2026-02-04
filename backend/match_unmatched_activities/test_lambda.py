#!/usr/bin/env python3
"""
Test for match_unmatched_activities Lambda function

Tests the Lambda function logic without actually calling AWS services.
Verifies that the function correctly reports async invocation status.
"""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock
import importlib

# Add the Lambda function directory to the path
lambda_dir = os.path.dirname(__file__)
sys.path.insert(0, lambda_dir)


def reload_lambda_function():
    """
    Reload lambda_function module to pick up environment variable changes.
    
    Also mocks boto3.client to prevent actual AWS API calls during testing.
    This is necessary because the lambda_function module creates boto3 clients
    at the module level during import.
    """
    if 'lambda_function' in sys.modules:
        del sys.modules['lambda_function']
    
    with patch('boto3.client'):
        import lambda_function
        return lambda_function


def extract_limit_from_mock_call(mock_sql):
    """
    Helper function to extract the limit parameter from a mocked SQL call.
    
    Args:
        mock_sql: The mocked _exec_sql function
        
    Returns:
        int: The limit value used in the SQL call
    """
    call_args = mock_sql.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('parameters')
    return params[0]['value']['longValue']


def test_handler_missing_env_vars():
    """Test that handler fails gracefully when environment variables are missing"""
    print("Testing handler with missing environment variables...")
    
    # Clear environment variables
    old_cluster = os.environ.get('DB_CLUSTER_ARN')
    old_secret = os.environ.get('DB_SECRET_ARN')
    old_lambda_arn = os.environ.get('MATCH_ACTIVITY_LAMBDA_ARN')
    
    if 'DB_CLUSTER_ARN' in os.environ:
        del os.environ['DB_CLUSTER_ARN']
    if 'DB_SECRET_ARN' in os.environ:
        del os.environ['DB_SECRET_ARN']
    if 'MATCH_ACTIVITY_LAMBDA_ARN' in os.environ:
        del os.environ['MATCH_ACTIVITY_LAMBDA_ARN']
    
    try:
        lambda_function = reload_lambda_function()
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
        if old_lambda_arn:
            os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = old_lambda_arn


def test_handler_no_unmatched_activities():
    """Test that handler returns appropriate message when no unmatched activities"""
    print("\nTesting handler with no unmatched activities...")
    
    # Set required environment variables
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = 'test-lambda-arn'
    
    lambda_function = reload_lambda_function()
    
    # Mock the database query to return no activities
    with patch.object(lambda_function, '_exec_sql') as mock_sql:
        mock_sql.return_value = {"records": []}
        
        result = lambda_function.handler({}, None)
        
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        body = json.loads(result['body'])
        assert body['message'] == "No unmatched activities found", "Expected no unmatched activities message"
        assert body['processed'] == 0, "Expected processed count to be 0"
        
        # Verify the default limit of 75 was used
        assert extract_limit_from_mock_call(mock_sql) == 75, "Expected default limit of 75"
        
        print("✓ Handler correctly handles no unmatched activities")
        print("✓ Handler uses default limit of 75")


def test_handler_successful_queueing():
    """Test that handler correctly reports queued invocations"""
    print("\nTesting handler with successful async invocations...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = 'test-lambda-arn'
    
    lambda_function = reload_lambda_function()
    
    # Mock the database query to return activities
    with patch.object(lambda_function, '_exec_sql') as mock_sql, \
         patch.object(lambda_function, 'lambda_client') as mock_lambda:
        
        mock_sql.return_value = {
            "records": [
                [{"longValue": 1}, {"longValue": 100}, {"stringValue": "Activity 1"}],
                [{"longValue": 2}, {"longValue": 200}, {"stringValue": "Activity 2"}],
                [{"longValue": 3}, {"longValue": 300}, {"stringValue": "Activity 3"}]
            ]
        }
        
        # Mock successful async Lambda invocations (returns 202 status)
        mock_lambda.invoke.return_value = {"StatusCode": 202}
        
        result = lambda_function.handler({}, None)
        
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        body = json.loads(result['body'])
        
        # Verify the response structure changed from "success" to "queued"
        assert 'queued' in body, "Expected 'queued' field in response"
        assert 'failed_to_queue' in body, "Expected 'failed_to_queue' field in response"
        assert body['queued'] == 3, f"Expected 3 queued, got {body['queued']}"
        assert body['failed_to_queue'] == 0, f"Expected 0 failed to queue, got {body['failed_to_queue']}"
        assert body['total_found'] == 3, f"Expected 3 total found, got {body['total_found']}"
        
        # Verify message mentions async behavior
        assert 'async' in body['message'].lower(), "Message should mention async behavior"
        assert 'queued' in body['message'].lower(), "Message should say 'queued' not 'matched'"
        
        print("✓ Handler correctly reports queued invocations")
        print(f"  Message: {body['message']}")


def test_handler_partial_queueing_failure():
    """Test that handler correctly reports when some invocations fail"""
    print("\nTesting handler with partial queueing failures...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = 'test-lambda-arn'
    
    lambda_function = reload_lambda_function()
    
    with patch.object(lambda_function, '_exec_sql') as mock_sql, \
         patch.object(lambda_function, 'lambda_client') as mock_lambda:
        
        mock_sql.return_value = {
            "records": [
                [{"longValue": 1}, {"longValue": 100}, {"stringValue": "Activity 1"}],
                [{"longValue": 2}, {"longValue": 200}, {"stringValue": "Activity 2"}],
                [{"longValue": 3}, {"longValue": 300}, {"stringValue": "Activity 3"}]
            ]
        }
        
        # Make the second invocation fail
        call_count = 0
        def invoke_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Lambda invocation failed")
            return {"StatusCode": 202}
        
        mock_lambda.invoke.side_effect = invoke_side_effect
        
        result = lambda_function.handler({}, None)
        
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        body = json.loads(result['body'])
        
        assert body['queued'] == 2, f"Expected 2 queued, got {body['queued']}"
        assert body['failed_to_queue'] == 1, f"Expected 1 failed to queue, got {body['failed_to_queue']}"
        assert body['total_found'] == 3, f"Expected 3 total found, got {body['total_found']}"
        
        print("✓ Handler correctly tracks partial failures")


def test_response_structure_changed():
    """Test that old 'success'/'failed' fields are replaced with 'queued'/'failed_to_queue'"""
    print("\nTesting that response structure uses correct field names...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = 'test-lambda-arn'
    
    lambda_function = reload_lambda_function()
    
    with patch.object(lambda_function, '_exec_sql') as mock_sql, \
         patch.object(lambda_function, 'lambda_client') as mock_lambda:
        
        mock_sql.return_value = {
            "records": [
                [{"longValue": 1}, {"longValue": 100}, {"stringValue": "Activity 1"}]
            ]
        }
        
        mock_lambda.invoke.return_value = {"StatusCode": 202}
        
        result = lambda_function.handler({}, None)
        body = json.loads(result['body'])
        
        # Ensure old field names are NOT present
        assert 'success' not in body, "Old 'success' field should not be present"
        assert 'failed' not in body, "Old 'failed' field should not be present"
        
        # Ensure new field names ARE present
        assert 'queued' in body, "New 'queued' field should be present"
        assert 'failed_to_queue' in body, "New 'failed_to_queue' field should be present"
        
        print("✓ Response structure correctly uses 'queued' instead of 'success'")


def test_handler_custom_limit():
    """Test that handler accepts and uses custom limit parameter"""
    print("\nTesting handler with custom limit parameter...")
    
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['DB_NAME'] = 'postgres'
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = 'test-lambda-arn'
    
    lambda_function = reload_lambda_function()
    
    with patch.object(lambda_function, '_exec_sql') as mock_sql, \
         patch.object(lambda_function, 'lambda_client') as mock_lambda:
        
        # Mock database to return 5 activities
        mock_sql.return_value = {
            "records": [
                [{"longValue": i}, {"longValue": i*100}, {"stringValue": f"Activity {i}"}]
                for i in range(1, 6)
            ]
        }
        
        mock_lambda.invoke.return_value = {"StatusCode": 202}
        
        # Test with custom limit of 150
        result = lambda_function.handler({"limit": 150}, None)
        
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        
        # Verify the custom limit was used in SQL call
        assert extract_limit_from_mock_call(mock_sql) == 150, "Expected custom limit of 150"
        
        body = json.loads(result['body'])
        assert body['total_found'] == 5, f"Expected 5 activities found, got {body['total_found']}"
        assert body['queued'] == 5, f"Expected 5 queued, got {body['queued']}"
        
        print("✓ Handler correctly uses custom limit parameter (150)")
        
        # Test with custom limit of 25
        mock_sql.reset_mock()
        result = lambda_function.handler({"limit": 25}, None)
        
        # Verify the custom limit was used
        assert extract_limit_from_mock_call(mock_sql) == 25, "Expected custom limit of 25"
        
        print("✓ Handler correctly uses custom limit parameter (25)")


if __name__ == '__main__':
    print("Running match_unmatched_activities Lambda tests...\n")
    print("=" * 60)
    
    try:
        test_handler_missing_env_vars()
        test_handler_no_unmatched_activities()
        test_handler_successful_queueing()
        test_handler_partial_queueing_failure()
        test_response_structure_changed()
        test_handler_custom_limit()
        
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
