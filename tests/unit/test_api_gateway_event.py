import os
import sys
import unittest
import json
from unittest.mock import patch

from tests.unit.conftest import APIGatewayEventFactory

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