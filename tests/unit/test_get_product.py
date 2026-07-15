import json
import unittest
from unittest.mock import patch
from tests.unit.conftest import APIGatewayEventFactory

from src.lambda_code.get_product import handler as lambda_handler


class TestGetProduct(unittest.TestCase):
    def setUp(self):
        self.sample_product = {
            'product_id': 'prod_123',
            'name': 'Wireless Headphones',
            'price': 199.99,
            'category': 'Electronics',
            'inventory_count': 50
        }
        self.valid_event = APIGatewayEventFactory.create_get_product_event('prod_123')

    @patch('src.lambda_code.get_product.get_product')
    def test_get_product_success(self, mock_get_product):
        mock_get_product.return_value = self.sample_product

        response = lambda_handler(self.valid_event, None)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['product_id'], 'prod_123')
        self.assertEqual(body['name'], 'Wireless Headphones')
        mock_get_product.assert_called_once_with('prod_123')

    @patch('src.lambda_code.get_product.get_product')
    def test_get_product_not_found(self, mock_get_product):
        mock_get_product.return_value = None

        response = lambda_handler(APIGatewayEventFactory.create_get_product_event('nonexistent_product'), None)

        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertEqual(body['error']['type'], 'product_not_found')
        self.assertIn('nonexistent_product', body['error']['message'])

    def test_missing_path_parameters(self):
        event = APIGatewayEventFactory.create_get_product_event(None)
        event['pathParameters'] = None

        response = lambda_handler(event, None)

        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Product id is required', body['error'])