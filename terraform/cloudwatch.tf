resource "aws_cloudwatch_dashboard" "meteo_blog" {
  dashboard_name = var.project_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = "# meteo-blog — Observabilidad\nMétricas de producción: **fetcher** (5 ejecuciones/día vía EventBridge) y **chatbot** (bajo demanda vía API Gateway)."
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 8
        height = 6
        properties = {
          title   = "Fetcher — Invocaciones"
          metrics = [["AWS/Lambda", "Invocations", "FunctionName", "${var.project_name}-fetcher", { stat = "Sum", period = 86400, label = "Invocaciones/día" }]]
          view    = "timeSeries"
          region  = var.aws_region
          period  = 86400
          yAxis   = { left = { min = 0 } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 2
        width  = 8
        height = 6
        properties = {
          title   = "Fetcher — Duración (ms)"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "${var.project_name}-fetcher", { stat = "Average", period = 86400, label = "Media" }],
            ["AWS/Lambda", "Duration", "FunctionName", "${var.project_name}-fetcher", { stat = "Maximum", period = 86400, label = "Máximo" }]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 86400
          yAxis  = { left = { min = 0 } }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 2
        width  = 8
        height = 6
        properties = {
          title   = "Fetcher — Errores"
          metrics = [["AWS/Lambda", "Errors", "FunctionName", "${var.project_name}-fetcher", { stat = "Sum", period = 86400, label = "Errores/día", color = "#d62728" }]]
          view    = "timeSeries"
          region  = var.aws_region
          period  = 86400
          yAxis   = { left = { min = 0 } }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 8
        height = 6
        properties = {
          title   = "Chatbot — Invocaciones"
          metrics = [["AWS/Lambda", "Invocations", "FunctionName", "${var.project_name}-chatbot", { stat = "Sum", period = 86400, label = "Invocaciones/día" }]]
          view    = "timeSeries"
          region  = var.aws_region
          period  = 86400
          yAxis   = { left = { min = 0 } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 8
        width  = 8
        height = 6
        properties = {
          title   = "Chatbot — Duración (ms)"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "${var.project_name}-chatbot", { stat = "Average", period = 86400, label = "Media" }],
            ["AWS/Lambda", "Duration", "FunctionName", "${var.project_name}-chatbot", { stat = "Maximum", period = 86400, label = "Máximo" }]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 86400
          yAxis  = { left = { min = 0 } }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 8
        width  = 8
        height = 6
        properties = {
          title   = "Chatbot — Errores"
          metrics = [["AWS/Lambda", "Errors", "FunctionName", "${var.project_name}-chatbot", { stat = "Sum", period = 86400, label = "Errores/día", color = "#d62728" }]]
          view    = "timeSeries"
          region  = var.aws_region
          period  = 86400
          yAxis   = { left = { min = 0 } }
        }
      }
    ]
  })
}
