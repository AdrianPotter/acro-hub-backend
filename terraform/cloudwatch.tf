# ── CloudWatch Log Groups ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "auth_lambda" {
  name              = "/aws/lambda/${var.app_name}-auth-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "moves_lambda" {
  name              = "/aws/lambda/${var.app_name}-moves-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "videos_lambda" {
  name              = "/aws/lambda/${var.app_name}-videos-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "events_lambda" {
  name              = "/aws/lambda/${var.app_name}-events-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "users_lambda" {
  name              = "/aws/lambda/${var.app_name}-users-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "user_move_lists_lambda" {
  name              = "/aws/lambda/${var.app_name}-user-move-lists-${var.environment}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.app_name}-${var.environment}"
  retention_in_days = 7
}

# ── API Gateway CloudWatch Logs Role ───────────────────────────────────────────

resource "aws_iam_role" "apigw_cloudwatch" {
  name = "${var.app_name}-apigw-cw-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "apigw_cloudwatch" {
  role       = aws_iam_role.apigw_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "acro_hub" {
  cloudwatch_role_arn = aws_iam_role.apigw_cloudwatch.arn

  depends_on = [
    aws_iam_role_policy_attachment.apigw_cloudwatch
  ]
}

# ── Dashboard ─────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "acro_hub" {
  dashboard_name = "${var.app_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      # Lambda Invocations
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title       = "Lambda Invocations"
          region      = var.aws_region
          annotations = {}
          period      = 300
          stat        = "Sum"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.app_name}-auth-${var.environment}", { label = "auth" }],
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.app_name}-moves-${var.environment}", { label = "moves" }],
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.app_name}-videos-${var.environment}", { label = "videos" }],
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.app_name}-events-${var.environment}", { label = "events" }],
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.app_name}-users-${var.environment}", { label = "users" }],
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.app_name}-user-move-lists-${var.environment}", { label = "user-move-lists" }],
          ]
          view = "timeSeries"
        }
      },
      # Lambda Errors
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title       = "Lambda Errors"
          region      = var.aws_region
          annotations = {}
          period      = 300
          stat        = "Sum"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", "${var.app_name}-auth-${var.environment}", { label = "auth", color = "#d62728" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${var.app_name}-moves-${var.environment}", { label = "moves", color = "#ff7f0e" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${var.app_name}-videos-${var.environment}", { label = "videos", color = "#9467bd" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${var.app_name}-events-${var.environment}", { label = "events", color = "#8c564b" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${var.app_name}-users-${var.environment}", { label = "users", color = "#e377c2" }],
            ["AWS/Lambda", "Errors", "FunctionName", "${var.app_name}-user-move-lists-${var.environment}", { label = "user-move-lists", color = "#17becf" }],
          ]
          view = "timeSeries"
        }
      },
      # API Gateway 4xx
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title       = "API Gateway 4xx Errors"
          region      = var.aws_region
          annotations = {}
          period      = 300
          stat        = "Sum"
          metrics = [
            ["AWS/ApiGateway", "4XXError", "ApiName", "${var.app_name}-api-${var.environment}", "Stage", var.environment],
          ]
          view = "timeSeries"
        }
      },
      # API Gateway 5xx
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title       = "API Gateway 5xx Errors"
          region      = var.aws_region
          annotations = {}
          period      = 300
          stat        = "Sum"
          metrics = [
            ["AWS/ApiGateway", "5XXError", "ApiName", "${var.app_name}-api-${var.environment}", "Stage", var.environment],
          ]
          view = "timeSeries"
        }
      },
      # DynamoDB Consumed Capacity
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          title       = "DynamoDB Consumed Read/Write Capacity"
          region      = var.aws_region
          annotations = {}
          period      = 300
          stat        = "Sum"
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "${var.app_name}-moves-${var.environment}", { label = "moves reads" }],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", "${var.app_name}-moves-${var.environment}", { label = "moves writes" }],
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "${var.app_name}-events-${var.environment}", { label = "events reads" }],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", "${var.app_name}-events-${var.environment}", { label = "events writes" }],
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "${var.app_name}-user-move-lists-${var.environment}", { label = "user-move-lists reads" }],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", "${var.app_name}-user-move-lists-${var.environment}", { label = "user-move-lists writes" }],
          ]
          view = "timeSeries"
        }
      },
    ]
  })
}

# ── Lambda Error Alarms ───────────────────────────────────────────────────────

locals {
  lambda_functions = ["auth", "moves", "videos", "events", "users", "user-move-lists"]
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(local.lambda_functions)

  alarm_name          = "${var.app_name}-${each.key}-high-errors-${var.environment}"
  alarm_description   = "More than 10 errors in 5 minutes on the ${each.key} Lambda"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.app_name}-${each.key}-${var.environment}"
  }
}

# ── API Gateway 5xx Alarm ─────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "apigw_5xx" {
  alarm_name          = "${var.app_name}-apigw-5xx-${var.environment}"
  alarm_description   = "API Gateway 5xx error rate spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = "${var.app_name}-api-${var.environment}"
    Stage   = var.environment
  }
}
