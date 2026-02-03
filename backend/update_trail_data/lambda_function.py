"""
Lambda function to download trail GeoJSON data and store in S3

This function downloads the main trail and spur trail GeoJSON data
from greenvilleopenmap.info and stores them in S3. It can be invoked
on-demand to update the trail data used for activity matching.

Environment Variables:
    TRAIL_DATA_BUCKET: S3 bucket name for storing trail GeoJSON files
"""

import json
import os
import urllib.request
import urllib.error
import boto3
from datetime import datetime

# S3 client
s3_client = boto3.client('s3')

# URLs for trail data
MAIN_TRAIL_URL = "https://greenvilleopenmap.info/SwampRabbitWays.geojson"
SPURS_TRAIL_URL = "https://greenvilleopenmap.info/SwampRabbitConnectors.geojson"

# S3 keys for storing the files
MAIN_TRAIL_KEY = "trails/main.geojson"
SPURS_TRAIL_KEY = "trails/spurs.geojson"


def download_geojson(url):
    """
    Download GeoJSON data from a URL
    
    Args:
        url: URL to download from
        
    Returns:
        bytes: Downloaded data
        
    Raises:
        urllib.error.URLError: If download fails
    """
    print(f"Downloading from {url}")
    
    # Set a reasonable timeout
    timeout = 30
    
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status} error downloading from {url}")
            
            data = response.read()
            print(f"Successfully downloaded {len(data)} bytes")
            return data
            
    except urllib.error.URLError as e:
        print(f"Error downloading from {url}: {e}")
        raise


def upload_to_s3(bucket_name, key, data, content_type='application/geo+json'):
    """
    Upload data to S3
    
    Args:
        bucket_name: S3 bucket name
        key: S3 object key
        data: Data to upload (bytes)
        content_type: MIME type for the object
        
    Raises:
        Exception: If upload fails
    """
    print(f"Uploading to s3://{bucket_name}/{key}")
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={
                'updated_at': datetime.utcnow().isoformat(),
                'source': 'greenvilleopenmap.info'
            }
        )
        print(f"Successfully uploaded to S3")
        
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise


def handler(event, context):
    """
    Lambda handler for updating trail data
    
    Downloads trail GeoJSON files and stores them in S3, overwriting existing files.
    
    Args:
        event: Lambda event (unused)
        context: Lambda context
        
    Returns:
        dict: API Gateway response with status and message
    """
    print("Starting trail data update")
    
    # Get S3 bucket from environment
    bucket_name = os.environ.get('TRAIL_DATA_BUCKET')
    if not bucket_name:
        error_msg = "TRAIL_DATA_BUCKET environment variable not set"
        print(error_msg)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': error_msg
            })
        }
    
    results = {
        'main_trail': {'status': 'pending'},
        'spurs_trail': {'status': 'pending'}
    }
    
    try:
        # Download and upload main trail
        print("Processing main trail...")
        main_data = download_geojson(MAIN_TRAIL_URL)
        upload_to_s3(bucket_name, MAIN_TRAIL_KEY, main_data)
        results['main_trail'] = {
            'status': 'success',
            'size_bytes': len(main_data),
            's3_key': MAIN_TRAIL_KEY
        }
        print(f"Main trail updated successfully")
        
    except Exception as e:
        error_msg = f"Failed to update main trail: {str(e)}"
        print(error_msg)
        results['main_trail'] = {
            'status': 'error',
            'error': str(e)
        }
    
    try:
        # Download and upload spurs trail
        print("Processing spurs trail...")
        spurs_data = download_geojson(SPURS_TRAIL_URL)
        upload_to_s3(bucket_name, SPURS_TRAIL_KEY, spurs_data)
        results['spurs_trail'] = {
            'status': 'success',
            'size_bytes': len(spurs_data),
            's3_key': SPURS_TRAIL_KEY
        }
        print(f"Spurs trail updated successfully")
        
    except Exception as e:
        error_msg = f"Failed to update spurs trail: {str(e)}"
        print(error_msg)
        results['spurs_trail'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Determine overall status
    all_success = all(r['status'] == 'success' for r in results.values())
    any_success = any(r['status'] == 'success' for r in results.values())
    
    if all_success:
        status_code = 200
        message = "All trail data updated successfully"
    elif any_success:
        status_code = 207  # Multi-Status
        message = "Trail data partially updated"
    else:
        status_code = 500
        message = "Failed to update trail data"
    
    print(f"Trail data update complete: {message}")
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'message': message,
            'results': results,
            'bucket': bucket_name,
            'timestamp': datetime.utcnow().isoformat()
        })
    }
