import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
src_root = os.path.join(repo_root, 'src')
for path in (repo_root, src_root):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.db.products_db import get_product

# Complete API Gateway event structure for product API
api_gateway_event = {
    'httpMethod': 'GET',
    'path': '/products/prod_123',
    'pathParameters': {
        'id': 'prod_123'
    },
    'queryStringParameters': {
        'category': 'Electronics',
        'limit': '10'
    },
    'headers': {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer token123',
        'User-Agent': 'Mozilla/5.0...'
    },
    'body': None,
    'isBase64Encoded': False,
    'requestContext': {
        'requestId': 'test-request-id',
        'stage': 'dev',
        'httpMethod': 'GET'
    }
}

class APIGatewayEventFactory:
    """Factory for creating API Gateway events for testing."""
    
    @staticmethod
    def create_get_product_event(product_id, query_params=None):
        """Create event for GET /products/{id} requests."""
        return {
            'httpMethod': 'GET',
            'path': f'/products/{product_id}',
            'pathParameters': {'id': product_id},
            'queryStringParameters': query_params,
            'headers': {'Content-Type': 'application/json'},
            'body': None,
            'isBase64Encoded': False
        }
    
    @staticmethod
    def create_post_product_event(product_data):
        """Create event for POST /products requests."""
        return {
            'httpMethod': 'POST',
            'path': '/products',
            'pathParameters': None,
            'queryStringParameters': None,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(product_data),
            'isBase64Encoded': False
        }
    
    @staticmethod
    def create_query_products_event(category=None, limit=None):
        """Create event for GET /products with query parameters."""
        query_params = {}
        if category:
            query_params['category'] = category
        if limit:
            query_params['limit'] = str(limit)
            
        return {
            'httpMethod': 'GET',
            'path': '/products',
            'pathParameters': None,
            'queryStringParameters': query_params if query_params else None,
            'headers': {'Content-Type': 'application/json'},
            'body': None,
            'isBase64Encoded': False
        }

# Usage in tests
class TestProductAPI(unittest.TestCase):
    def test_get_product_with_factory(self):
        """Test using event factory for cleaner test code."""
        event = APIGatewayEventFactory.create_get_product_event('prod_123')
        
        with patch('src.lambda_code.get_product.get_product') as mock_get:
            mock_get.return_value = {'product_id': 'prod_123', 'name': 'Test Product'}
            
            from src.lambda_code.get_product import handler as lambda_handler
            response = lambda_handler(event, None)
            
            self.assertEqual(response['statusCode'], 200)
            self.assertIn('product_id', json.loads(response['body']))
            self.assertEqual(json.loads(response['body'])['name'], 'Test Product')


    def test_post_product_with_factor(self):
        """Test using event factory for cleaner test code."""
        event = APIGatewayEventFactory.create_post_product_event({'name': 'New Product', 'price': 99.99, 'category': 'Electronics'})

        with patch('src.lambda_code.insert_product.insert_product') as mock_insert:
            mock_insert.return_value = {'product_id': 'prod_456', 'name': 'New Product', 'price': 99.99, 'category': 'Electronics'}
            
            from src.lambda_code.insert_product import handler as lambda_handler
            response = lambda_handler(event, None)
            
            self.assertEqual(response['statusCode'], 201)
            self.assertIn('product_id', json.loads(response['body']))
            self.assertEqual(json.loads(response['body'])['name'], 'New Product')
            mock_insert.assert_called_once()

    def test_query_products_with_factory(self):
        """Test using event factory for cleaner test code."""
        event = APIGatewayEventFactory.create_query_products_event(category='Electronics')

        with patch('src.lambda_code.query_products.get_products_by_category') as mock_query:
            mock_query.return_value = [{'product_id': 'prod_789', 'name': 'Gadget'}]
            
            from src.lambda_code.query_products import handler as lambda_handler
            response = lambda_handler(event, None)
            
            self.assertEqual(response['statusCode'], 200)
            self.assertIsInstance(json.loads(response['body']), list)
            self.assertEqual(json.loads(response['body'])[0]['name'], 'Gadget')
            mock_query.assert_called_once_with('Electronics')