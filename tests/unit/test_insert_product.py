import json
import pytest
from unittest.mock import patch
from tests.unit.conftest import APIGatewayEventFactory

from src.lambda_code.insert_product import handler


def make_event(body=None, raw_body=None, user_arn="arn:aws:iam::123456789012:user/test"):
    return APIGatewayEventFactory.create_post_product_event(body, user_arn=user_arn, raw_body=raw_body)


VALID_PRODUCT = {
    "title": "Wireless Headphones",
    "category": "Electronics",
    "description": "Noise-cancelling over-ear headphones",
    "price": 199.99,
}

DB_RESPONSE = {"ResponseMetadata": {"HTTPStatusCode": 200}}


# ---------------------------------------------------------------------------
# Valid product creation
# ---------------------------------------------------------------------------

class TestValidProductCreation:
    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_returns_201_with_all_required_fields(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        assert response["statusCode"] == 201
        mock_insert.assert_called_once()

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_auto_generates_id(self, mock_insert):
        handler(make_event(VALID_PRODUCT), None)

        call_args = mock_insert.call_args[0][0]
        assert "id" in call_args

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_passes_user_arn_to_db(self, mock_insert):
        arn = "arn:aws:iam::111111111111:user/alice"
        handler(make_event(VALID_PRODUCT, user_arn=arn), None)

        _, passed_arn = mock_insert.call_args[0]
        assert passed_arn == arn

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_unknown_user_arn_when_missing(self, mock_insert):
        event = {"httpMethod": "POST", "body": json.dumps(VALID_PRODUCT)}
        handler(event, None)

        _, passed_arn = mock_insert.call_args[0]
        assert passed_arn == "unknown"

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_response_body_contains_db_result(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        body = json.loads(response["body"])
        assert body == DB_RESPONSE


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestValidationErrors:
    @patch("src.lambda_code.insert_product.insert_product")
    def test_rejects_client_supplied_id(self, mock_insert):
        product_with_id = {**VALID_PRODUCT, "id": "custom-id-123"}
        response = handler(make_event(product_with_id), None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["type"] == "validation_error"
        assert "Product id is not allowed" in body["error"]["details"]["id"]
        mock_insert.assert_not_called()

    @patch("src.lambda_code.insert_product.insert_product")
    def test_rejects_invalid_json_body(self, mock_insert):
        # json.loads raises ValueError, which the handler maps to 409
        response = handler(make_event(raw_body="{not valid json}"), None)

        assert response["statusCode"] == 409
        mock_insert.assert_not_called()

    @patch("src.lambda_code.insert_product.insert_product")
    def test_handles_empty_body(self, mock_insert):
        # json.loads("") raises ValueError → 409
        response = handler(make_event(raw_body=""), None)

        assert response["statusCode"] == 409
        mock_insert.assert_not_called()

    @patch("src.lambda_code.insert_product.insert_product")
    def test_handles_none_body(self, mock_insert):
        # body defaults to '' then json.loads('') raises ValueError → 409
        response = handler(make_event(raw_body=None), None)

        assert response["statusCode"] == 409
        mock_insert.assert_not_called()


# ---------------------------------------------------------------------------
# Database errors
# ---------------------------------------------------------------------------

class TestDatabaseErrors:
    @patch("src.lambda_code.insert_product.insert_product", side_effect=Exception("Connection timed out"))
    def test_returns_500_on_db_connection_error(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        assert response["statusCode"] == 500
        assert "Internal server error" in json.loads(response["body"])["error"]

    @patch("src.lambda_code.insert_product.insert_product", side_effect=Exception("ResourceNotFoundException"))
    def test_returns_500_on_table_not_found(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        assert response["statusCode"] == 500

    @patch("src.lambda_code.insert_product.insert_product", side_effect=Exception("ProvisionedThroughputExceededException"))
    def test_returns_500_on_throughput_exceeded(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        assert response["statusCode"] == 500


# ---------------------------------------------------------------------------
# Duplicate product handling
# ---------------------------------------------------------------------------

class TestDuplicateProductHandling:
    @patch("src.lambda_code.insert_product.insert_product", side_effect=ValueError("Product already exists"))
    def test_returns_409_on_duplicate(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        assert response["statusCode"] == 409
        assert "Product already exists" in json.loads(response["body"])["error"]

    @patch("src.lambda_code.insert_product.insert_product", side_effect=ValueError("Duplicate title in category"))
    def test_409_error_message_is_propagated(self, mock_insert):
        response = handler(make_event(VALID_PRODUCT), None)

        body = json.loads(response["body"])
        assert "Duplicate title in category" in body["error"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_extremely_long_product_name(self, mock_insert):
        product = {**VALID_PRODUCT, "title": "A" * 500}
        response = handler(make_event(product), None)

        # Handler itself doesn't validate length — passes to DB layer
        assert response["statusCode"] == 201
        call_item = mock_insert.call_args[0][0]
        assert len(call_item["title"]) == 500

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_unicode_and_special_characters_in_title(self, mock_insert):
        product = {**VALID_PRODUCT, "title": "Ñoño 日本語 <script>alert(1)</script> & 'quotes'"}
        response = handler(make_event(product), None)

        assert response["statusCode"] == 201
        call_item = mock_insert.call_args[0][0]
        assert "日本語" in call_item["title"]

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_emoji_in_description(self, mock_insert):
        product = {**VALID_PRODUCT, "description": "Great product 🎧🔥💯"}
        response = handler(make_event(product), None)

        assert response["statusCode"] == 201

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_zero_price_passes_through_handler(self, mock_insert):
        """Price validation lives in the DB/schema layer, not the handler."""
        product = {**VALID_PRODUCT, "price": 0}
        response = handler(make_event(product), None)

        # Handler doesn't validate price — DB layer would reject it
        assert response["statusCode"] == 201

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_extra_fields_are_passed_through(self, mock_insert):
        product = {**VALID_PRODUCT, "custom_field": "custom_value", "tags": ["sale", "new"]}
        response = handler(make_event(product), None)

        assert response["statusCode"] == 201
        call_item = mock_insert.call_args[0][0]
        assert call_item["custom_field"] == "custom_value"
        assert call_item["tags"] == ["sale", "new"]

    @patch("src.lambda_code.insert_product.insert_product", return_value=DB_RESPONSE)
    def test_whitespace_only_title_passes_through_handler(self, mock_insert):
        product = {**VALID_PRODUCT, "title": "   "}
        response = handler(make_event(product), None)

        assert response["statusCode"] == 201
