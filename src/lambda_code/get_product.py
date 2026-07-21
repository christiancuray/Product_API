# get_product.py - Handler for GET /products/{id}
import logging
import os

import boto3
from botocore.exceptions import ClientError

from db.products_db import get_product
from utils.context_error_handler import ContextualErrorHandler
from utils.response_utils import create_error_response, create_success_response

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3')


def _attach_download_url(product):
    image_key = product.get('image_key') or product.get('imageUrl') or product.get('image_url')
    if not image_key:
        return product

    if isinstance(image_key, str) and image_key.startswith('http'):
        product['download_url'] = image_key
        return product

    bucket_name = os.environ.get('S3_BUCKET_NAME')
    if not bucket_name:
        return product

    try:
        product['download_url'] = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': image_key},
            ExpiresIn=3600,
        )
    except ClientError as exc:
        logger.warning("Could not generate download URL", extra={"error": str(exc), "key": image_key})

    return product


def handler(event, context):
    logger.debug("get_product invoked", extra={
        "request_id": getattr(context, "aws_request_id", None),
        "path": event.get("path"),
        "body": event.get("body")
    })

    try:
        path_parameters = event.get('pathParameters') or {}
        product_id = path_parameters.get('id')

        if not product_id:
            logger.error("Product id is missing in path parameters", extra={"path_parameters": path_parameters})
            return create_error_response(400, 'Product id is required')

        product = get_product(product_id)
        if product:
            product = _attach_download_url(product)
            logger.info("Product found", extra={"product_id": product_id})
            return create_success_response(200, product)

        request_id = getattr(context, 'aws_request_id', None)
        query_params = event.get('queryStringParameters') or {}
        user_context = {k: v for k, v in {
            'search_term': query_params.get('q'),
            'category': query_params.get('category'),
        }.items() if v}
        
        logger.warning("Product not found", extra={"product_id": product_id, "user_context": user_context})
        error_body = ContextualErrorHandler(user_context).handle_product_not_found(product_id, request_id)
        error_payload = error_body.get('error', error_body) if isinstance(error_body, dict) else error_body
        return create_error_response(404, error_payload)

    except Exception as e:
        logger.exception(f"Unexpected error while getting product: {str(e)}")
        return create_error_response(500, f'Internal server error - {str(e)}')
