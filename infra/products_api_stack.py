import os
from aws_cdk import Stack, aws_lambda, aws_apigateway as apigw, aws_dynamodb as dynamodb, aws_sqs as sqs, Duration
from aws_cdk import aws_iam as iam
from aws_cdk.aws_lambda_event_sources import SqsEventSource

from constructs import Construct

# the repo root relative to this file so asset paths work from any working directory
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")

class ProductApiStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for products
        product_table = dynamodb.Table(
            self, "Products",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        # Dead-letter queue for failed Lambda invocations
        dlq = sqs.Queue(
            self, "ProductApiDLQ",
            queue_name="product-api-dlq",
            retention_period=Duration.days(14), # 14 days
            visibility_timeout=Duration.minutes(5), # 5 mins
            receive_message_wait_time=Duration.seconds(20), # 20 seconds
        )

        # Shared runtime and code location for all Lambda functions
        lambda_runtime = aws_lambda.Runtime.PYTHON_3_12
        code_location = os.path.join(ROOT_DIR, "src")

        # Create a Lambda Layer for dependencies (like pydantic)
        dependency_layer = aws_lambda.LayerVersion(self, "DependenciesLayer",
            code=aws_lambda.Code.from_asset(os.path.join(ROOT_DIR, "layer")),
            compatible_runtimes=[lambda_runtime],
            description="Layer containing Pydantic and other dependencies"
        )

        # Create Lambda function for product retrieval
        self.get_product = aws_lambda.Function(self, "GetProduct",
            runtime=lambda_runtime,
            handler="lambda_code.get_product.handler",
            code=aws_lambda.Code.from_asset(code_location),
            environment={
                "TABLE_NAME": product_table.table_name
            },
            layers=[dependency_layer],
            dead_letter_queue=dlq  # sends failed async invocations to DLQ
        )
        product_table.grant_read_data(self.get_product)

        # Create Lambda function for querying products by category or listing all
        self.query_products = aws_lambda.Function(self, "QueryProducts",
            runtime=lambda_runtime,
            handler="lambda_code.query_products.handler",
            code=aws_lambda.Code.from_asset(code_location),
            environment={
                "TABLE_NAME": product_table.table_name
            },
            layers=[dependency_layer],
            dead_letter_queue=dlq  # sends failed async invocations to DLQ
        )
        product_table.grant_read_data(self.query_products)

        # Create Lambda function for product creation
        self.insert_product = aws_lambda.Function(self, "InsertProduct",
            runtime=lambda_runtime,
            handler="lambda_code.insert_product.handler",
            code=aws_lambda.Code.from_asset(code_location),
            environment={
                "TABLE_NAME": product_table.table_name
            },
            layers=[dependency_layer],
            dead_letter_queue=dlq  # sends failed async invocations to DLQ
        )
        product_table.grant_read_write_data(self.insert_product)

        # Create Lambda function for product updates
        self.update_product = aws_lambda.Function(self, "UpdateProduct",
            runtime=lambda_runtime,
            handler="lambda_code.update_product.handler",
            code=aws_lambda.Code.from_asset(code_location),   
            environment={
                "TABLE_NAME": product_table.table_name
            },
            layers=[dependency_layer],
            dead_letter_queue=dlq  # sends failed async invocations to DLQ
        )
        product_table.grant_read_write_data(self.update_product)
        
        # DLQ processor Lambda — triggered by messages in the DLQ
        dlq_processor = aws_lambda.Function(self, "DlqProcessor",
            runtime=lambda_runtime,
            handler="lambda_code.dlq_processor.handler",
            code=aws_lambda.Code.from_asset(code_location),
            layers=[dependency_layer]
        )
        # Automatically trigger DlqProcessor when messages arrive in the DLQ, up to 10 at a time
        dlq_processor.add_event_source(SqsEventSource(dlq, batch_size=10))

        # Allow DLQ processor to invoke other Lambda functions for retry
        dlq_processor.add_to_role_policy(iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=[self.get_product.function_arn, self.query_products.function_arn,
                       self.insert_product.function_arn, self.update_product.function_arn]
        ))

        # API Gateway REST API — routes HTTP requests to the appropriate Lambda functions
        api = apigw.RestApi(self, "ProductsAPI")

        # /products — GET lists all, POST creates a new product
        products = api.root.add_resource("products")
        products.add_method("GET", apigw.LambdaIntegration(self.query_products))  # type: ignore
        products.add_method("POST", apigw.LambdaIntegration(self.insert_product))  # type: ignore
        
        # /products/{id} — GET retrieves one, PUT updates one
        product_by_id = products.add_resource("{id}")
        product_by_id.add_method("GET", apigw.LambdaIntegration(self.get_product))  # type: ignore
        product_by_id.add_method("PUT", apigw.LambdaIntegration(self.update_product))  # type: ignore
