# get_product.py - Handler for GET /products/{id}
import traceback
from db.products_db import get_product
from utils.response_utils import create_success_response, create_error_response
from utils.context_error_handler import ContextualErrorHandler

def handler(event, context):
    try:
        path_parameters = event.get('pathParameters') or {}
        product_id = path_parameters.get('id')

        if not product_id:
            return create_error_response(400, 'Product id is required')

        product = get_product(product_id)
        if product:
            return create_success_response(200, product)

        request_id = getattr(context, 'aws_request_id', None)
        query_params = event.get('queryStringParameters') or {}
        user_context = {k: v for k, v in {
            'search_term': query_params.get('q'),
            'category': query_params.get('category'),
        }.items() if v}

        error_body = ContextualErrorHandler(user_context).handle_product_not_found(product_id, request_id)
        return create_error_response(404, error_body)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return create_error_response(500, f'Internal server error - {str(e)}')
