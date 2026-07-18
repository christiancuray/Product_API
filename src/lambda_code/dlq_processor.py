import json
import logging
import boto3

# Module-level logger and Lambda client reused across warm invocations
logger = logging.getLogger(__name__)
lambda_client = boto3.client('lambda')


def analyze_failure(failed_event: dict) -> dict:
    # take the error msg from the failed event and determine if it's retryble or not
    error_message = failed_event.get('errorMessage', '').lower()

    if 'timeout' in error_message or 'timed out' in error_message:
        return {'retryable': True, 'reason': 'timeout'}
    if 'rate limit' in error_message or 'throughput' in error_message:
        return {'retryable': True, 'reason': 'rate_limit'}
    if 'validation' in error_message:
        return {'retryable': False, 'reason': 'validation_error'}  # bad input, retrying won't help
    if 'not found' in error_message:
        return {'retryable': False, 'reason': 'resource_not_found'}  # resource gone, retrying won't help

    # Default to retryable for unknown errors to avoid silent data loss
    return {'retryable': True, 'reason': 'unknown'}


def handler(event, context):
    for record in event.get('Records', []):
        try:
            failed_event = json.loads(record['body'])
            analysis = analyze_failure(failed_event)

            logger.info(f"DLQ message received | reason={analysis['reason']} | retryable={analysis['retryable']}")

            if analysis['retryable']:
                source_function = failed_event.get('sourceFunction')
                if source_function:
                    # Async invoke so the processor doesn't block waiting for the retry result
                    lambda_client.invoke(
                        FunctionName=source_function,
                        InvocationType='Event',
                        Payload=json.dumps(failed_event.get('originalEvent', {}))
                    )
                    logger.info(f"Retried {source_function} successfully")
                else:
                    logger.warning("No sourceFunction in failed event — skipping retry")
            else:
                logger.error(f"Permanent failure, no retry | reason={analysis['reason']} | event={failed_event}")

        except Exception as e:
            # Log and continue so one bad record doesn't block the rest of the batch
            logger.exception(f"Error processing DLQ record: {str(e)}")
