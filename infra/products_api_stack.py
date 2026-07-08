from aws_cdk import Stack, aws_lambda, aws_apigateway as apigw, aws_dynamodb as dynamodb

from constructs import Construct

class ProductApiStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table for products
        product_table = dynamodb.Table(
            self, "Products",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        # Define Lambda configuration
        lambda_runtime = aws_lambda.Runtime.PYTHON_3_12
        code_location = "src"

        # Create a Lambda Layer for dependencies (like pydantic)
        dependency_layer = aws_lambda.LayerVersion(self, "DependenciesLayer",
            code=aws_lambda.Code.from_asset("layer"),
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
            layers=[dependency_layer]
        )
        product_table.grant_read_data(self.get_product)

        
        self.query_products = aws_lambda.Function(self, "QueryProducts",
            runtime=lambda_runtime,
            handler="lambda_code.query_products.handler",
            code=aws_lambda.Code.from_asset(code_location),
            environment={
                "TABLE_NAME": product_table.table_name
            },
            layers=[dependency_layer]
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
            layers=[dependency_layer]
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
            layers=[dependency_layer]
        )
        product_table.grant_read_write_data(self.update_product)
        
        #  API Gateway endpoint mapping. stack connects the API Gateway to the Lambda functions
        api = apigw.RestApi(self, "ProductsAPI")

        products = api.root.add_resource("products")
        products.add_method("GET", apigw.LambdaIntegration(self.query_products))  # type: ignore
        products.add_method("POST", apigw.LambdaIntegration(self.insert_product))  # type: ignore
        
        product_by_id = products.add_resource("{id}")
        product_by_id.add_method("GET", apigw.LambdaIntegration(self.get_product))  # type: ignore
        product_by_id.add_method("PUT", apigw.LambdaIntegration(self.update_product))  # type: ignore

