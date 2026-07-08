import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

USER_ARN = "arn:aws:iam::123456789012:user/test"


class TestGetProduct:
    def test_returns_existing_product(self, dynamodb_table):
        _, db = dynamodb_table
        product = db.get_product("prod_001")

        assert product is not None
        assert product["id"] == "prod_001"
        assert product["title"] == "Wireless Headphones"

    def test_converts_decimal_price_to_float(self, dynamodb_table):
        _, db = dynamodb_table
        product = db.get_product("prod_001")

        assert isinstance(product["price"], float)
        assert product["price"] == 199.99

    def test_returns_none_for_missing_product(self, dynamodb_table):
        _, db = dynamodb_table
        assert db.get_product("does_not_exist") is None


class TestGetProductFallback:
    """Fallback logic: when get_item(Key={'id': ...}) raises, retries with product_id key."""

    def test_fallback_finds_item_by_product_id_key(self, dynamodb_table):
        _, db = dynamodb_table
        legacy_item = {
            "product_id": "legacy_001",
            "title": "Legacy Item",
            "price": Decimal("29.99"),
            "category": "Accessories",
            "description": "Old-schema product",
        }
        mock_table = MagicMock()
        mock_table.get_item.side_effect = [
            Exception("Simulated primary key failure"),
            {"Item": legacy_item},
        ]

        with patch.object(db, "get_table", return_value=mock_table):
            result = db.get_product("legacy_001")

        assert result is not None
        assert result["title"] == "Legacy Item"

    def test_fallback_returns_none_when_both_keys_fail(self, dynamodb_table):
        _, db = dynamodb_table
        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("DynamoDB unavailable")

        with patch.object(db, "get_table", return_value=mock_table):
            result = db.get_product("any_id")

        assert result is None
        assert mock_table.get_item.call_count == 2

    def test_fallback_converts_decimal_price_to_float(self, dynamodb_table):
        _, db = dynamodb_table
        legacy_item = {
            "product_id": "legacy_002",
            "title": "Legacy Priced",
            "price": Decimal("9.99"),
            "category": "Home",
            "description": "D",
        }
        mock_table = MagicMock()
        mock_table.get_item.side_effect = [
            Exception("force fallback"),
            {"Item": legacy_item},
        ]

        with patch.object(db, "get_table", return_value=mock_table):
            result = db.get_product("legacy_002")

        assert result is not None
        assert isinstance(result["price"], float)
        assert result["price"] == 9.99

    def test_primary_key_success_does_not_trigger_fallback(self, dynamodb_table):
        _, db = dynamodb_table
        original_get_table = db.get_table
        call_count = {"n": 0}

        def patched_get_table():
            tbl = original_get_table()
            original_get_item = tbl.get_item

            def counting_get_item(Key, **kwargs):
                call_count["n"] += 1
                return original_get_item(Key=Key, **kwargs)

            tbl.get_item = counting_get_item
            return tbl

        with patch.object(db, "get_table", patched_get_table):
            db.get_product("prod_001")

        assert call_count["n"] == 1
