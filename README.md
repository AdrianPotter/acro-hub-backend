# Acro Hub Backend

Backend API for [Acro Hub](https://github.com/AdrianPotter/acro-hub-frontend) — a website for browsing partner acrobatic moves.

## Architecture

```
                        ┌─────────────────────────────────────────────────┐
                        │                   AWS Cloud                      │
                        │                                                  │
  Browser / SPA  ──────▶│  Route 53 (api.acrohub.org)                   │
                        │       │                                          │
                        │       ▼                                          │
                        │  API Gateway (REST)                              │
                        │       │                                          │
                        │       ├── Cognito Authorizer (JWT validation)    │
                        │       │                                          │
                        │       ├── /auth/*  ──▶ Lambda: auth              │
                        │       │                    │                     │
                        │       │                    ▼                     │
                        │       │             Cognito User Pool            │
                        │       │                                          │
                        │       ├── /moves/* ──▶ Lambda: moves             │
                        │       │                    │                     │
                        │       │                    ▼                     │
                        │       │             DynamoDB: acro-hub-moves     │
                        │       │                                          │
                        │       ├── /videos/*──▶ Lambda: videos            │
                        │       │                    │                     │
                        │       │          ┌─────────┴──────────┐          │
                        │       │          ▼                     ▼         │
                        │       │    S3 Videos Bucket    DynamoDB: moves   │
                        │       │    (pre-signed URLs)                     │
                        │       │                                          │
                        │       └── /events/*──▶ Lambda: events            │
                        │                            │                     │
                        │                            ▼                     │
                        │                    DynamoDB: acro-hub-events     │
                        │                                                  │
                        │  CloudWatch (dashboards & alarms)                │
                        └─────────────────────────────────────────────────┘
```

## Prerequisites

- **Python 3.14** — runtime for all Lambda functions and local tests
- **pip** — Python package manager
- **Terraform >= 1.5.0** — infrastructure provisioning
- **AWS CLI** configured with credentials that have sufficient permissions
- **pytest** — test runner (`pip install pytest`)

## Project Structure

```
acro-hub-backend/
├── PROMPT.md               # Original project brief
├── README.md               # This file
├── .gitignore
├── .github/
│   └── workflows/
│       └── deploy.yml      # CI/CD: package Lambdas + terraform apply on merge to main
├── lambdas/
│   ├── auth/               # Cognito authentication Lambda
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── moves/              # Acro-move metadata CRUD Lambda
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── videos/             # S3 pre-signed URL Lambda
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── events/             # Event-tracking Lambda
│       ├── handler.py
│       └── requirements.txt
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_moves.py
│   ├── test_videos.py
│   └── test_events.py
├── terraform/
│   ├── main.tf             # Provider & backend config
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cognito.tf
│   ├── dynamodb.tf
│   ├── s3.tf
│   ├── lambda.tf
│   ├── api_gateway.tf
│   ├── route53.tf
│   └── cloudwatch.tf
└── openapi/
    └── api.yaml            # OpenAPI 3.0 specification
```

## Local Development

### 1. Create and activate a virtual environment

```bash
python3.14 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows
```

### 2. Install dependencies for all Lambdas

```bash
pip install -r lambdas/auth/requirements.txt
pip install -r lambdas/moves/requirements.txt
pip install -r lambdas/videos/requirements.txt
pip install -r lambdas/events/requirements.txt
pip install pytest
```

### 3. Environment variables for local testing

Create a `.env.local` file (git-ignored) with the following, then source it before running tests:

```bash
export COGNITO_USER_POOL_ID=eu-west-1_XXXXXXXXX
export COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
export DYNAMODB_TABLE=acro-hub-moves-dev
export EVENTS_TABLE=acro-hub-events-dev
export VIDEO_BUCKET=acro-hub-videos-dev
export MOVES_TABLE=acro-hub-moves-dev
export AWS_DEFAULT_REGION=eu-west-1
```

```bash
source .env.local
```

### 4. Run unit tests

```bash
pytest tests/ -v
```

All Lambda business logic is fully unit-tested with mocked AWS SDK calls — no real AWS resources are required.

## Automated Deployment (GitHub Actions)

A workflow at `.github/workflows/deploy.yml` runs automatically on every push to `main`. It:

1. Packages each Lambda (`auth`, `moves`, `videos`, `events`) into a `function.zip` with its pip dependencies.
2. Runs `terraform init` → `terraform plan` → `terraform apply -auto-approve -var="environment=prod"` to deploy all infrastructure and Lambda code changes.

### Required repository secrets

The workflow authenticates with AWS using two repository secrets. Add them once under **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Access key ID for a dedicated deploy IAM user |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret access key |

### Minimum IAM permissions

The IAM user (or role) used by the workflow needs at least the following permissions:

| AWS service | Required actions |
|---|---|
| **S3** | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` on the Terraform state bucket (`acro-hub-terraform-state`) and the videos bucket |
| **Lambda** | `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:GetFunction`, `lambda:DeleteFunction`, `lambda:AddPermission`, `lambda:RemovePermission`, `lambda:ListTags`, `lambda:TagResource`, `lambda:UntagResource` |
| **IAM** | `iam:CreateRole`, `iam:DeleteRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRole`, `iam:GetRolePolicy`, `iam:PassRole`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:ListInstanceProfilesForRole`, `iam:TagRole`, `iam:UntagRole` |
| **API Gateway** | `apigateway:*` on the relevant REST APIs |
| **Cognito** | `cognito-idp:*` on the user pool |
| **DynamoDB** | `dynamodb:CreateTable`, `dynamodb:DeleteTable`, `dynamodb:DescribeTable`, `dynamodb:UpdateTable`, `dynamodb:ListTagsOfResource`, `dynamodb:TagResource`, `dynamodb:UntagResource` |
| **CloudWatch** | `logs:CreateLogGroup`, `logs:DeleteLogGroup`, `logs:PutRetentionPolicy`, `logs:DescribeLogGroups`, `logs:ListTagsLogGroup`, `logs:TagLogGroup`, `logs:UntagLogGroup` |
| **Route 53** | `route53:ChangeResourceRecordSets`, `route53:ListResourceRecordSets`, `route53:GetHostedZone` |
| **ACM** | `acm:RequestCertificate`, `acm:DescribeCertificate`, `acm:DeleteCertificate`, `acm:AddTagsToCertificate`, `acm:ListTagsForCertificate` |

> **Tip:** For a quick start you can attach the AWS-managed `AdministratorAccess` policy to the deploy user, then scope it down to the minimum permissions above once everything is working.

### Adding the secrets in GitHub

1. Go to the repository on GitHub.
2. Click **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** for each secret in the table above.
4. Paste the value and click **Add secret**.

Once both secrets are present, the next push to `main` will trigger a full deploy automatically.

---

## Deployment

### First-time setup — Terraform S3 state backend

The state bucket must exist before Terraform can initialise. Create it once:

```bash
aws s3api create-bucket \
  --bucket acro-hub-terraform-state \
  --region eu-west-1 \
  --create-bucket-configuration LocationConstraint=eu-west-1

aws s3api put-bucket-versioning \
  --bucket acro-hub-terraform-state \
  --versioning-configuration Status=Enabled
```

### Package Lambda functions

Each Lambda is deployed as a zip archive. Package them before `terraform apply`:

**Windows (PowerShell):**

```powershell
foreach ($svc in @("auth", "moves", "videos", "events")) {
  cd lambdas/$svc
  pip install -r requirements.txt -t package/
  Copy-Item handler.py package/
  Compress-Archive -Path package/* -DestinationPath function.zip -Force
  Remove-Item -Recurse -Force package
  cd ../..
}
```

### Terraform init / plan / apply

```bash
cd terraform

terraform init

# Review the plan before applying
terraform plan -var="environment=dev"

# Deploy
terraform apply -var="environment=dev"
```

For production:

```bash
terraform apply -var="environment=prod"
```

### Post-deployment: note key outputs

```bash
terraform output api_gateway_url
terraform output cognito_user_pool_id
terraform output cognito_client_id
terraform output videos_bucket_name
```

Use the `cognito_client_id` in the front-end SPA configuration.

## API Usage

Replace `<TOKEN>` with a valid Cognito JWT obtained after login.

### Register a new user

```bash
curl -X POST https://api.acrohub.org/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Password1!","name":"Jane Doe"}'
```

### Login

```bash
curl -X POST https://api.acrohub.org/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Password1!"}'
```

### List moves (authenticated)

```bash
curl https://api.acrohub.org/moves \
  -H "Authorization: Bearer <TOKEN>"
```

### Get a single move

```bash
curl https://api.acrohub.org/moves/<moveId> \
  -H "Authorization: Bearer <TOKEN>"
```

### Create a move

```bash
curl -X POST https://api.acrohub.org/moves \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Star",
    "description": "Classic acrobalance star pose",
    "difficulty": "easy",
    "category": "acrobalance",
    "tags": ["static","beginner"],
    "alternateNames": ["Star Pose", "Side Star"]
  }'
```

### Get a pre-signed video URL

```bash
curl "https://api.acrohub.org/videos/<moveId>/url" \
  -H "Authorization: Bearer <TOKEN>"
```

### Get a pre-signed upload URL

```bash
curl -X POST "https://api.acrohub.org/videos/<moveId>/upload-url" \
  -H "Authorization: Bearer <TOKEN>"
```

Then upload directly to S3 using the returned `uploadUrl`:

```bash
curl -X PUT "<uploadUrl>" \
  -H "Content-Type: video/mp4" \
  --data-binary @my-video.mp4
```

### Track an event

```bash
curl -X POST https://api.acrohub.org/events \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"eventType":"move_view","resourceId":"<moveId>"}'
```

## Configuration

All tuneable Terraform inputs live in `terraform/variables.tf`. The most common overrides:

| Variable | Default | Description |
|---|---|---|
| `aws_region` | `eu-west-1` | AWS region for all resources |
| `environment` | `dev` | Deployment environment tag |
| `domain_name` | `acrohub.org` | Root domain for Route 53 |
| `app_name` | `acro-hub` | Prefix for resource names |
| `cognito_callback_urls` | `["https://acrohub.org/callback"]` | OAuth callback URLs |
| `cognito_logout_urls` | `["https://acrohub.org"]` | OAuth logout URLs |

Pass overrides at apply time or create a `terraform.tfvars` file (git-ignored by default).

## Monitoring

A CloudWatch dashboard named **acro-hub-\<environment\>** is deployed automatically. It shows:

- Lambda invocation counts and error rates per function
- API Gateway 4xx / 5xx rates
- DynamoDB consumed read/write capacity

Alarms are configured for:

- Lambda error count > 10 in any 5-minute window (per function)
- API Gateway 5xx rate spike

View the dashboard in the AWS Console → CloudWatch → Dashboards.
