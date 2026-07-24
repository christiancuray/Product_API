import logging

from aws_cdk import Duration, RemovalPolicy, aws_s3 as s3
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
        lifecycle_rules=[
            s3.LifecycleRule(
                id="ProductImageLifecycle",
                enabled=True,
                prefix="products/",
                expiration=Duration.days(2555),
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                        transition_after=Duration.days(30),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER,
                        transition_after=Duration.days(90),
                    ),
                ],
            )
        ],
    )

    logger.info("Created S3 bucket %s", bucket.bucket_name)
    return bucket