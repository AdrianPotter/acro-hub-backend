# ── Lambda zip archives (built outside Terraform) ────────────────────────────

data "local_file" "auth_zip_check" {
  filename = "${path.module}/../lambdas/auth/function.zip"
}

data "local_file" "moves_zip_check" {
  filename = "${path.module}/../lambdas/moves/function.zip"
}

data "local_file" "videos_zip_check" {
  filename = "${path.module}/../lambdas/videos/function.zip"
}

data "local_file" "events_zip_check" {
  filename = "${path.module}/../lambdas/events/function.zip"
}

data "local_file" "users_zip_check" {
  filename = "${path.module}/../lambdas/users/function.zip"
}

# ── Shared Lambda assume-role policy ─────────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ── Auth Lambda ───────────────────────────────────────────────────────────────

resource "aws_iam_role" "auth_lambda" {
  name               = "${var.app_name}-auth-lambda-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "auth_lambda_basic" {
  role       = aws_iam_role.auth_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "auth_lambda_cognito" {
  name = "${var.app_name}-auth-cognito-${var.environment}"
  role = aws_iam_role.auth_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:InitiateAuth",
          "cognito-idp:SignUp",
          "cognito-idp:ConfirmSignUp",
          "cognito-idp:GlobalSignOut",
          "cognito-idp:ForgotPassword",
          "cognito-idp:ConfirmForgotPassword",
          "cognito-idp:AdminUpdateUserAttributes",
        ]
        Resource = aws_cognito_user_pool.acro_hub.arn
      }
    ]
  })
}

resource "aws_lambda_function" "auth" {
  function_name = "${var.app_name}-auth-${var.environment}"
  role          = aws_iam_role.auth_lambda.arn
  filename      = "${path.module}/../lambdas/auth/function.zip"
  handler       = "handler.router"
  runtime       = "python3.14"
  timeout       = 30
  memory_size   = 256

  source_code_hash = filebase64sha256("${path.module}/../lambdas/auth/function.zip")

  environment {
    variables = {
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.acro_hub.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.acro_hub_client.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.auth_lambda]
}

# ── Moves Lambda ──────────────────────────────────────────────────────────────

resource "aws_iam_role" "moves_lambda" {
  name               = "${var.app_name}-moves-lambda-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "moves_lambda_basic" {
  role       = aws_iam_role.moves_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "moves_lambda_dynamodb" {
  name = "${var.app_name}-moves-dynamodb-${var.environment}"
  role = aws_iam_role.moves_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query",
        ]
        Resource = aws_dynamodb_table.moves.arn
      }
    ]
  })
}

resource "aws_lambda_function" "moves" {
  function_name = "${var.app_name}-moves-${var.environment}"
  role          = aws_iam_role.moves_lambda.arn
  filename      = "${path.module}/../lambdas/moves/function.zip"
  handler       = "handler.router"
  runtime       = "python3.14"
  timeout       = 30
  memory_size   = 256

  source_code_hash = filebase64sha256("${path.module}/../lambdas/moves/function.zip")

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.moves.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.moves_lambda]
}

# ── Videos Lambda ─────────────────────────────────────────────────────────────

resource "aws_iam_role" "videos_lambda" {
  name               = "${var.app_name}-videos-lambda-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "videos_lambda_basic" {
  role       = aws_iam_role.videos_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "videos_lambda_s3_dynamodb" {
  name = "${var.app_name}-videos-s3-ddb-${var.environment}"
  role = aws_iam_role.videos_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${aws_s3_bucket.videos.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.moves.arn
      }
    ]
  })
}

resource "aws_lambda_function" "videos" {
  function_name = "${var.app_name}-videos-${var.environment}"
  role          = aws_iam_role.videos_lambda.arn
  filename      = "${path.module}/../lambdas/videos/function.zip"
  handler       = "handler.router"
  runtime       = "python3.14"
  timeout       = 30
  memory_size   = 256

  source_code_hash = filebase64sha256("${path.module}/../lambdas/videos/function.zip")

  environment {
    variables = {
      VIDEO_BUCKET = aws_s3_bucket.videos.bucket
      MOVES_TABLE  = aws_dynamodb_table.moves.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.videos_lambda]
}

# ── Events Lambda ─────────────────────────────────────────────────────────────

resource "aws_iam_role" "events_lambda" {
  name               = "${var.app_name}-events-lambda-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "events_lambda_basic" {
  role       = aws_iam_role.events_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "events_lambda_dynamodb" {
  name = "${var.app_name}-events-dynamodb-${var.environment}"
  role = aws_iam_role.events_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.events.arn,
          "${aws_dynamodb_table.events.arn}/index/*",
        ]
      }
    ]
  })
}

resource "aws_lambda_function" "events" {
  function_name = "${var.app_name}-events-${var.environment}"
  role          = aws_iam_role.events_lambda.arn
  filename      = "${path.module}/../lambdas/events/function.zip"
  handler       = "handler.router"
  runtime       = "python3.14"
  timeout       = 30
  memory_size   = 256

  source_code_hash = filebase64sha256("${path.module}/../lambdas/events/function.zip")

  environment {
    variables = {
      EVENTS_TABLE = aws_dynamodb_table.events.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.events_lambda]
}

# ── Users Lambda ──────────────────────────────────────────────────────────────

resource "aws_iam_role" "users_lambda" {
  name               = "${var.app_name}-users-lambda-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "users_lambda_basic" {
  role       = aws_iam_role.users_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "users_lambda_cognito" {
  name = "${var.app_name}-users-cognito-${var.environment}"
  role = aws_iam_role.users_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:ListUsers",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminListGroupsForUser",
          "cognito-idp:AdminAddUserToGroup",
          "cognito-idp:AdminRemoveUserFromGroup",
          "cognito-idp:AdminDisableUser",
          "cognito-idp:AdminEnableUser",
          "cognito-idp:AdminDeleteUser",
        ]
        Resource = aws_cognito_user_pool.acro_hub.arn
      }
    ]
  })
}

resource "aws_lambda_function" "users" {
  function_name = "${var.app_name}-users-${var.environment}"
  role          = aws_iam_role.users_lambda.arn
  filename      = "${path.module}/../lambdas/users/function.zip"
  handler       = "handler.router"
  runtime       = "python3.14"
  timeout       = 30
  memory_size   = 256

  source_code_hash = filebase64sha256("${path.module}/../lambdas/users/function.zip")

  environment {
    variables = {
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.acro_hub.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.users_lambda]
}
