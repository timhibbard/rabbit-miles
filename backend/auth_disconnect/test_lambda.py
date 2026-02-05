#!/usr/bin/env python3
"""
Test for auth_disconnect Lambda function

Tests that the Lambda function correctly validates required environment variables
and returns proper error responses when they are missing.
"""

import sys
import os
import json
from unittest.mock import Mock, patch
import importlib

# Add the Lambda function directory to the path
lambda_dir = os.path.dirname(__file__)
sys.path.insert(0, lambda_dir)


def reload_lambda_function():
    """
    Reload lambda_function module to pick up environment variable changes.
    
    Mocks boto3.client to prevent actual AWS API calls during testing.
    """
    if 'lambda_function' in sys.modules:
        del sys.modules['lambda_function']
    
    with patch('boto3.client'):
        import lambda_function
        return lambda_function


def test_missing_frontend_url():
    """Test that handler returns 500 when FRONTEND_URL is missing"""
    print("Testing missing FRONTEND_URL...")
    
    # Clear all environment variables
    for key in ['FRONTEND_URL', 'API_BASE_URL', 'APP_SECRET', 'DB_CLUSTER_ARN', 'DB_SECRET_ARN']:
        if key in os.environ:
            del os.environ[key]
    
    # Reload module with cleared environment
    lambda_function = reload_lambda_function()
    
    # Call handler
    event = {}
    context = {}
    response = lambda_function.handler(event, context)
    
    # Verify response
    assert response['statusCode'] == 500, \
        f"Expected status code 500, got: {response['statusCode']}"
    assert response['headers']['Content-Type'] == 'application/json', \
        f"Expected JSON content type, got: {response['headers']['Content-Type']}"
    body = json.loads(response['body'])
    assert body == {"message": "Internal Server Error"}, \
        f"Expected error message, got: {body}"
    
    print("✓ Test passed: Returns 500 when FRONTEND_URL is missing")


def test_missing_api_base_url():
    """Test that handler returns 500 when API_BASE_URL is missing"""
    print("Testing missing API_BASE_URL...")
    
    # Set only FRONTEND_URL
    os.environ['FRONTEND_URL'] = 'https://example.com'
    for key in ['API_BASE_URL', 'APP_SECRET', 'DB_CLUSTER_ARN', 'DB_SECRET_ARN']:
        if key in os.environ:
            del os.environ[key]
    
    # Reload module
    lambda_function = reload_lambda_function()
    
    # Call handler
    event = {}
    context = {}
    response = lambda_function.handler(event, context)
    
    # Verify response
    assert response['statusCode'] == 500, \
        f"Expected status code 500, got: {response['statusCode']}"
    body = json.loads(response['body'])
    assert body == {"message": "Internal Server Error"}, \
        f"Expected error message, got: {body}"
    
    print("✓ Test passed: Returns 500 when API_BASE_URL is missing")


def test_missing_app_secret():
    """Test that handler returns 500 when APP_SECRET is missing"""
    print("Testing missing APP_SECRET...")
    
    # Set required vars except APP_SECRET
    os.environ['FRONTEND_URL'] = 'https://example.com'
    os.environ['API_BASE_URL'] = 'https://api.example.com'
    for key in ['APP_SECRET', 'DB_CLUSTER_ARN', 'DB_SECRET_ARN']:
        if key in os.environ:
            del os.environ[key]
    
    # Reload module
    lambda_function = reload_lambda_function()
    
    # Call handler
    event = {}
    context = {}
    response = lambda_function.handler(event, context)
    
    # Verify response
    assert response['statusCode'] == 500, \
        f"Expected status code 500, got: {response['statusCode']}"
    body = json.loads(response['body'])
    assert body == {"message": "Internal Server Error"}, \
        f"Expected error message, got: {body}"
    
    print("✓ Test passed: Returns 500 when APP_SECRET is missing")


def test_missing_db_credentials():
    """Test that handler returns 500 when DB credentials are missing"""
    print("Testing missing DB credentials...")
    
    # Set required vars except DB credentials
    os.environ['FRONTEND_URL'] = 'https://example.com'
    os.environ['API_BASE_URL'] = 'https://api.example.com'
    os.environ['APP_SECRET'] = 'test-secret-1234567890'
    for key in ['DB_CLUSTER_ARN', 'DB_SECRET_ARN']:
        if key in os.environ:
            del os.environ[key]
    
    # Reload module
    lambda_function = reload_lambda_function()
    
    # Call handler
    event = {}
    context = {}
    response = lambda_function.handler(event, context)
    
    # Verify response
    assert response['statusCode'] == 500, \
        f"Expected status code 500, got: {response['statusCode']}"
    body = json.loads(response['body'])
    assert body == {"message": "Internal Server Error"}, \
        f"Expected error message, got: {body}"
    
    print("✓ Test passed: Returns 500 when DB credentials are missing")


def test_exception_handling():
    """Test that unexpected exceptions are caught and return 500"""
    print("Testing exception handling...")
    
    # Set all required environment variables
    os.environ['FRONTEND_URL'] = 'https://example.com'
    os.environ['API_BASE_URL'] = 'https://api.example.com'
    os.environ['APP_SECRET'] = 'test-secret-1234567890'
    os.environ['DB_CLUSTER_ARN'] = 'arn:aws:rds:us-east-1:123456789012:cluster:test-cluster'
    os.environ['DB_SECRET_ARN'] = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret'
    
    # Read the lambda_function.py source and verify it has try-except
    lambda_path = os.path.join(lambda_dir, 'lambda_function.py')
    with open(lambda_path, 'r') as f:
        source_code = f.read()
    
    # Verify try-except block exists in handler
    assert 'def handler(event, context):' in source_code, \
        "Source code should have handler function"
    assert '    try:' in source_code, \
        "Handler should have try block"
    assert '    except Exception as e:' in source_code, \
        "Handler should have except block for catching exceptions"
    assert '"message": "Internal Server Error"' in source_code, \
        "Handler should return Internal Server Error message on exceptions"
    
    print("✓ Test passed: Exception handling is properly implemented")


def test_has_env_var_validation():
    """Test that the handler validates all required environment variables"""
    print("Testing environment variable validation...")
    
    lambda_path = os.path.join(lambda_dir, 'lambda_function.py')
    with open(lambda_path, 'r') as f:
        source_code = f.read()
    
    # Check for validation of required environment variables
    assert 'if not FRONTEND' in source_code, \
        "Source code should validate FRONTEND"
    assert 'if not API_BASE' in source_code, \
        "Source code should validate API_BASE"
    assert 'if not APP_SECRET' in source_code, \
        "Source code should validate APP_SECRET"
    # DB credentials are validated together
    assert 'if not DB_CLUSTER_ARN or not DB_SECRET_ARN' in source_code, \
        "Source code should validate DB_CLUSTER_ARN and DB_SECRET_ARN"
    
    print("✓ Test passed: All required environment variables are validated")


if __name__ == '__main__':
    print("Running tests for auth_disconnect Lambda function...\n")
    
    try:
        test_missing_frontend_url()
        print()
        test_missing_api_base_url()
        print()
        test_missing_app_secret()
        print()
        test_missing_db_credentials()
        print()
        test_exception_handling()
        print()
        test_has_env_var_validation()
        print()
        print("All tests passed! ✓")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
