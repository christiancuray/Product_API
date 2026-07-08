# products_db.py - Database operations
import boto3
import boto3.dynamodb.conditions
import uuid
import os
from decimal import Decimal
from typing import Any, cast

from botocore.exceptions import ClientError

dynamodb = cast(Any, boto3.resource('dynamodb'))

def get_table():
    table_name = os.environ.get('TABLE_NAME') or 'Products'
    return dynamodb.Table(table_name)

def _sanitize_id(product_id) -> str:
    """Validate and sanitize a product ID before use in a DynamoDB key."""
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError(f"Invalid product_id: {product_id!r}")
    return product_id.strip()

def get_product(product_id):
    """Retrieve a single product by ID"""
    safe_id = _sanitize_id(product_id)
    table = get_table()
    try:
        item = table.get_item(Key={'id': safe_id}).get('Item')
    except Exception:
        # Fallback for backward compatibility if product_id key exists
        try:
            item = table.get_item(Key={'product_id': safe_id}).get('Item')
        except Exception:
            item = None
    
    if item is None:
        return None
    if 'price' in item and isinstance(item['price'], Decimal):
        item['price'] = float(item['price'])
    return item

def insert_product(item, user_arn):
    """Create a new product with generated UUID"""
    # add user to created by
    item['created_by'] = user_arn
    item['updated_by'] = user_arn

    if 'price' in item and isinstance(item['price'], float):
        item['price'] = Decimal(str(item['price']))

    # Ensure required fields exist
    if 'version' not in item:
        item['version'] = 1
    if 'created_at' not in item:
        from datetime import datetime
        item['created_at'] = datetime.now().isoformat() + 'Z'
    if 'updated_at' not in item:
        item['updated_at'] = item['created_at']

    return get_table().put_item(Item=item)

def update_product(product_id, fields, user_arn):
    """Update an existing product. Fails if product doesn't exist."""
    from datetime import datetime
    safe_id = _sanitize_id(product_id)
    
    # Fields are already validated by Pydantic before reaching this function
    timestamp = datetime.now().isoformat() + 'Z'
    
    update_expression = "SET category = :category, title = :title, description = :description, price = :price, updated_at = :updated_at, updated_by = :updated_by"

    expression_attribute_values = {
        ':category': fields['category'],
        ':title': fields['title'],
        ':description': fields['description'],
        ':price': Decimal(str(fields['price'])) if isinstance(fields['price'], float) else fields['price'],
        ':updated_at': timestamp,
        ':updated_by': user_arn
    }
    
    try:
        # Use condition to ensure product exists before updating
        response = get_table().update_item(
            Key={'id': safe_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression='attribute_exists(id)',
            ReturnValues='ALL_NEW'
        )
        return response['Attributes']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ValueError(f"Product with id {product_id} does not exist")
        raise

def update_product_with_version(product_id, fields, user_arn, expected_version):
    """Update product with optimistic locking using version number"""
    from datetime import datetime
    safe_id = _sanitize_id(product_id)   

    
    timestamp = datetime.now().isoformat() + 'Z'
    new_version = expected_version + 1
    
    update_expression = "SET category = :category, title = :title, description = :description, price = :price, updated_at = :updated_at, updated_by = :updated_by, version = :new_version"
    
    expression_attribute_values = {
        ':category': fields['category'],
        ':title': fields['title'],
        ':description': fields['description'],
        ':price': Decimal(str(fields['price'])) if isinstance(fields['price'], float) else fields['price'],
        ':updated_at': timestamp,
        ':updated_by': user_arn,
        ':new_version': new_version,
        ':expected_version': expected_version
    }
    
    try:
        response = get_table().update_item(
            Key={'id': safe_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression='attribute_exists(id) AND version = :expected_version',
            ReturnValues='ALL_NEW'
        )
        return response['Attributes']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ValueError(f"Product was modified by another user. Please refresh and try again.")
        raise

def get_all_products():
    """Retrieve all products from the table"""
    items = get_table().scan()['Items']
    for item in items:
        if 'price' in item and isinstance(item['price'], Decimal):
            item['price'] = float(item['price'])
    return items

def get_products_by_category(category):
    """Query products by category using GSI"""
    items = get_table().query(
        IndexName='category-index',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('category').eq(category)
    ).get('Items')
    for item in items:
        if 'price' in item and isinstance(item['price'], Decimal):
            item['price'] = float(item['price'])
    return items