# ── REST API ──────────────────────────────────────────────────────────────────

resource "aws_api_gateway_rest_api" "acro_hub" {
  name        = "${var.app_name}-api-${var.environment}"
  description = "Acro Hub backend REST API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# ── Cognito Authorizer ────────────────────────────────────────────────────────

resource "aws_api_gateway_authorizer" "cognito" {
  name          = "cognito-authorizer"
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  type          = "COGNITO_USER_POOLS"
  provider_arns = [aws_cognito_user_pool.acro_hub.arn]

  identity_source = "method.request.header.Authorization"
}

# ── Lambda permissions ────────────────────────────────────────────────────────

resource "aws_lambda_permission" "auth_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.acro_hub.execution_arn}/*/*"
}

resource "aws_lambda_permission" "moves_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.moves.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.acro_hub.execution_arn}/*/*"
}

resource "aws_lambda_permission" "videos_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.videos.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.acro_hub.execution_arn}/*/*"
}

resource "aws_lambda_permission" "events_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.events.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.acro_hub.execution_arn}/*/*"
}

resource "aws_lambda_permission" "users_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.users.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.acro_hub.execution_arn}/*/*"
}

resource "aws_lambda_permission" "user_move_lists_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.user_move_lists.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.acro_hub.execution_arn}/*/*"
}

# ── /auth resource ────────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_rest_api.acro_hub.root_resource_id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "auth_login" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login"
}

resource "aws_api_gateway_resource" "auth_logout" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "logout"
}

resource "aws_api_gateway_resource" "auth_register" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "register"
}

resource "aws_api_gateway_resource" "auth_forgot_password" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "forgot-password"
}

resource "aws_api_gateway_resource" "auth_confirm_registration" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "confirm-registration"
}

resource "aws_api_gateway_resource" "auth_confirm_password" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "confirm-password"
}

resource "aws_api_gateway_resource" "auth_refresh" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "refresh"
}

# ── /auth/login POST ──────────────────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_login_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_login.id
  http_method             = aws_api_gateway_method.auth_login_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

# ── /auth/login OPTIONS (CORS) ────────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_login_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_login_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_login_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.auth_login_options.http_method
  status_code = aws_api_gateway_method_response.auth_login_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_login_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /auth/logout POST ─────────────────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_logout_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_logout.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_logout_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_logout.id
  http_method             = aws_api_gateway_method.auth_logout_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

resource "aws_api_gateway_method" "auth_logout_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_logout.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_logout_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_logout.id
  http_method = aws_api_gateway_method.auth_logout_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_logout_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_logout.id
  http_method = aws_api_gateway_method.auth_logout_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_logout_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_logout.id
  http_method = aws_api_gateway_method.auth_logout_options.http_method
  status_code = aws_api_gateway_method_response.auth_logout_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_logout_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /auth/register POST ───────────────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_register_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_register.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_register_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_register.id
  http_method             = aws_api_gateway_method.auth_register_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

resource "aws_api_gateway_method" "auth_register_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_register.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_register_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_register.id
  http_method = aws_api_gateway_method.auth_register_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_register_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_register.id
  http_method = aws_api_gateway_method.auth_register_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_register_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_register.id
  http_method = aws_api_gateway_method.auth_register_options.http_method
  status_code = aws_api_gateway_method_response.auth_register_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_register_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /auth/forgot-password POST ────────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_forgot_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_forgot_password.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_forgot_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_forgot_password.id
  http_method             = aws_api_gateway_method.auth_forgot_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

resource "aws_api_gateway_method" "auth_forgot_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_forgot_password.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_forgot_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_forgot_password.id
  http_method = aws_api_gateway_method.auth_forgot_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_forgot_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_forgot_password.id
  http_method = aws_api_gateway_method.auth_forgot_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_forgot_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_forgot_password.id
  http_method = aws_api_gateway_method.auth_forgot_options.http_method
  status_code = aws_api_gateway_method_response.auth_forgot_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_forgot_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /auth/confirm-registration POST ───────────────────────────────────────────

resource "aws_api_gateway_method" "auth_confirm_registration_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_confirm_registration.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_confirm_registration_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_confirm_registration.id
  http_method             = aws_api_gateway_method.auth_confirm_registration_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

