terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Using local backend for simplicity. For production, use S3:
  # backend "s3" {
  #   bucket = "stock-pipeline-terraform-state"
  #   key    = "infrastructure/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "stock-pipeline"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
