# AgentPier Monitoring Setup

This document explains the monitoring infrastructure implemented for AgentPier, covering API response times, trust score calculation accuracy, DynamoDB performance, and CloudWatch dashboards.

## Overview

The monitoring system provides:

1. **API Response Time Monitoring** - Tracks API Gateway latency and error rates
2. **Trust Score Calculation Accuracy** - Monitors trust score calculation performance and accuracy
3. **DynamoDB Performance Monitoring** - Tracks read/write capacity and throttling
4. **CloudWatch Dashboards** - Visual monitoring with alerts
5. **Custom Metrics Collection** - Scheduled Lambda function for application-specific metrics

## Components

### 1. CloudFormation Resources

The monitoring infrastructure is defined in the main `template.yaml` file and includes:

- **MetricsCollectorFunction**: Scheduled Lambda that collects custom metrics every 5 minutes
- **CloudWatch Alarms**: Alerts for high API latency, error rates, and DynamoDB throttling
- **SNS Topic**: Centralized alerting destination
- **CloudWatch Dashboard**: Visual monitoring interface
- **Log Groups**: Structured logging for Lambda functions

### 2. Python Monitoring Package

Located in `src/monitoring/`, the package provides:

- **decorator.py**: Decorators for automatic metrics collection
- **metrics_collector.py**: Scheduled metrics collection Lambda
- **trust_monitoring.py**: Example integration with trust score functions

## Deployment

### Step 1: Deploy Infrastructure

```bash
cd infra/
sam deploy --guided
```

This will deploy all monitoring resources along with the existing AgentPier infrastructure.

### Step 2: Configure Alerting (Optional)

Subscribe to the SNS topic for alerts:

```bash
aws sns subscribe \
  --topic-arn <AlertingTopicArn from stack outputs> \
  --protocol email \
  --notification-endpoint your-email@domain.com
```

### Step 3: Access Dashboard

The CloudWatch dashboard URL is available in the CloudFormation stack outputs. Navigate to:

```
https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AgentPier-dev-Monitoring
```

## Usage

### Adding Monitoring to Lambda Functions

Use the decorators to automatically collect metrics:

```python
from monitoring import monitor_lambda_function, monitor_trust_score_calculation

@monitor_lambda_function("trust_score_query")
def get_trust_score(event, context):
    # Your function logic
    return result

@monitor_trust_score_calculation(include_accuracy=True)
def calculate_ace_score(events):
    # Your scoring logic
    return score
```

### Manual Metrics

Send custom metrics directly:

```python
from monitoring import get_metrics_collector

metrics = get_metrics_collector()
metrics.send_metric("custom_metric_name", 1.0, "Count")
```

### Operation Tracking

Track operations with context manager:

```python
from monitoring import track_operation

with track_operation("database_query", table="agents"):
    # Your database operation
    result = table.query(...)
```

## Metrics Collected

### API Metrics
- Request count and success/error rates
- Average response times
- HTTP status code distribution

### Trust Score Metrics
- Calculation count and error rates
- Calculation performance (duration)
- Score accuracy (comparison with recalculated values)
- Score distribution by tier

### DynamoDB Metrics
- Read/write capacity consumption
- Throttling events
- Query/scan performance

### System Metrics
- Lambda function duration and memory usage
- Error rates and types
- Custom application metrics

## Alarms and Thresholds

### Configured Alarms

1. **High API Latency**: Triggers when response time > 5 seconds
2. **High API Error Rate**: Triggers when error count > 10 in 5 minutes
3. **DynamoDB Throttling**: Triggers on any read/write throttling
4. **Trust Score Errors**: Triggers on any trust calculation errors

### Customizing Thresholds

Modify alarm thresholds in `template.yaml`:

```yaml
HighApiLatencyAlarm:
  Properties:
    Threshold: 5000  # milliseconds
    EvaluationPeriods: 2
```

## Dashboard Widgets

The CloudWatch dashboard includes:

1. **API Response Times** - Average latency over time
2. **API Request Volume & Errors** - Request count and error rates
3. **DynamoDB Capacity Usage** - Read/write capacity consumption
4. **DynamoDB Throttles** - Throttling events
5. **Trust Score Operations** - Calculation count and errors
6. **Trust Score Performance** - Accuracy and timing metrics

## Troubleshooting

### High Trust Score Calculation Errors

1. Check CloudWatch logs for the trust scoring functions
2. Review trust score calculation logic for edge cases
3. Verify DynamoDB data integrity

### API Performance Issues

1. Check API Gateway metrics for specific endpoints
2. Review Lambda function performance and memory usage
3. Check DynamoDB throttling and capacity

### Missing Metrics

1. Verify the metrics collector function is running (check CloudWatch Events)
2. Check Lambda function permissions for CloudWatch access
3. Review function logs for errors

### Custom Metrics Not Appearing

1. Verify correct namespace usage (`AgentPier/{Stage}`)
2. Check CloudWatch permissions
3. Review metric naming conventions

## Cost Considerations

The monitoring infrastructure has minimal cost impact:

- **CloudWatch Metrics**: ~$0.30 per metric per month
- **CloudWatch Alarms**: ~$0.10 per alarm per month
- **CloudWatch Dashboard**: ~$3.00 per dashboard per month
- **Lambda Execution**: Metrics collector runs every 5 minutes (~8,640 invocations/month)

Estimated monthly cost: $10-20 depending on usage.

## Security

### Permissions

The monitoring system uses minimal required permissions:

- **MetricsCollectorFunction**: Read access to DynamoDB, write to CloudWatch
- **Other Functions**: Write access to CloudWatch metrics only

### Data Privacy

- No sensitive data is collected in metrics
- Trust scores are aggregated without exposing individual agent details
- API request logs include timing data only, not request content

## Maintenance

### Regular Tasks

1. **Monthly**: Review dashboard for trends and anomalies
2. **Quarterly**: Adjust alarm thresholds based on usage patterns
3. **As needed**: Add new metrics for additional functionality

### Log Retention

- API logs: 7 days
- Trust scoring logs: 14 days
- CloudWatch metrics: 15 months (default)

### Updates

When adding new Lambda functions:

1. Add monitoring decorators
2. Create function-specific log groups
3. Add relevant alarms if needed
4. Update dashboard widgets

## Reference

### Environment Variables

- `METRICS_NAMESPACE`: CloudWatch namespace (default: `AgentPier/{Stage}`)
- `TABLE_NAME`: DynamoDB table name
- `STAGE`: Deployment stage (dev/prod)

### CloudWatch Namespaces

- `AgentPier/{Stage}`: Custom application metrics
- `AWS/ApiGateway`: API Gateway metrics
- `AWS/Lambda`: Lambda function metrics
- `AWS/DynamoDB`: DynamoDB metrics

### Metric Names

- `TrustScoreCalculations`: Count of trust score calculations
- `TrustScoreCalculationErrors`: Count of calculation errors
- `TrustScoreAccuracy`: Percentage accuracy of calculations
- `AverageScoreCalculationTime`: Average calculation duration
- `CustomAPIRequestCount`: API request count
- `CustomAPISuccessCount`: Successful API requests
- `CustomAPIErrorCount`: Failed API requests

## Support

For issues or questions about the monitoring system:

1. Check CloudWatch logs for error details
2. Review this documentation
3. Check AWS CloudWatch service status
4. Contact the development team with specific error messages and timestamps