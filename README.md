# Acro Hub Backend

Backend API for [Acro Hub](https://github.com/AdrianPotter/acro-hub-frontend) — a website for browsing partner acrobatic moves.

## Architecture

```
                        ┌─────────────────────────────────────────────────┐
                        │                   AWS Cloud                      │
                        │                                                  │
  Browser / SPA  ──────▶│  Route 53 (api.acrohub.dance)                   │
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

- **Python 3.11** — runtime for all Lambda functions and local tests
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
python3.11 -m venv .venv
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

```bash
for svc in auth moves videos events; do
  cd lambdas/$svc
  pip install -r requirements.txt -t package/
  cp handler.py package/
  cd package && zip -r ../function.zip . && cd ..
  rm -rf package
  cd ../..
done
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
curl -X POST https://api.acrohub.dance/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Password1!","name":"Jane Doe"}'
```

### Login

```bash
curl -X POST https://api.acrohub.dance/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Password1!"}'
```

### List moves (authenticated)

```bash
curl https://api.acrohub.dance/moves \
  -H "Authorization: Bearer <TOKEN>"
```

### Get a single move

```bash
curl https://api.acrohub.dance/moves/<moveId> \
  -H "Authorization: Bearer <TOKEN>"
```

### Create a move

```bash
curl -X POST https://api.acrohub.dance/moves \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Star",
    "description": "Classic acrobalance star pose",
    "difficulty": "easy",
    "category": "acrobalance",
    "tags": ["static","beginner"]
  }'
```

### Get a pre-signed video URL

```bash
curl "https://api.acrohub.dance/videos/<moveId>/url" \
  -H "Authorization: Bearer <TOKEN>"
```

### Get a pre-signed upload URL

```bash
curl -X POST "https://api.acrohub.dance/videos/<moveId>/upload-url" \
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
curl -X POST https://api.acrohub.dance/events \
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
| `domain_name` | `acrohub.dance` | Root domain for Route 53 |
| `app_name` | `acro-hub` | Prefix for resource names |
| `cognito_callback_urls` | `["https://acrohub.dance/callback"]` | OAuth callback URLs |
| `cognito_logout_urls` | `["https://acrohub.dance"]` | OAuth logout URLs |

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
