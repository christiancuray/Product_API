# update_product.py - Handler for PUT /products/{id}
import json
from utils.response_utils import create_success_response, create_error_response, handle_product_validation_error
from utils.context_error_handler import ContextualErrorHandler
from db.products_db import update_product
from utils.product_schema import ProductInput
from pydantic import ValidationError

def handler(event, context):
    product_id = None  # initialized here so it's always bound in the except ValueError block
    try:
        body = event.get('body') or ''
        product_id = (event.get('pathParameters') or {}).get('id')

        if not product_id:
            return create_error_response(400, 'Product id is required')

        raw_data = json.loads(body)

        # Validate and coerce input through Pydantic schema before hitting the DB
        product_input = ProductInput(**raw_data)
        validated_data = product_input.model_dump()

        identity = event.get('requestContext', {}).get('identity') or {}
        user_arn = identity.get('userArn') or 'unknown'  # fallback when called outside API Gateway

        updated = update_product(product_id, validated_data, user_arn)
        return create_success_response(200, updated)

    except json.JSONDecodeError:
        # Caught before ValueError so malformed JSON returns 400 not 404
        return create_error_response(400, 'Invalid JSON in request body')

    except ValidationError as e:
        error_details = {err['loc'][0]: err['msg'] for err in e.errors()}
        error_body = handle_product_validation_error(error_details)
        return  create_error_response(400, error_body)

    except ValueError as e:
        # DB layer raises ValueError when the product doesn't exist
        request_id = getattr(context, 'aws_request_id', None)
        error_body = ContextualErrorHandler().handle_product_not_found(product_id, request_id)
        return create_error_response(404, error_body)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')
