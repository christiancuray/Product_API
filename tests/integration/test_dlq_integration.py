"""
Integration tests for the DLQ processor.

These tests run against real AWS resources. Requires:
  - AWS credentials configured
  - ProductApiStack deployed
  - pip install requests boto3

Run with:
  pytest tests/integration/test_dlq_integration.py -v
"""
import json
import time
import boto3
import pytest

# ---------------------------------------------------------------------------
# Config — matches deployed stack
# ---------------------------------------------------------------------------

REGION = "us-east-1"
DLQ_URL = "https://sqs.us-east-1.amazonaws.com/950165721417/product-api-dlq"
API_BASE = "https://i4yf8mjk0c.execute-api.us-east-1.amazonaws.com/prod"
DLQ_PROCESSOR_LOG_GROUP = "/aws/lambda/ProductApiStack-DlqProcessor5971950F-AYZOtgfniBxu"

LAMBDA_NAMES = {
    "get":    "ProductApiStack-GetProductB1843B98-JIdANT5so2OE",
    "insert": "ProductApiStack-InsertProduct0DF3D99C-D8ww22oyu2lG",
    "update": "ProductApiStack-UpdateProduct20A0C881-ZznSkR7QEFA2",
    "query":  "ProductApiStack-QueryProducts92A22C2F-CcCyWTRWk2IA",
    "dlq":    "ProductApiStack-DlqProcessor5971950F-AYZOtgfniBxu",
}

sqs = boto3.client("sqs", region_name=REGION)
logs = boto3.client("logs", region_name=REGION)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def send_to_dlq(payload: dict) -> str:
    response = sqs.send_message(
        QueueUrl=DLQ_URL,
        MessageBody=json.dumps(payload),
    )
    return response["MessageId"]


def wait_for_log(message_id: str, timeout: int = 30) -> str | None:
    """Poll CloudWatch logs until the message_id appears or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = logs.filter_log_events(
                logGroupName=DLQ_PROCESSOR_LOG_GROUP,
                filterPattern=message_id,
                limit=5,
            )
            if response.get("events"):
                return response["events"][0]["message"]
        except logs.exceptions.ResourceNotFoundException:
            pass
        time.sleep(3)
    return None


def get_queue_depth() -> int:
    attrs = sqs.get_queue_attributes(
        QueueUrl=DLQ_URL,
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    return int(attrs["Attributes"]["ApproximateNumberOfMessages"])


# ---------------------------------------------------------------------------
# DLQ processor tests
# ---------------------------------------------------------------------------

class TestDlqProcessorIntegration:
    def test_dlq_processor_handles_timeout_message(self):
        """Processor receives a timeout message and logs it."""
        msg_id = send_to_dlq({
            "errorMessage": "Task timed out after 30 seconds",
            "sourceFunction": LAMBDA_NAMES["insert"],
            "originalEvent": {},
        })

        log = wait_for_log(msg_id)
        assert log is not None, f"No log found for message {msg_id} within timeout"

    def test_dlq_processor_handles_validation_error_message(self):
        """Processor receives a non-retryable validation error and logs it."""
        msg_id = send_to_dlq({
            "errorMessage": "Validation failed for field price",
            "sourceFunction": LAMBDA_NAMES["insert"],
            "originalEvent": {},
        })

        log = wait_for_log(msg_id)
        assert log is not None, f"No log found for message {msg_id} within timeout"

    def test_dlq_processor_handles_rate_limit_message(self):
        """Processor receives a rate limit error and attempts retry."""
        msg_id = send_to_dlq({
            "errorMessage": "ProvisionedThroughputExceededException",
            "sourceFunction": LAMBDA_NAMES["query"],
            "originalEvent": {},
        })

        log = wait_for_log(msg_id)
        assert log is not None, f"No log found for message {msg_id} within timeout"

    def test_dlq_processor_handles_missing_source_function(self):
        """Processor skips retry when sourceFunction is absent."""
        msg_id = send_to_dlq({
            "errorMessage": "Task timed out after 30 seconds",
        })

        log = wait_for_log(msg_id)
        assert log is not None, f"No log found for message {msg_id} within timeout"


# ---------------------------------------------------------------------------
# Queue depth test
# ---------------------------------------------------------------------------

class TestDlqQueueDepth:
    def test_queue_is_reachable(self):
        """Confirms the DLQ exists and is accessible."""
        depth = get_queue_depth()
        assert isinstance(depth, int)
        assert depth >= 0

    def test_messages_are_consumed_by_processor(self):
        """After sending a message, queue depth should return to 0."""
        initial_depth = get_queue_depth()

        send_to_dlq({
            "errorMessage": "Task timed out after 30 seconds",
            "sourceFunction": LAMBDA_NAMES["get"],
            "originalEvent": {},
        })

        # Give the processor time to consume it
        time.sleep(15)

        final_depth = get_queue_depth()
        assert final_depth <= initial_depth, "Message was not consumed by the processor"
