import os
import sys
import importlib
import pytest
import boto3
from decimal import Decimal
from moto import mock_dynamodb

os.environ["TABLE_NAME"] = "Products"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
# amazonq-ignore-next-line
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
    """Spin up a moto-mocked DynamoDB table and reload the db module so its
    module-level boto3 resource binds to the mock endpoint."""
    with mock_dynamodb():
        client = boto3.resource("dynamodb", region_name="us-east-1")
        table = client.create_table(  # type: ignore[attr-defined]
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

        # Reload so the module-level `dynamodb` resource points at the mock
        import src.db.products_db as db_module
        importlib.reload(db_module)

        yield table, db_module


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# insert_product
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# update_product
# ---------------------------------------------------------------------------

class TestUpdateProduct:
    FIELDS = {
        "title": "Updated Headphones",
        "category": "Audio",
        "description": "Updated description",
        "price": 179.99,
    }

    def test_updates_existing_product(self, dynamodb_table):
        table, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert result["title"] == "Updated Headphones"
        assert result["category"] == "Audio"

    def test_converts_float_price_to_decimal_on_update(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert isinstance(result["price"], Decimal)

    def test_sets_updated_by_on_update(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert result["updated_by"] == USER_ARN

    def test_raises_value_error_for_nonexistent_product(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError, match="does not exist"):
            db.update_product("ghost_id", self.FIELDS, USER_ARN)

    def test_returns_all_new_attributes(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert "id" in result
        assert "updated_at" in result


# ---------------------------------------------------------------------------
# update_product_with_version
# ---------------------------------------------------------------------------

class TestUpdateProductWithVersion:
    FIELDS = {
        "title": "Versioned Update",
        "category": "Computers",
        "description": "Updated via versioned call",
        "price": 139.99,
    }

    def test_updates_when_version_matches(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert result["title"] == "Versioned Update"
        assert result["version"] == 2

    def test_increments_version_number(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product_with_version("prod_003", self.FIELDS, USER_ARN, expected_version=2)

        assert result["version"] == 3

    def test_raises_value_error_on_version_mismatch(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError, match="modified by another user"):
            db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=99)

    def test_raises_value_error_for_nonexistent_product(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError):
            db.update_product_with_version("ghost_id", self.FIELDS, USER_ARN, expected_version=1)


# ---------------------------------------------------------------------------
# get_all_products
# ---------------------------------------------------------------------------

class TestGetAllProducts:
    def test_returns_all_seeded_products(self, dynamodb_table):
        _, db = dynamodb_table
        products = db.get_all_products()

        assert len(products) == len(SEED_PRODUCTS)

    def test_converts_all_prices_to_float(self, dynamodb_table):
        _, db = dynamodb_table
        products = db.get_all_products()

        for p in products:
            assert isinstance(p["price"], float)

    def test_returns_empty_list_when_table_is_empty(self, dynamodb_table):
        table, db = dynamodb_table
        # Clear the table
        for p in SEED_PRODUCTS:
            table.delete_item(Key={"id": p["id"]})

        assert db.get_all_products() == []


# ---------------------------------------------------------------------------
# get_products_by_category
# ---------------------------------------------------------------------------

class TestGetProductsByCategory:
    def test_returns_products_for_matching_category(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Computers")

        assert len(results) == 2
        assert all(p["category"] == "Computers" for p in results)

    def test_returns_empty_list_for_unknown_category(self, dynamodb_table):
        _, db = dynamodb_table
        assert db.get_products_by_category("NonExistent") == []

    def test_converts_prices_to_float(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Electronics")

        assert all(isinstance(p["price"], float) for p in results)

    def test_single_category_result(self, dynamodb_table):
        _, db = dynamodb_table
        results = db.get_products_by_category("Electronics")

        assert len(results) == 1
        assert results[0]["title"] == "Wireless Headphones"


# ---------------------------------------------------------------------------
# get_product — fallback logic (lines 22-27)
# ---------------------------------------------------------------------------

class TestGetProductFallback:
    """Tests for the legacy product_id key fallback in get_product()."""

    def test_fallback_finds_item_by_product_id_key(self, dynamodb_table):
        """When get_item(Key={'id': ...}) raises, the fallback tries product_id."""
        _, db = dynamodb_table
        import unittest.mock as mock

        legacy_item = {
            "product_id": "legacy_001",
            "title": "Legacy Item",
            "price": Decimal("29.99"),
            "category": "Accessories",
            "description": "Old-schema product",
        }

        # First call (id key) raises; second call (product_id key) returns the item
        mock_table = mock.MagicMock()
        mock_table.get_item.side_effect = [
            Exception("Simulated primary key failure"),
            {"Item": legacy_item},
        ]

        with mock.patch.object(db, "get_table", return_value=mock_table):
            result = db.get_product("legacy_001")

        assert result is not None
        assert result["title"] == "Legacy Item"

    def test_fallback_returns_none_when_both_keys_fail(self, dynamodb_table):
        """Returns None when both the primary and fallback get_item calls raise."""
        _, db = dynamodb_table
        import unittest.mock as mock

        mock_table = mock.MagicMock()
        mock_table.get_item.side_effect = Exception("DynamoDB unavailable")

        with mock.patch.object(db, "get_table", return_value=mock_table):
            result = db.get_product("any_id")

        assert result is None
        assert mock_table.get_item.call_count == 2

    def test_fallback_converts_decimal_price_to_float(self, dynamodb_table):
        """Price is still converted to float when item is found via fallback."""
        _, db = dynamodb_table
        import unittest.mock as mock

        legacy_item = {
            "product_id": "legacy_002",
            "title": "Legacy Priced",
            "price": Decimal("9.99"),
            "category": "Home",
            "description": "D",
        }

        mock_table = mock.MagicMock()
        mock_table.get_item.side_effect = [
            Exception("force fallback"),
            {"Item": legacy_item},
        ]

        with mock.patch.object(db, "get_table", return_value=mock_table):
            result = db.get_product("legacy_002")

        assert result is not None
        assert isinstance(result["price"], float)
        assert result["price"] == 9.99

    def test_primary_key_success_does_not_trigger_fallback(self, dynamodb_table):
        """When the primary key lookup succeeds, fallback is never attempted."""
        _, db = dynamodb_table
        import unittest.mock as mock

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

        with mock.patch.object(db, "get_table", patched_get_table):
            db.get_product("prod_001")

        assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# update_product — additional edge cases (lines 57-91)
# ---------------------------------------------------------------------------

class TestUpdateProductEdgeCases:
    FIELDS = {
        "title": "Edge Case Title",
        "category": "Electronics",
        "description": "Edge case description",
        "price": Decimal("99.99"),
    }

    def test_accepts_decimal_price_without_conversion(self, dynamodb_table):
        """Decimal price input is passed through unchanged (no str conversion)."""
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert isinstance(result["price"], Decimal)
        assert result["price"] == Decimal("99.99")

    def test_updated_at_is_set_as_iso_string(self, dynamodb_table):
        """updated_at is written as an ISO 8601 string ending in Z."""
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert isinstance(result["updated_at"], str)
        assert result["updated_at"].endswith("Z")

    def test_non_conditional_client_error_is_reraised(self, dynamodb_table):
        """ClientErrors other than ConditionalCheckFailed bubble up unchanged."""
        _, db = dynamodb_table
        import unittest.mock as mock
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Too many requests"}}
        mock_table = mock.MagicMock()
        mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

        with mock.patch.object(db, "get_table", return_value=mock_table):
            with pytest.raises(ClientError) as exc_info:
                db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert exc_info.value.response["Error"]["Code"] == "ProvisionedThroughputExceededException"

    def test_error_message_contains_product_id(self, dynamodb_table):
        """ValueError message for missing product includes the product_id."""
        _, db = dynamodb_table
        with pytest.raises(ValueError, match="missing_id"):
            db.update_product("missing_id", self.FIELDS, USER_ARN)

    def test_does_not_modify_version(self, dynamodb_table):
        """update_product does not touch the version field."""
        table, db = dynamodb_table
        db.update_product("prod_001", self.FIELDS, USER_ARN)

        stored = table.get_item(Key={"id": "prod_001"})["Item"]
        assert stored["version"] == 1  # unchanged from seed


# ---------------------------------------------------------------------------
# update_product_with_version — additional edge cases (lines 95-131)
# ---------------------------------------------------------------------------

class TestUpdateProductWithVersionEdgeCases:
    FIELDS = {
        "title": "Versioned Edge",
        "category": "Computers",
        "description": "Versioned edge description",
        "price": 59.99,
    }

    def test_sequential_updates_increment_version_each_time(self, dynamodb_table):
        """Two back-to-back versioned updates each increment the version."""
        _, db = dynamodb_table
        first = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)
        assert first["version"] == 2

        second = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=2)
        assert second["version"] == 3

    def test_stale_version_after_concurrent_update_raises(self, dynamodb_table):
        """Using the old version after a successful update raises ValueError."""
        _, db = dynamodb_table
        db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        with pytest.raises(ValueError, match="modified by another user"):
            db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

    def test_sets_updated_by_on_versioned_update(self, dynamodb_table):
        """updated_by is set to the provided user_arn."""
        _, db = dynamodb_table
        result = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert result["updated_by"] == USER_ARN

    def test_non_conditional_client_error_is_reraised(self, dynamodb_table):
        """ClientErrors other than ConditionalCheckFailed bubble up unchanged."""
        _, db = dynamodb_table
        import unittest.mock as mock
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "InternalServerError", "Message": "Service error"}}
        mock_table = mock.MagicMock()
        mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

        with mock.patch.object(db, "get_table", return_value=mock_table):
            with pytest.raises(ClientError) as exc_info:
                db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert exc_info.value.response["Error"]["Code"] == "InternalServerError"

    def test_updated_at_is_set_as_iso_string(self, dynamodb_table):
        """updated_at is written as an ISO 8601 string ending in Z."""
        _, db = dynamodb_table
        result = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert isinstance(result["updated_at"], str)
        assert result["updated_at"].endswith("Z")


# ---------------------------------------------------------------------------
# get_all_products — additional edge cases (lines 135-139)
# ---------------------------------------------------------------------------

class TestGetAllProductsEdgeCases:
    def test_items_without_price_are_returned_unchanged(self, dynamodb_table):
        """Items that have no price field are included without modification."""
        table, db = dynamodb_table
        table.put_item(Item={"id": "no_price", "title": "No Price Item", "category": "Home", "description": "D"})

        products = db.get_all_products()
        no_price = next(p for p in products if p["id"] == "no_price")

        assert "price" not in no_price

    def test_items_with_non_decimal_price_are_returned_unchanged(self, dynamodb_table):
        """Items whose price is already a string or int are not converted."""
        table, db = dynamodb_table
        table.put_item(Item={"id": "str_price", "title": "String Price", "category": "Home", "description": "D", "price": "free"})

        products = db.get_all_products()
        item = next(p for p in products if p["id"] == "str_price")

        assert item["price"] == "free"

    def test_returns_all_fields_for_each_product(self, dynamodb_table):
        """All stored attributes are present in the returned items."""
        _, db = dynamodb_table
        products = db.get_all_products()
        prod = next(p for p in products if p["id"] == "prod_001")

        assert prod["title"] == "Wireless Headphones"
        assert prod["category"] == "Electronics"
        assert prod["description"] == "Noise-cancelling over-ear headphones"
        assert prod["version"] == 1


# ---------------------------------------------------------------------------
# get_products_by_category — additional edge cases (lines 143-150)
# ---------------------------------------------------------------------------

class TestGetProductsByCategoryEdgeCases:
    def test_items_without_price_are_returned_unchanged(self, dynamodb_table):
        """Items in a category that have no price field are included as-is."""
        table, db = dynamodb_table
        table.put_item(Item={"id": "no_price_cat", "title": "Free Item", "category": "Computers", "description": "D"})

        results = db.get_products_by_category("Computers")
        no_price = next(p for p in results if p["id"] == "no_price_cat")

        assert "price" not in no_price

    def test_returns_all_fields_for_category_items(self, dynamodb_table):
        """All stored attributes are present in category query results."""
        _, db = dynamodb_table
        results = db.get_products_by_category("Electronics")

        assert len(results) == 1
        item = results[0]
        assert item["id"] == "prod_001"
        assert item["description"] == "Noise-cancelling over-ear headphones"
        assert item["version"] == 1

    def test_category_query_does_not_return_other_categories(self, dynamodb_table):
        """Items from other categories are not included in the result."""
        _, db = dynamodb_table
        results = db.get_products_by_category("Computers")

        ids = {p["id"] for p in results}
        assert "prod_001" not in ids  # prod_001 is Electronics

    def test_multiple_inserts_reflected_in_category_query(self, dynamodb_table):
        """Newly inserted items appear in subsequent category queries."""
        table, db = dynamodb_table
        table.put_item(Item={
            "id": "prod_new_elec",
            "title": "Smart Speaker",
            "price": Decimal("79.99"),
            "category": "Electronics",
            "description": "Voice-controlled speaker",
            "version": 1,
        })

        results = db.get_products_by_category("Electronics")
        assert len(results) == 2
        assert any(p["id"] == "prod_new_elec" for p in results)
