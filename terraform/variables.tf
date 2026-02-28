variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "domain_name" {
  description = "Root domain name for the project"
  type        = string
  default     = "acrohub.dance"
}

variable "app_name" {
  description = "Application name prefix for resource naming"
  type        = string
  default     = "acro-hub"
}

variable "cognito_callback_urls" {
  description = "List of allowed OAuth callback URLs for the Cognito app client"
  type        = list(string)
  default     = ["https://acrohub.dance/callback"]
}

variable "cognito_logout_urls" {
  description = "List of allowed OAuth logout URLs for the Cognito app client"
  type        = list(string)
  default     = ["https://acrohub.dance"]
}
