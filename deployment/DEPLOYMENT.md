# Deployment Guide

## Deployment paths

- Backend API: AWS Lambda container in CloudFormation stack `ocp9`
- Frontend UI: Streamlit Cloud app linked to this repository

Azure Functions app `ocp9funcapp-recsys` remains the rollback source until
the AWS endpoint passes parity checks and the Streamlit configuration is cut
over.

## AWS deployment

The single `ocp9` CloudFormation stack owns the private artifact bucket, ECR
repository, Lambda runtime, Function URL, logs and OCP9-specific IAM roles.
The account-level GitHub OIDC provider is intentionally shared and remains
outside the stack.

The initial stack deployment leaves `ImageUri` empty so the bucket, ECR and
deployment role can be created before the first image. Verify and upload the
13 external runtime artifacts with:

```bash
AWS_REGION=us-east-1 aws_lambda/upload_artifacts.sh /absolute/path/to/artifacts
```

The `Deploy OCP9 AWS Lambda API` workflow builds the Linux/AMD64 container,
pushes an immutable image to ECR and updates the stack's `ImageUri` parameter.
GitHub uses short-lived OIDC credentials from repository variable
`AWS_DEPLOY_ROLE_ARN`; no AWS access keys are stored in GitHub.

The runtime downloads only the ten serving artifacts into encrypted Lambda
ephemeral storage, verifies their SHA-256 hashes and memory-maps the arrays.
The remaining three files stay in S3 as training evidence.

## AWS smoke tests

```bash
curl "${FUNCTION_URL%/}/health"
curl -X POST "${FUNCTION_URL%/}/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1351, "k": 10}'
```

## Azure rollback deployment (temporary)

```bash
cd deployment/azure_functions
func azure functionapp publish ocp9funcapp-recsys --python
```

## API smoke test

```bash
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 12345, "k": 5, "env": {"device": 1, "os": 3, "country": "US"}}'
```

## Streamlit entrypoint

- Cloud wrapper entrypoint: `streamlit_app.py`
- Canonical app executed by wrapper: `deployment/streamlit/app.py`

## Notes

- Large model artifacts are excluded from Git and must be present in the deployed runtime/storage environment.
- Preferred local runtime location is `external_runtime_assets/azure/artifacts/`.