resource "aws_api_gateway_method" "auth_confirm_registration_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_confirm_registration.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_confirm_registration_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_confirm_registration.id
  http_method = aws_api_gateway_method.auth_confirm_registration_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_confirm_registration_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_confirm_registration.id
  http_method = aws_api_gateway_method.auth_confirm_registration_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_confirm_registration_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_confirm_registration.id
  http_method = aws_api_gateway_method.auth_confirm_registration_options.http_method
  status_code = aws_api_gateway_method_response.auth_confirm_registration_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_confirm_registration_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /auth/confirm-password POST ───────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_confirm_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_confirm_password.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_confirm_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_confirm_password.id
  http_method             = aws_api_gateway_method.auth_confirm_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

resource "aws_api_gateway_method" "auth_confirm_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_confirm_password.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_confirm_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_confirm_password.id
  http_method = aws_api_gateway_method.auth_confirm_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_confirm_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_confirm_password.id
  http_method = aws_api_gateway_method.auth_confirm_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_confirm_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_confirm_password.id
  http_method = aws_api_gateway_method.auth_confirm_options.http_method
  status_code = aws_api_gateway_method_response.auth_confirm_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_confirm_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /auth/refresh POST ────────────────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_refresh_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_refresh.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_refresh_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.auth_refresh.id
  http_method             = aws_api_gateway_method.auth_refresh_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.auth.arn}/invocations"
}

# ── /auth/refresh OPTIONS (CORS) ──────────────────────────────────────────────

resource "aws_api_gateway_method" "auth_refresh_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.auth_refresh.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_refresh_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_refresh.id
  http_method = aws_api_gateway_method.auth_refresh_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "auth_refresh_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_refresh.id
  http_method = aws_api_gateway_method.auth_refresh_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "auth_refresh_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.auth_refresh.id
  http_method = aws_api_gateway_method.auth_refresh_options.http_method
  status_code = aws_api_gateway_method_response.auth_refresh_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.auth_refresh_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /moves resource ───────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "moves" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_rest_api.acro_hub.root_resource_id
  path_part   = "moves"
}

resource "aws_api_gateway_resource" "moves_id" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.moves.id
  path_part   = "{id}"
}

# GET /moves

resource "aws_api_gateway_method" "moves_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "moves_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.moves.id
  http_method             = aws_api_gateway_method.moves_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.moves.arn}/invocations"
}

# POST /moves

resource "aws_api_gateway_method" "moves_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "moves_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.moves.id
  http_method             = aws_api_gateway_method.moves_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.moves.arn}/invocations"
}

# OPTIONS /moves (CORS)

resource "aws_api_gateway_method" "moves_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "moves_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.moves.id
  http_method = aws_api_gateway_method.moves_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "moves_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.moves.id
  http_method = aws_api_gateway_method.moves_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "moves_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.moves.id
  http_method = aws_api_gateway_method.moves_options.http_method
  status_code = aws_api_gateway_method_response.moves_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.moves_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# GET /moves/{id}

resource "aws_api_gateway_method" "moves_id_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves_id.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "moves_id_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.moves_id.id
  http_method             = aws_api_gateway_method.moves_id_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.moves.arn}/invocations"
}

# PUT /moves/{id}

resource "aws_api_gateway_method" "moves_id_put" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves_id.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "moves_id_put" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.moves_id.id
  http_method             = aws_api_gateway_method.moves_id_put.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.moves.arn}/invocations"
}

# PATCH /moves/{id}

resource "aws_api_gateway_method" "moves_id_patch" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves_id.id
  http_method   = "PATCH"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "moves_id_patch" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.moves_id.id
  http_method             = aws_api_gateway_method.moves_id_patch.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.moves.arn}/invocations"
}

# DELETE /moves/{id}

resource "aws_api_gateway_method" "moves_id_delete" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves_id.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "moves_id_delete" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.moves_id.id
  http_method             = aws_api_gateway_method.moves_id_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.moves.arn}/invocations"
}

# OPTIONS /moves/{id} (CORS)

resource "aws_api_gateway_method" "moves_id_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.moves_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "moves_id_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.moves_id.id
  http_method = aws_api_gateway_method.moves_id_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "moves_id_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.moves_id.id
  http_method = aws_api_gateway_method.moves_id_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "moves_id_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.moves_id.id
  http_method = aws_api_gateway_method.moves_id_options.http_method
  status_code = aws_api_gateway_method_response.moves_id_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.moves_id_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,PUT,PATCH,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /videos resource ──────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "videos" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_rest_api.acro_hub.root_resource_id
  path_part   = "videos"
}

resource "aws_api_gateway_resource" "videos_move_id" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.videos.id
  path_part   = "{moveId}"
}

resource "aws_api_gateway_resource" "videos_url" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.videos_move_id.id
  path_part   = "url"
}

resource "aws_api_gateway_resource" "videos_upload_url" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.videos_move_id.id
  path_part   = "upload-url"
}

