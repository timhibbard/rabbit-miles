#!/usr/bin/env python3
"""
Test for reset_last_matched Lambda function

Tests that the Lambda function correctly uses MATCH_ACTIVITY_LAMBDA_ARN
environment variable for invoking the match_activity_trail Lambda.
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


def test_env_var_name():
    """Test that the function uses MATCH_ACTIVITY_LAMBDA_ARN environment variable"""
    print("Testing that MATCH_ACTIVITY_LAMBDA_ARN is used...")
    
    # Set up test environment
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['APP_SECRET'] = 'test-secret'
    os.environ['FRONTEND_URL'] = 'https://example.com'
    
    # Reload module with test environment
    lambda_function = reload_lambda_function()
    
    # Verify the correct environment variable is used
    assert hasattr(lambda_function, 'MATCH_ACTIVITY_LAMBDA_ARN'), \
        "Module should have MATCH_ACTIVITY_LAMBDA_ARN variable"
    assert lambda_function.MATCH_ACTIVITY_LAMBDA_ARN == 'arn:aws:lambda:us-east-1:123456789012:function:test-function', \
        f"MATCH_ACTIVITY_LAMBDA_ARN should match env var, got: {lambda_function.MATCH_ACTIVITY_LAMBDA_ARN}"
    
    # Verify the old variable name is not used
    assert not hasattr(lambda_function, 'MATCH_ACTIVITY_TRAIL_LAMBDA'), \
        "Module should NOT have MATCH_ACTIVITY_TRAIL_LAMBDA variable"
    
    print("✓ Test passed: MATCH_ACTIVITY_LAMBDA_ARN is correctly used")


def test_lambda_invocation_uses_arn():
    """Test that lambda invocation uses the ARN from MATCH_ACTIVITY_LAMBDA_ARN"""
    print("Testing lambda invocation uses MATCH_ACTIVITY_LAMBDA_ARN...")
    
    # Set up test environment
    test_arn = 'arn:aws:lambda:us-east-1:123456789012:function:match-trail'
    os.environ['MATCH_ACTIVITY_LAMBDA_ARN'] = test_arn
    os.environ['DB_CLUSTER_ARN'] = 'test-cluster-arn'
    os.environ['DB_SECRET_ARN'] = 'test-secret-arn'
    os.environ['APP_SECRET'] = 'test-secret'
    os.environ['FRONTEND_URL'] = 'https://example.com'
    
    # Read the lambda_function.py source and verify it uses MATCH_ACTIVITY_LAMBDA_ARN
    lambda_path = os.path.join(lambda_dir, 'lambda_function.py')
    with open(lambda_path, 'r') as f:
        source_code = f.read()
    
    # Check that MATCH_ACTIVITY_LAMBDA_ARN is defined
    assert 'MATCH_ACTIVITY_LAMBDA_ARN' in source_code, \
        "Source code should define MATCH_ACTIVITY_LAMBDA_ARN"
    assert 'os.environ.get("MATCH_ACTIVITY_LAMBDA_ARN"' in source_code, \
        "Source code should read MATCH_ACTIVITY_LAMBDA_ARN from environment"
    
    # Check that FunctionName=MATCH_ACTIVITY_LAMBDA_ARN is used in invoke call
    assert 'FunctionName=MATCH_ACTIVITY_LAMBDA_ARN' in source_code, \
        "Source code should use FunctionName=MATCH_ACTIVITY_LAMBDA_ARN in lambda invoke"
    
    # Check that the old variable name is not used
    assert 'MATCH_ACTIVITY_TRAIL_LAMBDA' not in source_code, \
        "Source code should NOT contain MATCH_ACTIVITY_TRAIL_LAMBDA"
    
    # Check that there's a conditional check for MATCH_ACTIVITY_LAMBDA_ARN
    assert 'if MATCH_ACTIVITY_LAMBDA_ARN:' in source_code, \
        "Source code should check if MATCH_ACTIVITY_LAMBDA_ARN is set before invoking"
    
    print("✓ Test passed: Lambda invocation correctly uses MATCH_ACTIVITY_LAMBDA_ARN")


def test_matches_pattern_from_other_lambdas():
    """Test that the pattern matches other Lambda functions (match_unmatched_activities, webhook_processor)"""
    print("Testing that pattern matches other Lambda functions...")
    
    # Read reset_last_matched source
    reset_path = os.path.join(lambda_dir, 'lambda_function.py')
    with open(reset_path, 'r') as f:
        reset_source = f.read()
    
    # Read match_unmatched_activities source
    match_unmatched_path = os.path.join(lambda_dir, '..', 'match_unmatched_activities', 'lambda_function.py')
    with open(match_unmatched_path, 'r') as f:
        match_unmatched_source = f.read()
    
    # Verify both use the same environment variable name
    assert 'MATCH_ACTIVITY_LAMBDA_ARN = os.environ.get("MATCH_ACTIVITY_LAMBDA_ARN"' in reset_source, \
        "reset_last_matched should use MATCH_ACTIVITY_LAMBDA_ARN"
    assert 'MATCH_ACTIVITY_LAMBDA_ARN = os.environ.get("MATCH_ACTIVITY_LAMBDA_ARN"' in match_unmatched_source, \
        "match_unmatched_activities should use MATCH_ACTIVITY_LAMBDA_ARN"
    
    # Verify both use FunctionName=MATCH_ACTIVITY_LAMBDA_ARN
    assert 'FunctionName=MATCH_ACTIVITY_LAMBDA_ARN' in reset_source, \
        "reset_last_matched should use FunctionName=MATCH_ACTIVITY_LAMBDA_ARN"
    assert 'FunctionName=MATCH_ACTIVITY_LAMBDA_ARN' in match_unmatched_source, \
        "match_unmatched_activities should use FunctionName=MATCH_ACTIVITY_LAMBDA_ARN"
    
    print("✓ Test passed: Pattern matches other Lambda functions")


if __name__ == '__main__':
    print("Running tests for reset_last_matched Lambda function...\n")
    
    try:
        test_env_var_name()
        print()
        test_lambda_invocation_uses_arn()
        print()
        test_matches_pattern_from_other_lambdas()
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

