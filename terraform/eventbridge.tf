resource "aws_scheduler_schedule" "fetcher" {
  name       = "${var.project_name}-fetcher-schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.fetch_schedule
  schedule_expression_timezone = "Europe/Madrid"

  target {
    arn      = aws_lambda_function.fetcher.arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}
