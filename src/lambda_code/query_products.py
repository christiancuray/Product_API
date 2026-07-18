# query_products.py - Handler for GET /products
import logging
from utils.response_utils import create_error_response, create_success_response
from db.products_db import get_products_by_category, get_all_products

logger = logging.getLogger(__name__)

def handler(event, context):
    logger.debug("query_products invoked", extra={
        "request_id": getattr(context, "aws_request_id", None),
        "path": event.get("path"),
        "body": event.get("body")
    })
    
    try:
        query_parameters = event.get('queryStringParameters') or {}
        category = query_parameters.get('category')
        
        if category:
            products = get_products_by_category(category)
        else:
            products = get_all_products()

        logger.info(f"Products retrieved successfully", extra={"category": category, "count": len(products)})
        return create_success_response(200, products)
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')