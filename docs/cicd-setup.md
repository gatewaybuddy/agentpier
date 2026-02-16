# AgentPier CI/CD Pipeline

## Overview

Three GitHub Actions workflows handle CI and deployment:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Every push & PR | Lint, test, security scan |
| `deploy-dev.yml` | Push to `main` | Build + deploy to dev |
| `deploy-prod.yml` | Manual / GitHub release | Build + deploy to prod |

## Pipeline Flow

```
Push to branch → CI (lint + test + security)
Push to main → CI → Deploy Dev → Smoke test
Release tag → CI → Deploy Prod → Smoke test
```

## GitHub Secrets Required

Add these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | From `agentpier-deploy` IAM user |
| `AWS_SECRET_ACCESS_KEY` | From `agentpier-deploy` IAM user |

Create two **environments** in GitHub:
- `dev` — no protection rules
- `production` — add required reviewers for manual approval

## Security Checks

### 1. Bandit (SAST)
Scans all Python source for common security issues (hardcoded passwords, SQL injection patterns, unsafe deserialization, etc.). Runs on every push.

### 2. Safety (Dependency Vulnerabilities)
Checks installed Python packages against the CVE database. Warns on known vulnerabilities. Currently advisory (non-blocking) since boto3 is the only real dependency.

### 3. Ruff (Linting)
Fast Python linter. Catches code quality issues, unused imports, and style problems.

### 4. Content Filter Tests
`test_content_filter.py` runs the injection/evasion patterns identified in the 2025-02-15 security audit against the content filter. Tests cover:
- Zero-width character evasion
- Spaced-letter evasion ("E s c o r t")
- Leetspeak substitution
- Prompt injection patterns
- All 11 blocked content categories

## Manual Deployment

```bash
# Dev
sam build --template-file infra/template.yaml
sam deploy --config-env dev

# Prod
sam build --template-file infra/template.yaml
sam deploy --config-env prod
```

## SAM Configuration

`samconfig.toml` defines two profiles:
- **dev**: `agentpier-dev` stack, auto-confirms changesets
- **prod**: `agentpier-prod` stack, requires changeset confirmation

Both deploy to `us-east-1`.

## IAM Permissions

The `agentpier-deploy` user needs these permissions for SAM to work:

### Required Additions (for SAM bootstrap S3 bucket)
- `s3:PutEncryptionConfiguration`
- `s3:PutBucketPolicy`
- `s3:PutBucketVersioning`
- `s3:PutBucketPublicAccessBlock`
- `s3:GetEncryptionConfiguration`
- `s3:GetBucketPolicy`
- `s3:GetBucketVersioning`

**Note:** The deploy user currently cannot list its own policies (`iam:ListAttachedUserPolicies` is denied). You need to use the root account or an admin user to add the missing S3 permissions. See the IAM section below.

### How to Fix IAM (from root/admin account)
```bash
# Create a policy with the missing S3 permissions
aws iam create-policy \
  --policy-name agentpier-sam-bootstrap \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutEncryptionConfiguration",
        "s3:PutBucketPolicy",
        "s3:PutBucketVersioning",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetEncryptionConfiguration",
        "s3:GetBucketPolicy",
        "s3:GetBucketVersioning",
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    }]
  }'

# Attach to deploy user
aws iam attach-user-policy \
  --user-name agentpier-deploy \
  --policy-arn arn:aws:iam::152924643524:policy/agentpier-sam-bootstrap
```

### Cleanup Done
- Deleted failed `aws-sam-cli-managed-default` CloudFormation stack (was in ROLLBACK_COMPLETE state)

## Test Structure

```
tests/
├── conftest.py              # Fixtures, mock DynamoDB, event builders
├── requirements-test.txt    # Test dependencies
├── test_auth.py             # API key generation, authentication
├── test_content_filter.py   # Content filter + evasion patterns
├── test_handlers.py         # Handler integration tests
└── test_trust.py            # ACE trust scoring logic
```

Run locally:
```bash
cd /mnt/d/Projects/agentpier
pip install -r tests/requirements-test.txt
pytest tests/ -v
```
