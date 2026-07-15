import json
import pytest
from unittest.mock import patch
from tests.unit.conftest import APIGatewayEventFactory

from src.lambda_code.update_product import handler


VALID_PRODUCT = {
    "title": "Wireless Headphones",
    "category": "Electronics",
    "description": "Noise-cancelling over-ear headphones",
    "price": 199.99,
}

DB_RESPONSE = {
    "id": "prod_123",
    **VALID_PRODUCT,
    "updated_at": "2024-01-01T00:00:00Z",
    "updated_by": "arn:aws:iam::123456789012:user/test",
}


def make_event(product_id="prod_123", body=None, user_arn="arn:aws:iam::123456789012:user/test"):
    event = APIGatewayEventFactory.create_post_product_event(body or VALID_PRODUCT, user_arn=user_arn)
    event["httpMethod"] = "PUT"
    event["pathParameters"] = {"id": product_id}
    return event


# ---------------------------------------------------------------------------
# Successful updates
# ---------------------------------------------------------------------------

class TestValidUpdate:
    @patch("src.lambda_code.update_product.update_product", return_value=DB_RESPONSE)
    def test_returns_200_on_valid_update(self, mock_update):
        response = handler(make_event(), None)

        assert response["statusCode"] == 200
        mock_update.assert_called_once()

    @patch("src.lambda_code.update_product.update_product", return_value=DB_RESPONSE)
    def test_response_body_contains_updated_product(self, mock_update):
        response = handler(make_event(), None)

        body = json.loads(response["body"])
        assert body["id"] == "prod_123"
        assert body["title"] == "Wireless Headphones"

    @patch("src.lambda_code.update_product.update_product", return_value=DB_RESPONSE)
    def test_passes_product_id_to_db(self, mock_update):
        handler(make_event(product_id="prod_456"), None)

        product_id_arg = mock_update.call_args[0][0]
        assert product_id_arg == "prod_456"

    @patch("src.lambda_code.update_product.update_product", return_value=DB_RESPONSE)
    def test_passes_user_arn_to_db(self, mock_update):
        arn = "arn:aws:iam::111111111111:user/alice"
        handler(make_event(user_arn=arn), None)

        user_arn_arg = mock_update.call_args[0][2]
        assert user_arn_arg == arn

    @patch("src.lambda_code.update_product.update_product", return_value=DB_RESPONSE)
    def test_unknown_user_arn_when_missing(self, mock_update):
        event = make_event()
        del event["requestContext"]
        handler(event, None)

        user_arn_arg = mock_update.call_args[0][2]
        assert user_arn_arg == "unknown"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestValidationErrors:
    @patch("src.lambda_code.update_product.update_product")
    def test_returns_400_on_missing_required_field(self, mock_update):
        body = {k: v for k, v in VALID_PRODUCT.items() if k != "title"}
        response = handler(make_event(body=body), None)

        assert response["statusCode"] == 400
        mock_update.assert_not_called()

    @patch("src.lambda_code.update_product.update_product")
    def test_returns_400_on_invalid_category(self, mock_update):
        body = {**VALID_PRODUCT, "category": "InvalidCategory"}
        response = handler(make_event(body=body), None)

        assert response["statusCode"] == 400
        mock_update.assert_not_called()

    @patch("src.lambda_code.update_product.update_product")
    def test_returns_400_on_zero_price(self, mock_update):
        body = {**VALID_PRODUCT, "price": 0}
        response = handler(make_event(body=body), None)

        assert response["statusCode"] == 400
        mock_update.assert_not_called()

    @patch("src.lambda_code.update_product.update_product")
    def test_returns_400_on_negative_price(self, mock_update):
        body = {**VALID_PRODUCT, "price": -10}
        response = handler(make_event(body=body), None)

        assert response["statusCode"] == 400
        mock_update.assert_not_called()

    @patch("src.lambda_code.update_product.update_product")
    def test_returns_400_on_missing_product_id(self, mock_update):
        event = make_event()
        event["pathParameters"] = None
        response = handler(event, None)

        assert response["statusCode"] == 400
        mock_update.assert_not_called()

    @patch("src.lambda_code.update_product.update_product")
    def test_returns_400_on_invalid_json(self, mock_update):
        event = APIGatewayEventFactory.create_post_product_event(None, raw_body="{invalid}")
        event["pathParameters"] = {"id": "prod_123"}
        response = handler(event, None)

        assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

class TestProductNotFound:
    @patch("src.lambda_code.update_product.update_product", side_effect=ValueError("Product does not exist"))
    def test_returns_404_when_product_not_found(self, mock_update):
        response = handler(make_event(), None)

        assert response["statusCode"] == 404

    @patch("src.lambda_code.update_product.update_product", side_effect=ValueError("Product does not exist"))
    def test_404_body_contains_error_type(self, mock_update):
        response = handler(make_event(), None)

        body = json.loads(response["body"])
        assert body["error"]["type"] == "product_not_found"


# ---------------------------------------------------------------------------
# Database errors
# ---------------------------------------------------------------------------

class TestDatabaseErrors:
    @patch("src.lambda_code.update_product.update_product", side_effect=Exception("Connection timed out"))
    def test_returns_500_on_db_error(self, mock_update):
        response = handler(make_event(), None)

        assert response["statusCode"] == 500
        assert "Internal server error" in json.loads(response["body"])["error"]

    @patch("src.lambda_code.update_product.update_product", side_effect=Exception("ProvisionedThroughputExceededException"))
    def test_returns_500_on_throughput_exceeded(self, mock_update):
        response = handler(make_event(), None)

        assert response["statusCode"] == 500
