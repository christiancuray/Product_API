from utils.response_utils import create_structured_error_response


class ContextualErrorHandler:
    """Generate context-aware error messages for better user experience."""

    def __init__(self, user_context=None):
        self.user_context = user_context or {}

    def handle_product_not_found(self, product_id, request_id=None):
        """Generate helpful message for missing products."""
        suggestions = ['Verify the product ID is correct']

        if self.user_context.get('search_term'):
            suggestions.append(f'Try searching for "{self.user_context["search_term"]}" to find similar products')

        if self.user_context.get('category'):
            suggestions.append(f'Browse other products in {self.user_context["category"]} category')

        return create_structured_error_response(
            error_type='product_not_found',
            message=f'Product {product_id} is not available',
            suggestions=suggestions,
            request_id=request_id
        )

    def handle_checkout_error(self, error_details):
        """Generate helpful checkout error messages."""
        if error_details.get('payment_failed'):
            return create_structured_error_response(
                error_type='payment_error',
                message='Payment processing failed',
                suggestions=[
                    'Verify your payment information is correct',
                    'Check that your card has sufficient funds',
                    'Try a different payment method',
                    'Contact your bank if the problem persists'
                ]
            )
        elif error_details.get('address_invalid'):
            return create_structured_error_response(
                error_type='address_error',
                message='Shipping address validation failed',
                details=error_details['address_errors'],
                suggestions=[
                    'Verify your address is complete and accurate',
                    'Check that postal code matches your city/state',
                    'Ensure we deliver to your location'
                ]
            )
