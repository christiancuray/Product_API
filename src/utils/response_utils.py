# response_utils.py - Response formatting
import json
from decimal import Decimal
from datetime import datetime

def create_success_response(status_code, data):
    """Create standardized success response for API Gateway"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data, default=decimal_serializer)
    }

def create_error_response(status_code, msg):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': msg}, default=decimal_serializer)
    }

def decimal_serializer(obj):
    """Handle Decimal objects in JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# ---------------------------------------------------------------------------
# Structured error response format
# ---------------------------------------------------------------------------

def create_structured_error_response(error_type, message, details=None, suggestions=None, request_id=None):
    """Create comprehensive error response for API consumers."""
    error_response = {
        'error': {
            'type': error_type,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'request_id': request_id
        }
    }
    
    if details:
        error_response['error']['details'] = details
    
    if suggestions:
        error_response['error']['suggestions'] = suggestions
    
    return error_response

# Usage examples for different error scenarios
def handle_product_validation_error(validation_errors):
    """Handle product validation failures with detailed feedback."""
    return create_structured_error_response(
        error_type='validation_error',
        message='Product data validation failed',
        details=validation_errors,
        suggestions=[
            'Check that all required fields are provided',
            'Ensure price is a positive number',
            'Verify category is from the allowed list'
        ]
    )

def handle_inventory_insufficient_error(product_id, requested, available):
    """Handle insufficient inventory with helpful guidance."""
    return create_structured_error_response(
        error_type='insufficient_inventory',
        message=f'Not enough inventory for product {product_id}',
        details={
            'requested_quantity': requested,
            'available_quantity': available
        },
        suggestions=[
            f'Reduce quantity to {available} or less',
            'Check back later for restocked inventory',
            'Consider similar products in the same category'
        ]
    )