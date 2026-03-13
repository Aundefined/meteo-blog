resource "aws_ecr_repository" "fetcher" {
  name                 = "${var.project_name}-fetcher"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "fetcher" {
  repository = aws_ecr_repository.fetcher.name

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
