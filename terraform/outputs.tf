output "cloudfront_url" {
  description = "URL pública de la app"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "s3_bucket" {
  description = "Nombre del bucket S3 del frontend"
  value       = aws_s3_bucket.frontend.id
}

output "ecr_repository_url" {
  description = "URL del repositorio ECR"
  value       = aws_ecr_repository.fetcher.repository_url
}

output "lambda_function_name" {
  description = "Nombre de la Lambda"
  value       = aws_lambda_function.fetcher.function_name
}

output "github_actions_role_arn" {
  description = "ARN del rol para GitHub Actions"
  value       = aws_iam_role.github_actions.arn
}

output "chatbot_api_url" {
  description = "URL del API Gateway del chatbot"
  value       = aws_apigatewayv2_stage.chatbot.invoke_url
}
