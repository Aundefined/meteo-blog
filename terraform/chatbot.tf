# --- ECR ---

resource "aws_ecr_repository" "chatbot" {
  name                 = "${var.project_name}-chatbot"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "chatbot" {
  repository = aws_ecr_repository.chatbot.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Mantener últimas 10 imágenes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# --- Lambda ---

resource "aws_lambda_function" "chatbot" {
  function_name = "${var.project_name}-chatbot"
  role          = aws_iam_role.chatbot_lambda.arn
  package_type  = "Image"
  image_uri     = var.chatbot_image_uri
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      S3_BUCKET        = aws_s3_bucket.frontend.id
      BEDROCK_MODEL_ID = var.bedrock_model_id
      BEDROCK_REGION   = var.aws_region
    }
  }
}

resource "aws_cloudwatch_log_group" "chatbot" {
  name              = "/aws/lambda/${aws_lambda_function.chatbot.function_name}"
  retention_in_days = 14
}

# --- API Gateway HTTP API ---

resource "aws_apigatewayv2_api" "chatbot" {
  name          = "${var.project_name}-chatbot"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type"]
    max_age       = 86400
  }
}

resource "aws_apigatewayv2_stage" "chatbot" {
  api_id      = aws_apigatewayv2_api.chatbot.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "chatbot" {
  api_id                 = aws_apigatewayv2_api.chatbot.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.chatbot.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "chatbot" {
  api_id    = aws_apigatewayv2_api.chatbot.id
  route_key = "POST /"
  target    = "integrations/${aws_apigatewayv2_integration.chatbot.id}"
}

resource "aws_lambda_permission" "chatbot_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chatbot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.chatbot.execution_arn}/*/*"
}
