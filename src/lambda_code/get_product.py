# get_product.py - Handler for GET /products/{id}
import traceback
import logging
from db.products_db import get_product
from utils.response_utils import create_success_response, create_error_response
from utils.context_error_handler import ContextualErrorHandler

logger = logging.getLogger(__name__)

def handler(event, context):
    logger.debug("get_product invoked", extra={
        "request_id": getattr(context, "aws_request_id", None),
        "path": event.get("path"),
        "body": event.get("body")
    })

    try:
        path_parameters = event.get('pathParameters') or {}
        product_id = path_parameters.get('id')

        if not product_id:
            logger.error("Product id is missing in path parameters", extra={"path_parameters": path_parameters})
            return create_error_response(400, 'Product id is required')

        product = get_product(product_id)
        if product:
            logger.info("Product found", extra={"product_id": product_id})
            return create_success_response(200, product)

        request_id = getattr(context, 'aws_request_id', None)
        query_params = event.get('queryStringParameters') or {}
        user_context = {k: v for k, v in {
            'search_term': query_params.get('q'),
            'category': query_params.get('category'),
        }.items() if v}
        
        logger.warning("Product not found", extra={"product_id": product_id, "user_context": user_context})
        error_body = ContextualErrorHandler(user_context).handle_product_not_found(product_id, request_id)
        return create_error_response(404, error_body)

    except Exception as e:
        logger.exception(f"Unexpected error while getting product: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')
