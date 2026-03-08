# Acro Hub - Project Prompt

I've started building a project called "Acro Hub". It provides a website where you can browse partner acrobatic moves based on various characteristics.

The project has the following characteristics:

- A front end single-page-application deployed on an AWS S3 bucket. This is already contained in a separate repository: https://github.com/AdrianPotter/acro-hub-frontend
- A back end using AWS lambda. Preferably based on Python because that's what I know best. That should be contained in this repository.

The back end must do the following things:

- Manage logins, logouts, registrations and password resets
- Serve up metadata on acrobatic moves
- Provide signed-urls to access the acro videos stored in S3
- Allow upload of new videos and metadata
- Ensure that only logged in members are allowed to access the content
- Provide operational insights into member logins and move views

Create the repository with the code needed to complete these functions based on the following tech stack:

| Concern                | Service                |
| ---------------------- | ---------------------- |
| User management        | Cognito User Pool      |
| Credential storage     | Cognito                |
| JWT validation         | API Gateway Authorizer |
| Move metadata          | DynamoDB               |
| Video storage          | S3 (private)           |
| Secure video access    | Lambda (Python) pre-signed URLs |
| Upload handling        | Pre-signed S3 uploads  |
| Event tracking         | DynamoDB events table  |
| Operational monitoring | CloudWatch             |

APIs should be accessed via API gateway and route 53 should be used for DNS using a generic test domain e.g. acrohub.org to begin with that will be confirmed later. Terraform should be used for deploying the infrastructure. Generate OpenAPI specifications for all APIs to make future modification easier and cover all Python codes with unit tests

Put this prompt into a PROMPT.MD markup file to make it easier to review this later. The README.MD should have instructions for local run and tests along with deployment. Update the .gitignore based on the tech stack and based on using PyCharm as the IDE.
