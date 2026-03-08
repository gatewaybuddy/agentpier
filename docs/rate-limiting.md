# Enhanced Rate Limiting for AgentPier

## Overview

AgentPier implements a sophisticated multi-tier rate limiting system that provides:

- **Redis-based sliding window rate limiting** for high performance
- **User tier-based limits** based on trust scores
- **Per-endpoint type configuration** for granular control
- **Automatic DynamoDB fallback** for high availability
- **Real-time CloudWatch metrics** for monitoring
- **API endpoints** for monitoring and configuration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│               Lambda Function                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │      Enhanced Rate Limiter                             ││
│  │  ┌─────────────┐      ┌──────────────────────────────┐ ││
│  │  │   Redis     │ ────▶│      DynamoDB Fallback       │ ││
│  │  │ (Primary)   │      │     (High Availability)      │ ││
│  │  └─────────────┘      └──────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                 CloudWatch Metrics                         │
└─────────────────────────────────────────────────────────────┘
```

## User Tiers

Rate limits are applied based on user trust tiers calculated from their trust score:

| Tier | Score Range | Description | Example Limits |
|------|-------------|-------------|----------------|
| `untrusted` | 0-19 | New users, minimal verification | 5 V-Token creates/5min |
| `provisional` | 20-39 | Basic verification completed | 10 V-Token creates/5min |
| `established` | 40-59 | Proven reliability over time | 20 V-Token creates/5min |
| `trusted` | 60-79 | High confidence in behavior | 50 V-Token creates/5min |
| `highly_trusted` | 80-95 | Maximum trust level | 100 V-Token creates/5min |

## Endpoint Configurations

### V-Token Operations

#### V-Token Creation (`vtokens_create`)
- **untrusted**: 5 requests per 5 minutes
- **provisional**: 10 requests per 5 minutes  
- **established**: 20 requests per 5 minutes
- **trusted**: 50 requests per 5 minutes
- **highly_trusted**: 100 requests per 5 minutes

#### V-Token Verification (`vtokens_verify`)
- **untrusted**: 20 requests per minute
- **provisional**: 50 requests per minute
- **established**: 100 requests per minute
- **trusted**: 200 requests per minute
- **highly_trusted**: 500 requests per minute

### Trust System

#### Trust Calculation (`trust_calculation`)
- **untrusted**: 10 requests per 5 minutes
- **provisional**: 20 requests per 5 minutes
- **established**: 50 requests per 5 minutes
- **trusted**: 100 requests per 5 minutes
- **highly_trusted**: 200 requests per 5 minutes

### Marketplace Operations

#### Search (`marketplace_search`)
- **untrusted**: 30 requests per minute
- **provisional**: 60 requests per minute
- **established**: 120 requests per minute
- **trusted**: 240 requests per minute
- **highly_trusted**: 500 requests per minute

#### Create Listings (`marketplace_create`)
- **untrusted**: 2 requests per hour
- **provisional**: 5 requests per hour
- **established**: 10 requests per hour
- **trusted**: 25 requests per hour
- **highly_trusted**: 50 requests per hour

### Authentication

#### Challenge Requests (`auth_challenge`)
- **untrusted**: 5 requests per hour
- **provisional**: 10 requests per hour
- **established**: 15 requests per hour
- **trusted**: 20 requests per hour
- **highly_trusted**: 30 requests per hour

#### Registration (`auth_register`)
- **untrusted**: 3 requests per hour
- **provisional**: 5 requests per hour
- **established**: 8 requests per hour
- **trusted**: 10 requests per hour
- **highly_trusted**: 15 requests per hour

#### Sign In (`auth_signin`)
- **untrusted**: 10 requests per 5 minutes
- **provisional**: 20 requests per 5 minutes
- **established**: 30 requests per 5 minutes
- **trusted**: 50 requests per 5 minutes
- **highly_trusted**: 100 requests per 5 minutes

## Implementation

### Adding Rate Limiting to Handlers

Use the `@rate_limit_middleware` decorator:

```python
from utils.enhanced_rate_limit import rate_limit_middleware
from utils.response import handler

@rate_limit_middleware("vtokens_create")
@handler
def create_vtoken(event, context):
    # Handler implementation
    pass
```

### Manual Rate Limit Checks

For custom logic:

```python
from utils.enhanced_rate_limit import check_enhanced_rate_limit

