import boto3
import json
import os
from botocore.exceptions import ClientError
from utils.response_utils import create_success_response, create_error_response 
import logging

logger = logging.getLogger(__name__)

# Initialize S3 client outside handler for reuse
s3_client = boto3.client('s3')

def handler(event, context):
    product_image_bucket = os.environ['S3_BUCKET_NAME']

    # Extract product ID and image type from the req
    product_id = event['pathParameters']['id']
    image_type = event['queryStringParameters'].get('type', 'main')
    object_key = f"products/{product_id}/{image_type}.jpg"
    
    try:
        # Generate presigned URL for GET operation
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': product_image_bucket,
                'Key': object_key
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        logger.info("Download URL generated successfully")
        return create_success_response(200, {'download_url': download_url, 'expires_in': 3600})
        
    except ClientError as e:
        logger.exception(f"Error generating download URL: {str(e)}")
        return create_error_response(404, {'error': 'Image not found', 'details': str(e)})