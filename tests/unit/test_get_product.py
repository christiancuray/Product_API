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

class TestGetProduct(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.sample_product = {
            'product_id': 'prod_123',
            'name': 'Wireless Headphones',
            'price': 199.99,
            'category': 'Electronics',
            'inventory_count': 50
        }
        
        self.valid_event = {
            'httpMethod': 'GET',
            'pathParameters': {'id': 'prod_123'},
            'queryStringParameters': None,
            'body': None
        }

    @patch('src.lambda_code.get_product.get_product')
    def test_get_product_success(self, mock_get_product):
        """Test successful product retrieval."""
        # Arrange
        mock_get_product.return_value = self.sample_product
        
        # Act
        from src.lambda_code.get_product import handler as lambda_handler
        response = lambda_handler(self.valid_event, None)
        
        # Assert
        self.assertEqual(response['statusCode'], 200)
        
        body = json.loads(response['body'])
        self.assertEqual(body['product_id'], 'prod_123')
        self.assertEqual(body['name'], 'Wireless Headphones')
        
        # Verify database was called correctly
        mock_get_product.assert_called_once_with('prod_123')

    @patch('src.lambda_code.get_product.get_product')
    def test_get_product_not_found(self, mock_get_product):
        """Test handling of non-existent product requests."""
        # Arrange
        mock_get_product.return_value = None
        
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'id': 'nonexistent_product'}
        }
        
        # Act
        from src.lambda_code.get_product import handler as lambda_handler
        response = lambda_handler(event, None)
        
        # Assert
        self.assertEqual(response['statusCode'], 404)
        
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Product not found', body['error'])

    def test_missing_path_parameters(self):
        """Test handling of malformed requests."""
        # Arrange
        invalid_event = {
            'httpMethod': 'GET',
            'pathParameters': None  # Missing required parameters
        }
        
         # Act
        from src.lambda_code.get_product import handler as lambda_handler
        response = lambda_handler(invalid_event, None)
        
        # Assert
        self.assertEqual(response['statusCode'], 400)
        
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Product id is required', body['error'])