# GET /videos/{moveId}/url

resource "aws_api_gateway_method" "videos_url_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.videos_url.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "videos_url_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.videos_url.id
  http_method             = aws_api_gateway_method.videos_url_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.videos.arn}/invocations"
}

resource "aws_api_gateway_method" "videos_url_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.videos_url.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "videos_url_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.videos_url.id
  http_method = aws_api_gateway_method.videos_url_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "videos_url_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.videos_url.id
  http_method = aws_api_gateway_method.videos_url_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "videos_url_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.videos_url.id
  http_method = aws_api_gateway_method.videos_url_options.http_method
  status_code = aws_api_gateway_method_response.videos_url_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.videos_url_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# POST /videos/{moveId}/upload-url

resource "aws_api_gateway_method" "videos_upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.videos_upload_url.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "videos_upload_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.videos_upload_url.id
  http_method             = aws_api_gateway_method.videos_upload_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.videos.arn}/invocations"
}

resource "aws_api_gateway_method" "videos_upload_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.videos_upload_url.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "videos_upload_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.videos_upload_url.id
  http_method = aws_api_gateway_method.videos_upload_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "videos_upload_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.videos_upload_url.id
  http_method = aws_api_gateway_method.videos_upload_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "videos_upload_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.videos_upload_url.id
  http_method = aws_api_gateway_method.videos_upload_options.http_method
  status_code = aws_api_gateway_method_response.videos_upload_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.videos_upload_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /events resource ──────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "events" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_rest_api.acro_hub.root_resource_id
  path_part   = "events"
}

# GET /events

resource "aws_api_gateway_method" "events_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "events_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.events.id
  http_method             = aws_api_gateway_method.events_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.events.arn}/invocations"
}

# POST /events

resource "aws_api_gateway_method" "events_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "events_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.events.id
  http_method             = aws_api_gateway_method.events_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.events.arn}/invocations"
}

# OPTIONS /events (CORS)

resource "aws_api_gateway_method" "events_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "events_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.events_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "events_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.events_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "events_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.events_options.http_method
  status_code = aws_api_gateway_method_response.events_options_200.status_code

  depends_on = [
    aws_api_gateway_integration.events_options
  ]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /users resource ───────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "users" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_rest_api.acro_hub.root_resource_id
  path_part   = "users"
}

resource "aws_api_gateway_resource" "users_username" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.users.id
  path_part   = "{username}"
}

resource "aws_api_gateway_resource" "users_username_groups" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.users_username.id
  path_part   = "groups"
}

resource "aws_api_gateway_resource" "users_username_disable" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.users_username.id
  path_part   = "disable"
}

resource "aws_api_gateway_resource" "users_username_enable" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.users_username.id
  path_part   = "enable"
}

# GET /users

resource "aws_api_gateway_method" "users_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "users_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.users.id
  http_method             = aws_api_gateway_method.users_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.users.arn}/invocations"
}

# OPTIONS /users (CORS)

resource "aws_api_gateway_method" "users_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "users_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users.id
  http_method = aws_api_gateway_method.users_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "users_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users.id
  http_method = aws_api_gateway_method.users_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "users_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users.id
  http_method = aws_api_gateway_method.users_options.http_method
  status_code = aws_api_gateway_method_response.users_options_200.status_code

  depends_on = [aws_api_gateway_integration.users_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# GET /users/{username}

resource "aws_api_gateway_method" "users_username_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "users_username_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.users_username.id
  http_method             = aws_api_gateway_method.users_username_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.users.arn}/invocations"
}

# DELETE /users/{username}

resource "aws_api_gateway_method" "users_username_delete" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "users_username_delete" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.users_username.id
  http_method             = aws_api_gateway_method.users_username_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.users.arn}/invocations"
}

# OPTIONS /users/{username} (CORS)

resource "aws_api_gateway_method" "users_username_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "users_username_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username.id
  http_method = aws_api_gateway_method.users_username_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "users_username_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username.id
  http_method = aws_api_gateway_method.users_username_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "users_username_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username.id
  http_method = aws_api_gateway_method.users_username_options.http_method
  status_code = aws_api_gateway_method_response.users_username_options_200.status_code

  depends_on = [aws_api_gateway_integration.users_username_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# PUT /users/{username}/groups

resource "aws_api_gateway_method" "users_username_groups_put" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username_groups.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "users_username_groups_put" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.users_username_groups.id
  http_method             = aws_api_gateway_method.users_username_groups_put.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.users.arn}/invocations"
}

# OPTIONS /users/{username}/groups (CORS)

