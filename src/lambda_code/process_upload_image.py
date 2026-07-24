import logging
import os
from datetime import datetime

import boto3

from utils.response_utils import create_success_response

logger = logging.getLogger(__name__)

# Initialize clients outside handler for reuse
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
product_table = dynamodb.Table(os.environ['TABLE_NAME']) # type: ignore

def handler(event, context):
    
    # Process each S3 event record
    for record in event['Records']:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        
        try:
            # Extract product ID from object key
            # Format: products/prod_123/main.jpg
            product_id = object_key.split('/')[1]
            
            # Get image metadata without downloading the file
            response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
            file_size = response['ContentLength']
            content_type = response['ContentType']
            
            # Create image URL
            image_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
            
            # Update product record with image information
            product_table.update_item(
                Key={'id': product_id},
                UpdateExpression='SET image_url = :img, file_size = :size, upload_date = :date',
                ExpressionAttributeValues={
                    ':img': image_url,
                    ':size': file_size,
                    ':date': datetime.now().isoformat()  # Use timestamp
                }
            )
            
            # TODO: To do this in production, you would choose from the following:
            # 1. Use AWS Lambda layers with image processing libraries such as Pillow
            # 2. Invoke another service like AWS Batch for heavy processing
            # 3. Use Amazon Rekognition for image analysis
            # 4. Start an AWS Step Functions workflow for complex workflows
            
            logger.info(f"Processed image metadata for product {product_id}")
            
        except Exception as e:
            logger.exception(f"Error processing {object_key}: {e}")
    
    return create_success_response(200, 'Image metadata processed successfully')