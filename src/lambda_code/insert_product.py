# insert_product.py - Handler for POST /products
import json
import uuid
from db.products_db import insert_product
from utils.response_utils import create_success_response, create_error_response

def handler(event, context):
    body = event.get('body') or ''
    try:
        # Parse JSON body
        item = json.loads(body)
        
        # Prevent clients from specifying their own ID
        if 'id' in item:
            return create_error_response(400, 'Product id is not allowed')
        
        # Generate unique ID
        product_id = str(uuid.uuid4())
        item['id'] = product_id
        
        # Extract user Amazon Resource Name (ARN) from request context
        identity = event.get('requestContext', {}).get('identity') or {}
        user_arn = identity.get('userArn') or 'unknown'
        
        # Store in DynamoDB
        inserted = insert_product(item, user_arn)
        
        # Return created product
        return create_success_response(201, inserted)
    except ValueError as e:
        return create_error_response(409, str(e))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')