resource "aws_api_gateway_method" "users_username_groups_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username_groups.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "users_username_groups_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_groups.id
  http_method = aws_api_gateway_method.users_username_groups_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "users_username_groups_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_groups.id
  http_method = aws_api_gateway_method.users_username_groups_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "users_username_groups_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_groups.id
  http_method = aws_api_gateway_method.users_username_groups_options.http_method
  status_code = aws_api_gateway_method_response.users_username_groups_options_200.status_code

  depends_on = [aws_api_gateway_integration.users_username_groups_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,PUT'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# POST /users/{username}/disable

resource "aws_api_gateway_method" "users_username_disable_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username_disable.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "users_username_disable_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.users_username_disable.id
  http_method             = aws_api_gateway_method.users_username_disable_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.users.arn}/invocations"
}

# OPTIONS /users/{username}/disable (CORS)

resource "aws_api_gateway_method" "users_username_disable_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username_disable.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "users_username_disable_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_disable.id
  http_method = aws_api_gateway_method.users_username_disable_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "users_username_disable_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_disable.id
  http_method = aws_api_gateway_method.users_username_disable_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "users_username_disable_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_disable.id
  http_method = aws_api_gateway_method.users_username_disable_options.http_method
  status_code = aws_api_gateway_method_response.users_username_disable_options_200.status_code

  depends_on = [aws_api_gateway_integration.users_username_disable_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# POST /users/{username}/enable

resource "aws_api_gateway_method" "users_username_enable_post" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username_enable.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "users_username_enable_post" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.users_username_enable.id
  http_method             = aws_api_gateway_method.users_username_enable_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.users.arn}/invocations"
}

# OPTIONS /users/{username}/enable (CORS)

resource "aws_api_gateway_method" "users_username_enable_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.users_username_enable.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "users_username_enable_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_enable.id
  http_method = aws_api_gateway_method.users_username_enable_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "users_username_enable_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_enable.id
  http_method = aws_api_gateway_method.users_username_enable_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "users_username_enable_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.users_username_enable.id
  http_method = aws_api_gateway_method.users_username_enable_options.http_method
  status_code = aws_api_gateway_method_response.users_username_enable_options_200.status_code

  depends_on = [aws_api_gateway_integration.users_username_enable_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── /me resource ─────────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "me" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_rest_api.acro_hub.root_resource_id
  path_part   = "me"
}

resource "aws_api_gateway_resource" "me_moves" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.me.id
  path_part   = "moves"
}

resource "aws_api_gateway_resource" "me_moves_list_type" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.me_moves.id
  path_part   = "{listType}"
}

resource "aws_api_gateway_resource" "me_moves_list_type_move_id" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  parent_id   = aws_api_gateway_resource.me_moves_list_type.id
  path_part   = "{moveId}"
}

# GET /me/moves/{listType}

resource "aws_api_gateway_method" "me_moves_list_type_get" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.me_moves_list_type.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "me_moves_list_type_get" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.me_moves_list_type.id
  http_method             = aws_api_gateway_method.me_moves_list_type_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.user_move_lists.arn}/invocations"
}

# OPTIONS /me/moves/{listType} (CORS)

resource "aws_api_gateway_method" "me_moves_list_type_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.me_moves_list_type.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "me_moves_list_type_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.me_moves_list_type.id
  http_method = aws_api_gateway_method.me_moves_list_type_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "me_moves_list_type_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.me_moves_list_type.id
  http_method = aws_api_gateway_method.me_moves_list_type_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "me_moves_list_type_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.me_moves_list_type.id
  http_method = aws_api_gateway_method.me_moves_list_type_options.http_method
  status_code = aws_api_gateway_method_response.me_moves_list_type_options_200.status_code

  depends_on = [aws_api_gateway_integration.me_moves_list_type_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# PUT /me/moves/{listType}/{moveId}

resource "aws_api_gateway_method" "me_moves_list_type_move_id_put" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "me_moves_list_type_move_id_put" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method             = aws_api_gateway_method.me_moves_list_type_move_id_put.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.user_move_lists.arn}/invocations"
}

# DELETE /me/moves/{listType}/{moveId}

resource "aws_api_gateway_method" "me_moves_list_type_move_id_delete" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "me_moves_list_type_move_id_delete" {
  rest_api_id             = aws_api_gateway_rest_api.acro_hub.id
  resource_id             = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method             = aws_api_gateway_method.me_moves_list_type_move_id_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.user_move_lists.arn}/invocations"
}

# OPTIONS /me/moves/{listType}/{moveId} (CORS)

