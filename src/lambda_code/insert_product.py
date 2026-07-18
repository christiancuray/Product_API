# insert_product.py - Handler for POST /products
import json
import uuid
import logging
from db.products_db import insert_product
from utils.response_utils import create_success_response, create_error_response, handle_product_validation_error

logger = logging.getLogger(__name__)

def handler(event, context):
    logger.debug("insert_product invoked", extra={
        "request_id": getattr(context, "aws_request_id", None),
        "path": event.get("path"),
        "body": event.get("body")
    })
     
    body = event.get('body') or ''
    try:
        # parse the req body as json
        item = json.loads(body)
        # validate the input
        if 'id' in item:
            error_body = handle_product_validation_error({'id': 'Product id is not allowed in request body'})
            logger.warning("Client supplied id in insert request", extra={"body": item})

            return create_error_response(400, error_body)

        product_id = str(uuid.uuid4())
        item['id'] = product_id
        
        identity = event.get('requestContext', {}).get('identity') or {}
        user_arn = identity.get('userArn') or 'unknown'

        inserted = insert_product(item, user_arn)
        logger.info("Product inserted successfully", extra={"product_id": product_id})
        return create_success_response(201, inserted)

    except ValueError as e:
        logger.warning("Insert product validation failure", exc_info=True)
        return create_error_response(409, str(e))
    except Exception as e:
        logger.exception(f"Unexpected error inserting product: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')
