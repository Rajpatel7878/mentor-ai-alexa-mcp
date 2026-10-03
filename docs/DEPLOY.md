# Deploy to AWS App Runner

> **Time estimate:** ~25 minutes for a first deploy.  
> **Prerequisites:** AWS CLI installed and configured, Docker Desktop running.

---

## Overview

```
Local code
  └── docker build
       └── push to Amazon ECR
            └── App Runner service (auto-TLS, auto-scale)
                 └── Public HTTPS URL  (https://<id>.awsapprunner.com)
```

---

## Step 1 — Set variables

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1          # change if needed
export ECR_REPO=mentor-ai
export IMAGE_TAG=latest
export ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
export FRONTEND_ORIGIN="https://your-frontend.example.com"
```

---

## Step 2 — Create ECR repository

```bash
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION
```

---

## Step 3 — Build and push Docker image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Build (from repo root)
docker build -t ${ECR_REPO}:${IMAGE_TAG} ./server

# Tag
docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}

# Push
docker push ${ECR_URI}:${IMAGE_TAG}
```

---

## Step 4 — Create an App Runner IAM role

App Runner needs permission to pull from ECR.

```bash
# Create the trust policy
cat > /tmp/apprunner-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "build.apprunner.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document file:///tmp/apprunner-trust.json

aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

The ECR access role is different from the runtime instance role. Create the
runtime role explicitly so the application can call Bedrock through the normal
AWS credential chain:

```bash
cat > /tmp/apprunner-instance-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "tasks.apprunner.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name AppRunnerInstanceRole \
  --assume-role-policy-document file:///tmp/apprunner-instance-trust.json

cat > /tmp/bedrock-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "bedrock:InvokeModel",
    "Resource": "*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name AppRunnerInstanceRole \
  --policy-name BedrockInvokeModel \
  --policy-document file:///tmp/bedrock-policy.json

export INSTANCE_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerInstanceRole"
```

---

## Step 5 — Create the App Runner service

```bash
cat > /tmp/apprunner-service.json <<EOF
{
  "ServiceName": "mentor-ai",
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "${ECR_URI}:${IMAGE_TAG}",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "AWS_REGION": "${AWS_REGION}",
          "BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
          "LOG_LEVEL": "INFO",
          "CORS_ORIGIN": "${FRONTEND_ORIGIN}",
          "TRUST_PROXY_HEADERS": "true",
          "RATE_LIMIT_REQUESTS": "20",
          "RATE_LIMIT_WINDOW_SECONDS": "60",
          "BEDROCK_OFFLINE": "false"
        }
      }
    },
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/AppRunnerECRAccessRole"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB",
    "InstanceRoleArn": "${INSTANCE_ROLE_ARN}"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/health"
  }
}
EOF

aws apprunner create-service \
  --cli-input-json file:///tmp/apprunner-service.json \
  --region $AWS_REGION
```

> `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are intentionally not set:
> App Runner supplies credentials through `InstanceRoleArn`, and the server's
> automatic credential detection will use that role for Bedrock.
>
> Replace `https://your-frontend.example.com` with the real website origin, or
> use a tightly controlled value while testing. Do not use `*` for a public
> deployment. Add authentication or an API gateway before exposing this service
> to untrusted users because each successful request can incur Bedrock charges.

---

## Step 6 — Get the public URL

```bash
export SERVICE_ARN=$(aws apprunner list-services \
  --region $AWS_REGION \
  --query "ServiceSummaryList[?ServiceName=='mentor-ai'].ServiceArn" \
  --output text)

aws apprunner describe-service \
  --service-arn $SERVICE_ARN \
  --region $AWS_REGION \
  --query "Service.ServiceUrl" \
  --output text
```

Your MCP endpoint is:
```
https://<returned-domain>/mcp
```

Your REST API is:
```
https://<returned-domain>/api/ask
```

---

## Step 7 — Verify

```bash
# Health check
curl https://<returned-domain>/health

# Quick API test
curl -X POST https://<returned-domain>/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I raise a Series A?"}'
```

---

## Step 8 — Point the website at App Runner

Edit `web/index.html` and change the default value of `apiBaseInput`:

```html
<input id="api-base-input" value="https://<returned-domain>" ... />
```

Or let the judge update it in the live demo UI — the field is editable.

---

## Updating the deployment

```bash
# Rebuild and push a new image
docker build -t ${ECR_REPO}:${IMAGE_TAG} ./server
docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
docker push ${ECR_URI}:${IMAGE_TAG}

# Trigger a new App Runner deployment
aws apprunner start-deployment \
  --service-arn $SERVICE_ARN \
  --region $AWS_REGION
```

---

## Cost estimate (hackathon scale)

| Service | Approximate cost |
|---|---|
| App Runner (0.25 vCPU, 0.5 GB, low traffic) | ~\$0–\$5 / week |
| ECR storage (< 1 GB image) | ~\$0.10 / month |
| Bedrock Claude Haiku (~1000 calls) | ~\$0.10–\$0.50 |

---

## Teardown

```bash
aws apprunner delete-service --service-arn $SERVICE_ARN --region $AWS_REGION
aws ecr delete-repository --repository-name $ECR_REPO --force --region $AWS_REGION
```
