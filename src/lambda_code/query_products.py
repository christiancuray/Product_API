# query_products.py - Handler for GET /products

from utils.response_utils import create_error_response, create_success_response
from db.products_db import get_products_by_category, get_all_products

def handler(event, context):
    # extract query parameters and path parameters from the event
    path_parameters = event.get('pathParameters') or {}
    try:
        query_parameters = event.get('queryStringParameters') or {}
        category = query_parameters.get('category')
        
        if category:
            products = get_products_by_category(category)
        else:
            products = get_all_products()
        
        return create_success_response(200, products)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')