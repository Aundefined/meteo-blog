resource "aws_lambda_function" "fetcher" {
  function_name = "${var.project_name}-fetcher"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  timeout       = 300
  memory_size   = 256

  environment {
    variables = {
      AEMET_API_KEY             = var.aemet_api_key
      S3_BUCKET                 = aws_s3_bucket.frontend.id
      CLOUDFRONT_DISTRIBUTION_ID = aws_cloudfront_distribution.frontend.id
      BEDROCK_MODEL_ID = var.bedrock_model_id
      BEDROCK_REGION   = var.aws_region
    }
  }
}

resource "aws_cloudwatch_log_group" "fetcher" {
  name              = "/aws/lambda/${aws_lambda_function.fetcher.function_name}"
  retention_in_days = 14
}
