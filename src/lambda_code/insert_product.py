# insert_product.py - Handler for POST /products
import json
import uuid
from db.products_db import insert_product
from utils.response_utils import create_success_response, create_error_response, handle_product_validation_error

def handler(event, context):
    body = event.get('body') or ''
    try:
        # parse the req body as json
        item = json.loads(body)
        # validate the input
        if 'id' in item:
            error_body = handle_product_validation_error({'id': 'Product id is not allowed in request body'})
            return create_error_response(400, error_body)

        product_id = str(uuid.uuid4())
        item['id'] = product_id
        
        identity = event.get('requestContext', {}).get('identity') or {}
        user_arn = identity.get('userArn') or 'unknown'

        inserted = insert_product(item, user_arn)
        return create_success_response(201, inserted)

    except ValueError as e:
        return create_error_response(409, str(e))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')
