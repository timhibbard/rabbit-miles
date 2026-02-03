#!/usr/bin/env python3
"""
Simple test for update_trail_data Lambda function

Tests the Lambda function logic without actually uploading to S3.
This is a basic smoke test to ensure the function can be imported
and the handler responds correctly to mock events.
"""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Add the Lambda function directory to the path
lambda_dir = os.path.join(os.path.dirname(__file__), '..', 'update_trail_data')
sys.path.insert(0, lambda_dir)

import lambda_function


def test_handler_missing_bucket():
    """Test that handler fails gracefully when TRAIL_DATA_BUCKET is not set"""
    print("Testing handler with missing TRAIL_DATA_BUCKET...")
    
    # Clear environment variable
    if 'TRAIL_DATA_BUCKET' in os.environ:
        del os.environ['TRAIL_DATA_BUCKET']
    
    result = lambda_function.handler({}, None)
    
    assert result['statusCode'] == 500, "Expected status 500 when bucket not set"
    body = json.loads(result['body'])
    assert 'error' in body, "Expected error in response body"
    print("✓ Handler correctly fails when TRAIL_DATA_BUCKET is missing")


def test_handler_with_mock_s3():
    """Test handler with mocked S3 and URL downloads"""
    print("\nTesting handler with mocked S3 and downloads...")
    
    # Set environment variable
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    # Mock data
    mock_main_data = b'{"type": "FeatureCollection", "features": []}'
    mock_spurs_data = b'{"type": "FeatureCollection", "features": []}'
    
    # Mock the download and upload functions
    with patch('lambda_function.download_geojson') as mock_download, \
         patch('lambda_function.upload_to_s3') as mock_upload:
        
        # Configure mocks
        mock_download.side_effect = [mock_main_data, mock_spurs_data]
        
        # Call handler
        result = lambda_function.handler({}, None)
        
        # Verify response
        assert result['statusCode'] == 200, f"Expected status 200, got {result['statusCode']}"
        body = json.loads(result['body'])
        assert body['message'] == "All trail data updated successfully", "Expected success message"
        assert body['results']['main_trail']['status'] == 'success', "Main trail should succeed"
        assert body['results']['spurs_trail']['status'] == 'success', "Spurs trail should succeed"
        
        # Verify mocks were called correctly
        assert mock_download.call_count == 2, "Should download both trails"
        assert mock_upload.call_count == 2, "Should upload both trails"
        
        print("✓ Handler successfully processes both trails with mocked S3")


def test_handler_partial_failure():
    """Test handler when one trail fails"""
    print("\nTesting handler with partial failure...")
    
    os.environ['TRAIL_DATA_BUCKET'] = 'test-bucket'
    
    mock_main_data = b'{"type": "FeatureCollection", "features": []}'
    
    with patch('lambda_function.download_geojson') as mock_download, \
         patch('lambda_function.upload_to_s3') as mock_upload:
        
        # First download succeeds, second fails
        mock_download.side_effect = [mock_main_data, Exception("Network error")]
        
        result = lambda_function.handler({}, None)
        
        # Should return 207 Multi-Status
        assert result['statusCode'] == 207, f"Expected status 207, got {result['statusCode']}"
        body = json.loads(result['body'])
        assert body['message'] == "Trail data partially updated"
        assert body['results']['main_trail']['status'] == 'success'
        assert body['results']['spurs_trail']['status'] == 'error'
        
        print("✓ Handler correctly handles partial failure")


def test_download_function():
    """Test the download_geojson function with mock"""
    print("\nTesting download_geojson function...")
    
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b'test data'
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    
    with patch('urllib.request.urlopen', return_value=mock_response):
        data = lambda_function.download_geojson('http://example.com/test.json')
        assert data == b'test data', "Should return downloaded data"
        print("✓ download_geojson works correctly")


def test_upload_function():
    """Test the upload_to_s3 function with mock"""
    print("\nTesting upload_to_s3 function...")
    
    with patch('lambda_function.s3_client') as mock_s3:
        lambda_function.upload_to_s3('test-bucket', 'test-key', b'test data')
        
        # Verify put_object was called
        assert mock_s3.put_object.called, "Should call put_object"
        call_args = mock_s3.put_object.call_args
        assert call_args[1]['Bucket'] == 'test-bucket'
        assert call_args[1]['Key'] == 'test-key'
        assert call_args[1]['Body'] == b'test data'
        
        print("✓ upload_to_s3 works correctly")


if __name__ == '__main__':
    print("Running update_trail_data Lambda tests...\n")
    print("=" * 60)
    
    try:
        test_handler_missing_bucket()
        test_handler_with_mock_s3()
        test_handler_partial_failure()
        test_download_function()
        test_upload_function()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