def my_handler(event, context):
    # Check rate limit
    rate_limit_response = check_enhanced_rate_limit(event, "custom_endpoint")
    if rate_limit_response:
        return rate_limit_response
    
    # Rate limit passed, continue with logic
    return success({"message": "Request processed"})
```

## Backend Systems

### Redis (Primary)

- **Performance**: Sub-millisecond response times
- **Algorithm**: Sliding window using Redis sorted sets
- **Persistence**: Automatic expiry using Redis TTL
- **High Availability**: ElastiCache replication group with Multi-AZ

### DynamoDB (Fallback)

- **Reliability**: 99.99% availability SLA
- **Algorithm**: Fixed window with TTL-based cleanup
- **Scaling**: Automatic with PAY_PER_REQUEST billing
- **Fallback Triggers**: Redis connection failures or timeouts

## Monitoring API Endpoints

### Get Rate Limit Info
```
GET /rate-limits
Authorization: Bearer <api-key>
```

Response includes user's tier, backend status, and all endpoint limits.

### Get Current Status
```
GET /rate-limits/status?endpoint_type=vtokens_create
Authorization: Bearer <api-key>
```

Response includes current usage, remaining requests, and retry timing.

### Get Configuration (Admin)
```
GET /rate-limits/config
X-Admin-Key: <admin-key>
```

Complete system configuration for debugging and monitoring.

## CloudWatch Metrics

The system publishes metrics to CloudWatch under namespace `AgentPier/{Stage}/RateLimit`:

### Metrics

- **RateLimitChecks**: Total rate limit checks performed
  - Dimensions: `EndpointType`, `UserTier`, `Backend`
- **RateLimitViolations**: Requests blocked by rate limiting
  - Dimensions: `EndpointType`, `UserTier`  
- **RateLimitAllowed**: Requests allowed through rate limiting
  - Dimensions: `EndpointType`, `UserTier`

### Sample Queries

```sql
-- Rate limit violation rate by endpoint
SELECT AVG(RateLimitViolations) / AVG(RateLimitChecks) * 100 
FROM SCHEMA("AgentPier/prod/RateLimit", EndpointType)

-- Backend performance comparison
SELECT Backend, AVG(RateLimitChecks) 
FROM SCHEMA("AgentPier/prod/RateLimit", Backend)
GROUP BY Backend
```

## Error Responses

When rate limits are exceeded:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded for vtokens_create. Tier: established, Limit: 20/300s",
  "retry_after": 120,
  "rate_limit": {
    "tier": "established",
    "endpoint_type": "vtokens_create", 
    "limit": 20,
    "window": 300,
    "backend": "redis"
  }
}
```

## Configuration

### Environment Variables

- `REDIS_HOST`: ElastiCache cluster endpoint
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `METRICS_NAMESPACE`: CloudWatch namespace for metrics
- `TABLE_NAME`: DynamoDB table for fallback storage

### Infrastructure

Deployed via CloudFormation with:
- ElastiCache Redis replication group
- VPC with private subnets for security
- Security groups restricting access
- NAT gateways for Lambda internet access

## Troubleshooting

### Redis Connection Issues

1. Check VPC configuration and security groups
2. Verify ElastiCache cluster status
3. Review Lambda function logs for Redis errors
4. Confirm NAT gateway configuration

### High Rate Limit Violations

1. Review CloudWatch metrics by endpoint and tier
2. Check if legitimate traffic patterns have changed
3. Consider adjusting limits for specific tiers
4. Verify user tier calculations are accurate

### Performance Issues

1. Monitor Redis vs DynamoDB response times
2. Check ElastiCache cluster performance metrics
3. Review Lambda memory and timeout settings
4. Consider upgrading ElastiCache node types

## Security Considerations

1. **VPC Isolation**: Redis is deployed in private subnets
2. **Encryption**: Redis supports encryption at rest and in transit (production)
3. **Access Control**: Security groups restrict access to Lambda functions only
4. **Monitoring**: All rate limit activity is logged to CloudWatch
5. **Fail Closed**: When backends are unavailable, requests are rejected

## Future Enhancements

- **Geographic Rate Limiting**: Different limits by region
- **Adaptive Limits**: Machine learning-based limit adjustment
- **Burst Allowances**: Short-term burst capacity for trusted users
- **Custom Rules**: Per-user rate limit overrides
- **Advanced Analytics**: Rate limit pattern analysis and reporting