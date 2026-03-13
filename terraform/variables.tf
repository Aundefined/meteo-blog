variable "aws_region" {
  description = "Región AWS"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Nombre del proyecto, usado como prefijo en los recursos"
  type        = string
  default     = "meteo-blog"
}

variable "image_uri" {
  description = "URI de la imagen Docker en ECR para la Lambda"
  type        = string
}

variable "aemet_api_key" {
  description = "API key de AEMET OpenData"
  type        = string
  sensitive   = true
}

variable "bedrock_model_id" {
  description = "ID del modelo Bedrock"
  type        = string
  default     = "eu.amazon.nova-micro-v1:0"
}

variable "github_repo" {
  description = "Repo de GitHub en formato usuario/repo"
  type        = string
  default     = "Aundefined/meteo-blog"
}

variable "fetch_schedule" {
  description = "Expresión cron para EventBridge (UTC)"
  type        = string
  default     = "cron(0 5,9,13,17 * * ? *)"  # 6h, 10h, 14h, 18h hora España (invierno)
}
