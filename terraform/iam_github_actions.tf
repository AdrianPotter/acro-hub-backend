# ── GitHub Actions IAM User ───────────────────────────────────────────────────
# Programmatic user used by the GitHub Actions deploy workflow.
# After applying, retrieve the outputs and store them as GitHub repository
# secrets: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.

resource "aws_iam_user" "github_actions" {
  name = "${var.app_name}-github-actions-${var.environment}"

  tags = {
    Name = "${var.app_name}-github-actions-${var.environment}"
  }
}

resource "aws_iam_access_key" "github_actions" {
  user = aws_iam_user.github_actions.name
}

# ── Deployment Policy ─────────────────────────────────────────────────────────

resource "aws_iam_policy" "github_actions_deploy" {
  name        = "${var.app_name}-github-actions-deploy-${var.environment}"
  description = "Permissions required for the GitHub Actions deploy workflow to run terraform apply"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Terraform state – S3 backend
      {
        Sid    = "TerraformStateS3"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = [
          "arn:aws:s3:::${var.app_name}-terraform-state",
          "arn:aws:s3:::${var.app_name}-terraform-state/*",
        ]
      },
      # S3 – videos bucket management
      {
        Sid    = "S3VideosBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:GetBucketAcl",
          "s3:GetBucketCORS",
          "s3:GetLifecycleConfiguration",
          "s3:GetBucketLocation",
          "s3:GetBucketLogging",
          "s3:GetBucketObjectLockConfiguration",
          "s3:GetBucketPolicy",
          "s3:GetBucketPolicyStatus",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketRequestPayment",
          "s3:GetBucketTagging",
          "s3:GetBucketVersioning",
          "s3:GetAccelerateConfiguration",
          "s3:GetBucketWebsite",
          "s3:GetEncryptionConfiguration",
          "s3:PutBucketCORS",
          "s3:PutLifecycleConfiguration",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutBucketTagging",
          "s3:PutBucketVersioning",
          "s3:PutEncryptionConfiguration",
        ]
        Resource = "arn:aws:s3:::${var.app_name}-videos-${var.environment}"
      },
      # Lambda – function management
      {
        Sid    = "LambdaManagement"
        Effect = "Allow"
        Action = [
          "lambda:AddPermission",
          "lambda:CreateFunction",
          "lambda:DeleteFunction",
          "lambda:GetFunction",
          "lambda:GetFunctionCodeSigningConfig",
          "lambda:GetPolicy",
          "lambda:ListVersionsByFunction",
          "lambda:RemovePermission",
          "lambda:TagResource",
          "lambda:UntagResource",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:*:function:${var.app_name}-*"
      },
      # IAM – roles and policies for Lambda and API Gateway
      {
        Sid    = "IAMRolesAndPolicies"
        Effect = "Allow"
        Action = [
          "iam:AttachRolePolicy",
          "iam:CreatePolicy",
          "iam:CreateRole",
          "iam:DeletePolicy",
          "iam:DeleteRole",
          "iam:DeleteRolePolicy",
          "iam:DetachRolePolicy",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
          "iam:ListPolicies",
          "iam:ListPolicyVersions",
          "iam:ListRolePolicies",
          "iam:PassRole",
          "iam:PutRolePolicy",
          "iam:TagPolicy",
          "iam:TagRole",
          "iam:UntagPolicy",
          "iam:UntagRole",
          "iam:UpdateAssumeRolePolicy",
        ]
        Resource = [
          "arn:aws:iam::*:role/${var.app_name}-*",
          "arn:aws:iam::*:policy/${var.app_name}-*",
        ]
      },
      # IAM – read access keys for the github-actions user itself (needed by Terraform to manage the access key resource)
      {
        Sid    = "IAMGithubActionsUser"
        Effect = "Allow"
        Action = [
          "iam:CreateAccessKey",
          "iam:CreateUser",
          "iam:DeleteAccessKey",
          "iam:DeleteUser",
          "iam:GetUser",
          "iam:ListAccessKeys",
          "iam:TagUser",
          "iam:UntagUser",
          "iam:AttachUserPolicy",
          "iam:DetachUserPolicy",
          "iam:ListAttachedUserPolicies",
          "iam:ListUserPolicies",
        ]
        Resource = "arn:aws:iam::*:user/${var.app_name}-*"
      },
      # API Gateway – REST API management
      {
        Sid    = "APIGatewayManagement"
        Effect = "Allow"
        Action = [
          "apigateway:DELETE",
          "apigateway:GET",
          "apigateway:PATCH",
          "apigateway:POST",
          "apigateway:PUT",
        ]
        Resource = "arn:aws:apigateway:${var.aws_region}::/*"
      },
      # Cognito – user pool management
      {
        Sid    = "CognitoManagement"
        Effect = "Allow"
        Action = [
          "cognito-idp:CreateGroup",
          "cognito-idp:CreateUserPool",
          "cognito-idp:CreateUserPoolClient",
          "cognito-idp:CreateUserPoolDomain",
          "cognito-idp:DeleteGroup",
          "cognito-idp:DeleteUserPool",
          "cognito-idp:DeleteUserPoolClient",
          "cognito-idp:DeleteUserPoolDomain",
          "cognito-idp:DescribeUserPool",
          "cognito-idp:DescribeUserPoolClient",
          "cognito-idp:DescribeUserPoolDomain",
          "cognito-idp:GetGroup",
          "cognito-idp:GetUserPoolMfaConfig",
          "cognito-idp:ListGroups",
          "cognito-idp:ListTagsForResource",
          "cognito-idp:ListUserPoolClients",
          "cognito-idp:ListUserPools",
          "cognito-idp:TagResource",
          "cognito-idp:UntagResource",
          "cognito-idp:UpdateGroup",
          "cognito-idp:UpdateUserPool",
          "cognito-idp:UpdateUserPoolClient",
        ]
        Resource = "*"
      },
      # DynamoDB – table management
      {
        Sid    = "DynamoDBManagement"
        Effect = "Allow"
        Action = [
          "dynamodb:CreateTable",
          "dynamodb:DeleteTable",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:DescribeTable",
          "dynamodb:DescribeTimeToLive",
          "dynamodb:ListTagsOfResource",
          "dynamodb:TagResource",
          "dynamodb:UntagResource",
          "dynamodb:UpdateContinuousBackups",
          "dynamodb:UpdateTable",
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/${var.app_name}-*"
      },
      # CloudWatch Logs – DescribeLogGroups is a list-level API that AWS evaluates
      # against the account/region scope, so it requires Resource: "*".
      {
        Sid    = "CloudWatchLogsDescribe"
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      },
      # CloudWatch Logs – log group management (scoped to app-owned log groups)
      {
        Sid    = "CloudWatchLogsManagement"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:ListTagsForResource",
          "logs:ListTagsLogGroup",
          "logs:PutRetentionPolicy",
          "logs:TagLogGroup",
          "logs:TagResource",
          "logs:UntagLogGroup",
          "logs:UntagResource",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/*"
      },
      # CloudWatch – metric alarms and dashboards
      {
        Sid    = "CloudWatchAlarmsAndDashboards"
        Effect = "Allow"
        Action = [
          "cloudwatch:DeleteAlarms",
          "cloudwatch:DeleteDashboards",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:GetDashboard",
          "cloudwatch:ListTagsForResource",
          "cloudwatch:PutDashboard",
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:TagResource",
          "cloudwatch:UntagResource",
        ]
        Resource = "*"
      },
      # Route 53 – record management (existing hosted zone)
      {
        Sid    = "Route53RecordManagement"
        Effect = "Allow"
        Action = [
          "route53:ChangeResourceRecordSets",
          "route53:GetChange",
          "route53:GetHostedZone",
          "route53:ListHostedZones",
          "route53:ListResourceRecordSets",
          "route53:ListTagsForResource",
        ]
        Resource = "*"
      },
      # ACM – certificate management
      {
        Sid    = "ACMCertificateManagement"
        Effect = "Allow"
        Action = [
          "acm:AddTagsToCertificate",
          "acm:DeleteCertificate",
          "acm:DescribeCertificate",
          "acm:ListCertificates",
          "acm:ListTagsForCertificate",
          "acm:RemoveTagsFromCertificate",
          "acm:RequestCertificate",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_user_policy_attachment" "github_actions_deploy" {
  user       = aws_iam_user.github_actions.name
  policy_arn = aws_iam_policy.github_actions_deploy.arn
}
