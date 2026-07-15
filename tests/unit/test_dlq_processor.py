import json
import pytest
from unittest.mock import patch, MagicMock

from src.lambda_code.dlq_processor import analyze_failure, handler


def make_record(body: dict) -> dict:
    return {"body": json.dumps(body)}


def make_event(*bodies: dict) -> dict:
    return {"Records": [make_record(b) for b in bodies]}


# ---------------------------------------------------------------------------
# analyze_failure
# ---------------------------------------------------------------------------

class TestAnalyzeFailure:
    def test_timeout_is_retryable(self):
        result = analyze_failure({"errorMessage": "Task timed out after 30 seconds"})
        assert result == {"retryable": True, "reason": "timeout"}

    def test_rate_limit_is_retryable(self):
        result = analyze_failure({"errorMessage": "Rate limit exceeded"})
        assert result == {"retryable": True, "reason": "rate_limit"}

    def test_throughput_exceeded_is_retryable(self):
        result = analyze_failure({"errorMessage": "ProvisionedThroughputExceededException"})
        assert result == {"retryable": True, "reason": "rate_limit"}

    def test_validation_error_is_not_retryable(self):
        result = analyze_failure({"errorMessage": "Validation failed for field price"})
        assert result == {"retryable": False, "reason": "validation_error"}

    def test_not_found_is_not_retryable(self):
        result = analyze_failure({"errorMessage": "Product not found"})
        assert result == {"retryable": False, "reason": "resource_not_found"}

    def test_unknown_error_is_retryable(self):
        result = analyze_failure({"errorMessage": "Something unexpected happened"})
        assert result == {"retryable": True, "reason": "unknown"}

    def test_missing_error_message_defaults_to_unknown(self):
        result = analyze_failure({})
        assert result == {"retryable": True, "reason": "unknown"}

    def test_case_insensitive_matching(self):
        result = analyze_failure({"errorMessage": "TIMEOUT occurred"})
        assert result["reason"] == "timeout"


# ---------------------------------------------------------------------------
# handler — retryable with sourceFunction
# ---------------------------------------------------------------------------

class TestHandlerRetry:
    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_invokes_source_function_on_retryable_error(self, mock_client):
        body = {
            "errorMessage": "Task timed out",
            "sourceFunction": "InsertProductFn",
            "originalEvent": {"body": '{"title": "Test"}'},
        }
        handler(make_event(body), None)

        mock_client.invoke.assert_called_once_with(
            FunctionName="InsertProductFn",
            InvocationType="Event",
            Payload=json.dumps(body["originalEvent"]),
        )

    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_skips_invoke_when_no_source_function(self, mock_client):
        body = {"errorMessage": "Task timed out"}
        handler(make_event(body), None)

        mock_client.invoke.assert_not_called()

    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_processes_multiple_records(self, mock_client):
        body = {
            "errorMessage": "timeout",
            "sourceFunction": "GetProductFn",
            "originalEvent": {},
        }
        handler(make_event(body, body), None)

        assert mock_client.invoke.call_count == 2


# ---------------------------------------------------------------------------
# handler — non-retryable
# ---------------------------------------------------------------------------

class TestHandlerPermanentFailure:
    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_does_not_invoke_lambda_on_validation_error(self, mock_client):
        body = {"errorMessage": "Validation failed", "sourceFunction": "InsertProductFn"}
        handler(make_event(body), None)

        mock_client.invoke.assert_not_called()

    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_does_not_invoke_lambda_on_not_found(self, mock_client):
        body = {"errorMessage": "Product not found", "sourceFunction": "GetProductFn"}
        handler(make_event(body), None)

        mock_client.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# handler — error resilience
# ---------------------------------------------------------------------------

class TestHandlerResilience:
    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_continues_processing_after_bad_record(self, mock_client):
        good_body = {
            "errorMessage": "timeout",
            "sourceFunction": "GetProductFn",
            "originalEvent": {},
        }
        bad_record = {"body": "{invalid json"}
        good_record = make_record(good_body)

        event = {"Records": [bad_record, good_record]}
        handler(event, None)

        # Bad record is swallowed, good record is still processed
        mock_client.invoke.assert_called_once()

    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_handles_empty_records(self, mock_client):
        handler({"Records": []}, None)
        mock_client.invoke.assert_not_called()

    @patch("src.lambda_code.dlq_processor.lambda_client")
    def test_lambda_invoke_failure_does_not_raise(self, mock_client):
        mock_client.invoke.side_effect = Exception("Lambda invoke failed")
        body = {
            "errorMessage": "timeout",
            "sourceFunction": "GetProductFn",
            "originalEvent": {},
        }
        # Should not raise
        handler(make_event(body), None)
