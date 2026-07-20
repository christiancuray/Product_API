import logging

from aws_cdk import RemovalPolicy, aws_s3 as s3
from constructs import Construct

logger = logging.getLogger(__name__)

def create_product_images_bucket(scope: Construct, id: str) -> s3.Bucket:
    bucket = s3.Bucket(
        scope,
        id,
        bucket_name="products-api-assets",
        versioned=True,
        block_public_access=s3.BlockPublicAccess(
            block_public_acls=True,
            ignore_public_acls=True,
            block_public_policy=False,
            restrict_public_buckets=False,
        ),
        encryption=s3.BucketEncryption.S3_MANAGED,
        removal_policy=RemovalPolicy.DESTROY,
        auto_delete_objects=True,
    )

    logger.info("Created S3 bucket %s", bucket.bucket_name)
    return bucket