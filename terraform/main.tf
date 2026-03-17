terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "meteo-blog-tfstate-483874865128-euw1"
    key     = "terraform.tfstate"
    region  = "eu-west-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project = "meteo-blog"
    }
  }
}

# ACM para CloudFront requiere us-east-1 obligatoriamente
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      project = "meteo-blog"
    }
  }
}