resource "aws_api_gateway_method" "me_moves_list_type_move_id_options" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  resource_id   = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "me_moves_list_type_move_id_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method = aws_api_gateway_method.me_moves_list_type_move_id_options.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "me_moves_list_type_move_id_options_200" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method = aws_api_gateway_method.me_moves_list_type_move_id_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "me_moves_list_type_move_id_options" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id
  resource_id = aws_api_gateway_resource.me_moves_list_type_move_id.id
  http_method = aws_api_gateway_method.me_moves_list_type_move_id_options.http_method
  status_code = aws_api_gateway_method_response.me_moves_list_type_move_id_options_200.status_code

  depends_on = [aws_api_gateway_integration.me_moves_list_type_move_id_options]

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ── Gateway Responses (CORS on auth errors) ───────────────────────────────────
#
# When API Gateway rejects a request at the authorizer level (missing/invalid
# JWT), it generates a 401 or 403 response itself — before the Lambda
# integration is ever called.  These gateway-level responses do not
# automatically inherit the CORS headers that the Lambda would have returned,
# so browsers block them with "No Access-Control-Allow-Origin header present".
#
# The resources below attach the necessary CORS headers to those gateway-
# generated error responses so that the browser can read the error body.

resource "aws_api_gateway_gateway_response" "unauthorized" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,PATCH,DELETE'"
  }

  response_templates = {
    "application/json" = "{\"message\": $context.error.messageString}"
  }
}

resource "aws_api_gateway_gateway_response" "access_denied" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  response_type = "ACCESS_DENIED"
  status_code   = "403"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'OPTIONS,GET,POST,PUT,PATCH,DELETE'"
  }

  response_templates = {
    "application/json" = "{\"message\": $context.error.messageString}"
  }
}

# ── Deployment & Stage ────────────────────────────────────────────────────────

resource "aws_api_gateway_deployment" "acro_hub" {
  rest_api_id = aws_api_gateway_rest_api.acro_hub.id

  # Force redeploy when any method/integration/gateway-response changes
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_method.auth_login_post,
      aws_api_gateway_method.auth_logout_post,
      aws_api_gateway_method.auth_register_post,
      aws_api_gateway_method.auth_forgot_post,
      aws_api_gateway_method.auth_confirm_registration_post,
      aws_api_gateway_method.auth_confirm_post,
      aws_api_gateway_method.auth_refresh_post,
      aws_api_gateway_method.moves_get,
      aws_api_gateway_method.moves_post,
      aws_api_gateway_method.moves_id_get,
      aws_api_gateway_method.moves_id_put,
      aws_api_gateway_method.moves_id_patch,
      aws_api_gateway_method.moves_id_delete,
      aws_api_gateway_method.videos_url_get,
      aws_api_gateway_method.videos_upload_post,
      aws_api_gateway_method.events_get,
      aws_api_gateway_method.events_post,
      aws_api_gateway_method.users_get,
      aws_api_gateway_method.users_username_get,
      aws_api_gateway_method.users_username_delete,
      aws_api_gateway_method.users_username_groups_put,
      aws_api_gateway_method.users_username_disable_post,
      aws_api_gateway_method.users_username_enable_post,
      aws_api_gateway_method.me_moves_list_type_get,
      aws_api_gateway_method.me_moves_list_type_move_id_put,
      aws_api_gateway_method.me_moves_list_type_move_id_delete,
      aws_api_gateway_gateway_response.unauthorized,
      aws_api_gateway_gateway_response.access_denied,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "acro_hub" {
  rest_api_id   = aws_api_gateway_rest_api.acro_hub.id
  deployment_id = aws_api_gateway_deployment.acro_hub.id
  stage_name    = var.environment

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format         = "$context.requestId $context.extendedRequestId $context.identity.sourceIp $context.requestTime $context.httpMethod $context.resourcePath $context.protocol $context.status $context.responseLength $context.error.message $context.error.messageString"
  }

  xray_tracing_enabled = true

  depends_on = [
    aws_api_gateway_account.acro_hub
  ]
}

# ── Custom Domain ─────────────────────────────────────────────────────────────

resource "aws_api_gateway_domain_name" "acro_hub" {
  domain_name              = "api.${var.domain_name}"
  regional_certificate_arn = aws_acm_certificate.api.arn

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  depends_on = [aws_acm_certificate_validation.api]
}

resource "aws_api_gateway_base_path_mapping" "acro_hub" {
  api_id      = aws_api_gateway_rest_api.acro_hub.id
  stage_name  = aws_api_gateway_stage.acro_hub.stage_name
  domain_name = aws_api_gateway_domain_name.acro_hub.domain_name
}
