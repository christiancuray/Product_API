import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

USER_ARN = "arn:aws:iam::123456789012:user/test"


class TestUpdateProduct:
    FIELDS = {
        "title": "Updated Headphones",
        "category": "Audio",
        "description": "Updated description",
        "price": 179.99,
    }

    def test_updates_existing_product(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert result["title"] == "Updated Headphones"
        assert result["category"] == "Audio"

    def test_converts_float_price_to_decimal(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert isinstance(result["price"], Decimal)

    def test_accepts_decimal_price_without_conversion(self, dynamodb_table):
        """Decimal price input skips the float branch and is stored as-is."""
        _, db = dynamodb_table
        fields = {**self.FIELDS, "price": Decimal("99.99")}
        result = db.update_product("prod_001", fields, USER_ARN)

        assert isinstance(result["price"], Decimal)
        assert result["price"] == Decimal("99.99")

    def test_sets_updated_by(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert result["updated_by"] == USER_ARN

    def test_updated_at_is_iso_string(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert isinstance(result["updated_at"], str)
        assert result["updated_at"].endswith("Z")

    def test_returns_all_new_attributes(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert "id" in result
        assert "updated_at" in result

    def test_does_not_modify_version(self, dynamodb_table):
        """update_product never touches the version field."""
        table, db = dynamodb_table
        db.update_product("prod_001", self.FIELDS, USER_ARN)

        stored = table.get_item(Key={"id": "prod_001"})["Item"]
        assert stored["version"] == 1

    def test_raises_value_error_for_nonexistent_product(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError, match="does not exist"):
            db.update_product("ghost_id", self.FIELDS, USER_ARN)

    def test_error_message_contains_product_id(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError, match="missing_id"):
            db.update_product("missing_id", self.FIELDS, USER_ARN)

    def test_non_conditional_client_error_is_reraised(self, dynamodb_table):
        _, db = dynamodb_table
        error_response = {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Too many requests"}}
        mock_table = MagicMock()
        mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

        with patch.object(db, "get_table", return_value=mock_table):
            with pytest.raises(ClientError) as exc_info:
                db.update_product("prod_001", self.FIELDS, USER_ARN)

        assert exc_info.value.response["Error"]["Code"] == "ProvisionedThroughputExceededException"


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

    def test_sequential_updates_increment_version_each_time(self, dynamodb_table):
        _, db = dynamodb_table
        first = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)
        assert first["version"] == 2

        second = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=2)
        assert second["version"] == 3

    def test_sets_updated_by(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert result["updated_by"] == USER_ARN

    def test_updated_at_is_iso_string(self, dynamodb_table):
        _, db = dynamodb_table
        result = db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert isinstance(result["updated_at"], str)
        assert result["updated_at"].endswith("Z")

    def test_raises_value_error_on_version_mismatch(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError, match="modified by another user"):
            db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=99)

    def test_stale_version_after_concurrent_update_raises(self, dynamodb_table):
        """Reusing the old version after a successful update raises ValueError."""
        _, db = dynamodb_table
        db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        with pytest.raises(ValueError, match="modified by another user"):
            db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

    def test_raises_value_error_for_nonexistent_product(self, dynamodb_table):
        _, db = dynamodb_table
        with pytest.raises(ValueError):
            db.update_product_with_version("ghost_id", self.FIELDS, USER_ARN, expected_version=1)

    def test_non_conditional_client_error_is_reraised(self, dynamodb_table):
        _, db = dynamodb_table
        error_response = {"Error": {"Code": "InternalServerError", "Message": "Service error"}}
        mock_table = MagicMock()
        mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

        with patch.object(db, "get_table", return_value=mock_table):
            with pytest.raises(ClientError) as exc_info:
                db.update_product_with_version("prod_002", self.FIELDS, USER_ARN, expected_version=1)

        assert exc_info.value.response["Error"]["Code"] == "InternalServerError"
