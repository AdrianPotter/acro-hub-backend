output "api_gateway_url" {
  description = "Base URL of the deployed API Gateway stage"
  value       = "https://${aws_api_gateway_rest_api.acro_hub.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
}

output "api_custom_domain_url" {
  description = "Custom domain URL for the API"
  value       = "https://api.${var.domain_name}"
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.acro_hub.id
}

output "cognito_client_id" {
  description = "Cognito app client ID (used by the front-end SPA)"
  value       = aws_cognito_user_pool_client.acro_hub_client.id
}

output "videos_bucket_name" {
  description = "Name of the S3 bucket used for video storage"
  value       = aws_s3_bucket.videos.bucket
}

output "route53_name_servers" {
  description = "Name servers for the Route 53 hosted zone (add these to your domain registrar)"
  value       = aws_route53_zone.acro_hub.name_servers
}
