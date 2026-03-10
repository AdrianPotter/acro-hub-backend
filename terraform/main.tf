terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.34.0"
    }
  }

  backend "s3" {
    bucket = "acro-hub-terraform-state"
    key    = "backend/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "acro-hub"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Provider in us-east-1 required for ACM certificates used with API Gateway edge-optimised endpoints
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "acro-hub"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
