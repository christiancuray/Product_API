import pytest
from decimal import Decimal

USER_ARN = "arn:aws:iam::123456789012:user/test"


class TestInsertProduct:
    def test_inserts_new_product(self, dynamodb_table):
        table, db = dynamodb_table
        item = {
            "id": "prod_new",
            "title": "Gaming Mouse",
            "price": 79.99,
            "category": "Electronics",
            "description": "High-precision gaming mouse",
        }
        db.insert_product(item, USER_ARN)

        stored = table.get_item(Key={"id": "prod_new"})["Item"]
        assert stored["title"] == "Gaming Mouse"

    def test_converts_float_price_to_decimal(self, dynamodb_table):
        table, db = dynamodb_table
        item = {
            "id": "prod_float",
            "title": "Float Price Item",
            "price": 9.99,
            "category": "Accessories",
            "description": "Test item",
        }
        db.insert_product(item, USER_ARN)

        stored = table.get_item(Key={"id": "prod_float"})["Item"]
        assert isinstance(stored["price"], Decimal)
        assert stored["price"] == Decimal("9.99")

    def test_sets_created_by_and_updated_by(self, dynamodb_table):
        table, db = dynamodb_table
        item = {"id": "prod_arn", "title": "T", "category": "Home", "description": "D", "price": 1.00}
        db.insert_product(item, USER_ARN)

        stored = table.get_item(Key={"id": "prod_arn"})["Item"]
        assert stored["created_by"] == USER_ARN
        assert stored["updated_by"] == USER_ARN

    def test_sets_default_version_when_absent(self, dynamodb_table):
        table, db = dynamodb_table
        item = {"id": "prod_ver", "title": "T", "category": "Home", "description": "D", "price": 1.00}
        db.insert_product(item, USER_ARN)

        stored = table.get_item(Key={"id": "prod_ver"})["Item"]
        assert stored["version"] == 1

    def test_sets_created_at_and_updated_at_timestamps(self, dynamodb_table):
        table, db = dynamodb_table
        item = {"id": "prod_ts", "title": "T", "category": "Home", "description": "D", "price": 1.00}
        db.insert_product(item, USER_ARN)

        stored = table.get_item(Key={"id": "prod_ts"})["Item"]
        assert "created_at" in stored
        assert "updated_at" in stored
        assert stored["created_at"] == stored["updated_at"]

    def test_overwrites_existing_item(self, dynamodb_table):
        """DynamoDB put_item replaces on duplicate key — no error raised."""
        table, db = dynamodb_table
        item = {"id": "prod_001", "title": "Overwritten", "category": "Home", "description": "D", "price": 1.00}
        db.insert_product(item, USER_ARN)

        stored = table.get_item(Key={"id": "prod_001"})["Item"]
        assert stored["title"] == "Overwritten"
