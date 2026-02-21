"""Shared fixtures for AgentPier tests."""

import os
import sys
import pytest
import boto3
from moto import mock_aws
from decimal import Decimal
from datetime import datetime, timezone

# Add src/ to path so handlers can import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Force table name for tests
os.environ["TABLE_NAME"] = "agentpier-test"
os.environ["STAGE"] = "test"


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb(aws_credentials):
    """Create a mock DynamoDB table matching the SAM template."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="agentpier-test",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")


@pytest.fixture
def sample_user(dynamodb):
    """Insert a sample user and return (user_id, raw_api_key)."""
    from utils.auth import generate_api_key

    user_id = "testuser123"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "META",
        "GSI1PK": f"AGENT_NAME#testbot",
        "GSI1SK": now,
        "user_id": user_id,
        "agent_name": "testbot",
        "description": "A test agent",
        "operator_email": "test@example.com",
        "human_verified": False,
        "trust_score": Decimal("0.5"),
        "listings_count": 2,
        "transactions_completed": 5,
        "disputes": 0,
        "dispute_rate": Decimal("0.0"),
        "created_at": now,
        "updated_at": now,
    })

    dynamodb.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": f"APIKEY#{key_hash[:16]}",
        "GSI2PK": f"APIKEY#{key_hash}",
        "GSI2SK": now,
        "user_id": user_id,
        "key_hash": key_hash,
        "api_key_raw": raw_key,
        "permissions": ["read", "write"],
        "created_at": now,
    })

    return user_id, raw_key


def make_api_event(method="GET", path="/", body=None, headers=None,
                   path_params=None, query_params=None, api_key=None):
    """Build a mock API Gateway event."""
    hdrs = headers or {}
    if api_key:
        hdrs["x-api-key"] = api_key
    
    event = {
        "httpMethod": method,
        "path": path,
        "headers": hdrs,
        "pathParameters": path_params or {},
        "queryStringParameters": query_params or {},
        "requestContext": {
            "identity": {"sourceIp": "127.0.0.1"},
            "stage": "test",
        },
        "body": None,
    }
    if body is not None:
        import json
        event["body"] = json.dumps(body) if isinstance(body, dict) else body
    return event
