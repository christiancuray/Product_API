# update_product.py - Handler for PUT /products/{id}
import json
import logging
from utils.response_utils import create_success_response, create_error_response, handle_product_validation_error
from utils.context_error_handler import ContextualErrorHandler
from db.products_db import update_product
from utils.product_schema import ProductInput
from pydantic import ValidationError

logger = logging.getLogger(__name__)

def handler(event, context):
    logger.debug("update_product invoked", extra={
        "request_id": getattr(context, "aws_request_id", None),
        "path": event.get("path"),
        "body": event.get("body")
    })

    product_id = None
    try:
        body = event.get('body') or ''
        product_id = (event.get('pathParameters') or {}).get('id')

        if not product_id:
            logger.error("Product id is missing in path parameters", extra={"path_parameters": event.get('pathParameters')})
            return create_error_response(400, 'Product id is required')

        raw_data = json.loads(body)

        # Validate and coerce input through Pydantic schema before hitting the DB
        product_input = ProductInput(**raw_data)
        validated_data = product_input.model_dump()

        identity = event.get('requestContext', {}).get('identity') or {}
        user_arn = identity.get('userArn') or 'unknown'  # fallback when called outside API Gateway

        updated = update_product(product_id, validated_data, user_arn)
        logger.info("Product updated successfully", extra={"product_id": product_id})
        return create_success_response(200, updated)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body", extra={"body": event.get('body')})
        return create_error_response(400, 'Invalid JSON in request body')

    except ValidationError as e:
        error_details = {err['loc'][0]: err['msg'] for err in e.errors()}
        error_body = handle_product_validation_error(error_details)
        logger.error("Product validation failed", extra={"error_details": error_details})
        return  create_error_response(400, error_body)

    except ValueError as e:
        # DB layer raises ValueError when the product doesn't exist
        request_id = getattr(context, 'aws_request_id', None)
        error_body = ContextualErrorHandler().handle_product_not_found(product_id, request_id)
        logger.error("Product not found", extra={"product_id": product_id, "request_id": request_id})
        return create_error_response(404, error_body)

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')
