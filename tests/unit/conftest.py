import os
import sys
import importlib
import json
import pytest
import boto3
from decimal import Decimal
from moto import mock_dynamodb


class APIGatewayEventFactory:
    """Factory for creating API Gateway events for testing."""

    @staticmethod
    def create_get_product_event(product_id, query_params=None):
        return {
            'httpMethod': 'GET',
            'path': f'/products/{product_id}',
            'pathParameters': {'id': product_id},
            'queryStringParameters': query_params,
            'headers': {'Content-Type': 'application/json'},
            'body': None,
            'isBase64Encoded': False,
        }

    @staticmethod
    def create_post_product_event(product_data, user_arn="arn:aws:iam::123456789012:user/test", raw_body=None):
        return {
            'httpMethod': 'POST',
            'path': '/products',
            'pathParameters': None,
            'queryStringParameters': None,
            'headers': {'Content-Type': 'application/json'},
            'body': raw_body if raw_body is not None else (json.dumps(product_data) if product_data is not None else None),
            'isBase64Encoded': False,
            'requestContext': {'identity': {'userArn': user_arn}},
        }

    @staticmethod
    def create_query_products_event(category=None, limit=None):
        query_params = {}
        if category:
            query_params['category'] = category
        if limit:
            query_params['limit'] = str(limit)
        return {
            'httpMethod': 'GET',
            'path': '/products',
            'pathParameters': None,
            'queryStringParameters': query_params or None,
            'headers': {'Content-Type': 'application/json'},
            'body': None,
            'isBase64Encoded': False,
        }


@pytest.fixture
def api_event_factory():
    return APIGatewayEventFactory

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
src_root = os.path.join(repo_root, "src")
for path in (repo_root, src_root):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ["TABLE_NAME"] = "Products"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

TABLE_NAME = "Products"
USER_ARN = "arn:aws:iam::123456789012:user/test"

SEED_PRODUCTS = [
    {
        "id": "prod_001",
        "title": "Wireless Headphones",
        "price": Decimal("199.99"),
        "category": "Electronics",
        "description": "Noise-cancelling over-ear headphones",
        "version": 1,
    },
    {
        "id": "prod_002",
        "title": "Mechanical Keyboard",
        "price": Decimal("149.99"),
        "category": "Computers",
        "description": "Tactile mechanical keyboard",
        "version": 1,
    },
    {
        "id": "prod_003",
        "title": "USB-C Hub",
        "price": Decimal("49.99"),
        "category": "Computers",
        "description": "7-in-1 USB-C hub",
        "version": 2,
    },
]


@pytest.fixture
def dynamodb_table():
    """Moto-mocked DynamoDB table. Reloads the db module so its module-level
    boto3 resource binds to the mock endpoint instead of real AWS."""
    with mock_dynamodb():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = resource.create_table(  # type: ignore[attr-defined]
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "category", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "category-index",
                    "KeySchema": [{"AttributeName": "category", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )

        for product in SEED_PRODUCTS:
            table.put_item(Item=product)

        import src.db.products_db as db_module
        importlib.reload(db_module)

        yield table, db_module
