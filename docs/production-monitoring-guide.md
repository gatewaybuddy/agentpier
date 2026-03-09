# AgentPier Production Monitoring Guide

Comprehensive production-grade monitoring system with APM, business metrics, SLA tracking, and operational dashboards.

## Overview

The production monitoring enhancement provides:

- **Application Performance Monitoring (APM)**: Distributed tracing for trust calculations and API flows
- **Business Metrics Tracking**: Trust scores, V-Token validations, API usage patterns, growth metrics
- **Anomaly Detection**: Automated detection of unusual trust calculation patterns
- **SLA Monitoring**: Real-time tracking against availability, latency, and error rate targets
- **Operational Dashboards**: Comprehensive CloudWatch dashboards for production management
- **Capacity Planning**: Automated analysis and scaling recommendations

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   Lambda        │    │   Production     │    │   CloudWatch      │
│   Functions     │───▶│   Monitoring     │───▶│   Dashboards      │
│   (Enhanced)    │    │   Collector      │    │   & Alarms        │
└─────────────────┘    └──────────────────┘    └───────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   DynamoDB      │    │   Business       │    │   SNS Alerts     │
│   Metrics       │    │   Intelligence   │    │   & Notifications │
│   Storage       │    │   Analytics      │    │                   │
└─────────────────┘    └──────────────────┘    └───────────────────┘
```

## Quick Start

### 1. Deploy Monitoring Infrastructure

```bash
# Deploy enhanced monitoring components
sam deploy --template-file infra/production-dashboard.yaml \
           --stack-name agentpier-monitoring-prod \
           --parameter-overrides Stage=prod \
           --capabilities CAPABILITY_IAM

# Verify deployment
aws cloudformation describe-stacks --stack-name agentpier-monitoring-prod
```

### 2. Integrate Monitoring in Lambda Functions

```python
from monitoring.integration import production_monitor, ProductionMonitoringMiddleware

# Method 1: Decorator approach
@production_monitor("trust_score_calculation", include_anomaly_detection=True)
def calculate_trust_score(event, context):
    # Your trust calculation logic
    return {"trust_score": 85.0}

# Method 2: Middleware approach (automatic)
@ProductionMonitoringMiddleware.lambda_middleware
def lambda_handler(event, context):
    # Your Lambda function logic - automatically monitored
    return response
```

### 3. Verify Monitoring Setup

```bash
# Run health check
python3 -c "
from monitoring.integration import MonitoringHealthCheck
import json
result = MonitoringHealthCheck.verify_monitoring_setup()
print(json.dumps(result, indent=2))
"

# Test monitoring pipeline
python3 -c "
from monitoring.integration import MonitoringHealthCheck
import json
result = MonitoringHealthCheck.test_monitoring_pipeline()
print(json.dumps(result, indent=2))
"
```

## Component Details

### 1. Production Metrics Collector

**Location**: `src/monitoring/production_monitoring.py`

**Key Features**:
- Business metrics collection (trust scores, V-Tokens, API requests)
- SLA metrics calculation (availability, latency, error rates)
- Anomaly detection for trust calculations
- CloudWatch metrics publishing

**Scheduled Execution**: Every 5 minutes via CloudWatch Events

### 2. Distributed Tracing System

**Components**:
- `DistributedTracer`: Lightweight tracing for complex operations
- Context managers for segment tracking
- CloudWatch metrics integration
- Trust calculation flow visibility

**Usage**:
```python
from monitoring.performance_monitoring import get_tracer

tracer = get_tracer()
trace_id = tracer.start_trace("trust_calculation")

with tracer.trace_segment("data_validation"):
    # Validate input data
    
with tracer.trace_segment("ace_score_calculation"):
    # Calculate ACE score
    
tracer.finish_trace()
```

### 3. Performance Benchmarking

**Features**:
- Baseline establishment from historical data
- Regression detection (>20% degradation)
- Performance alert generation
- Trend analysis and capacity planning

**Usage**:
```python
from monitoring.performance_monitoring import get_performance_benchmark

benchmark = get_performance_benchmark()
baseline = benchmark.calculate_baseline("/trust/{agent_id}", "GET", hours=24)
regression = benchmark.check_performance_regression("/trust/{agent_id}", "GET")
```

### 4. Anomaly Detection

**Monitored Metrics**:
- Trust score sudden changes (>25% deviation)
- Calculation time anomalies (>3x normal)
- Validation failures
- Score distribution shifts

**Alert Severities**:
- **Low**: Minor deviations, monitoring only
- **Medium**: Moderate anomalies, investigate
- **High**: Significant anomalies, immediate attention
- **Critical**: System-threatening anomalies, urgent action

## Dashboards

### Production Operations Dashboard

**URL**: Available in CloudFormation outputs after deployment

**Sections**:
1. **SLA Performance**: Availability, latency, error rate tracking
2. **Business Metrics**: Trust calculations, V-Token validations, growth trends
3. **System Health**: Lambda and DynamoDB performance
4. **Anomaly Detection**: Trust calculation anomalies and alerts

### Business Intelligence Dashboard

**Features**:
- Growth trend analysis (7-day moving averages)
- Trust tier distribution visualization
- Platform utilization heatmaps
- Revenue indicator tracking

## SLA Targets

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Availability | 99.5% | < 99.0% |
| Latency (P99) | < 2 seconds | > 5 seconds |
| Error Rate | < 1% | > 5% |
| Trust Calc Time | < 1 second | > 5 seconds |

## Capacity Planning

### Automated Analysis

```bash
# Generate capacity planning report
./scripts/capacity-planning.py --stage prod --hours 168 --format summary

# Save detailed report
./scripts/capacity-planning.py --stage prod --output capacity-report.json --format json
```

### Manual Monitoring

Key metrics to watch:
- Lambda concurrent executions (limit: 1000)
- DynamoDB read/write capacity utilization
- API Gateway request rates
- Trust calculation volume trends

## Alerting Configuration

### Critical Alerts (Immediate Response)

1. **SLA Availability < 99.5%**
   - Notification: SNS → Email/Slack
   - Response: Check system health, investigate outages

2. **Trust Score Anomalies > 10/hour**
   - Notification: SNS → PagerDuty
   - Response: Investigate data quality, check calculation logic

3. **API Latency P99 > 5 seconds**
   - Notification: SNS → Monitoring team
   - Response: Check Lambda performance, DynamoDB throttling

### Warning Alerts (Monitor Closely)

1. **Capacity utilization > 70%**
2. **Growth rate > 25% week-over-week**
3. **Error rate > 2%**

## Troubleshooting

### Common Issues

#### 1. Missing Metrics Data

**Symptoms**: Empty dashboards, no monitoring data
**Causes**: 
- Production monitoring Lambda not deployed
- IAM permissions missing
- Incorrect namespace configuration

**Solution**:
```bash
# Check Lambda function
aws lambda get-function --function-name agentpier-production-monitoring-prod

# Check CloudWatch metrics
aws cloudwatch list-metrics --namespace "AgentPier/prod"

# Verify IAM permissions
aws iam simulate-principal-policy --policy-source-arn <lambda-role-arn> \
  --action-names cloudwatch:PutMetricData
```

#### 2. High False Positive Anomaly Alerts

**Symptoms**: Too many anomaly notifications
**Causes**: 
- Thresholds too sensitive
- Insufficient historical data
- Normal business growth patterns

**Solution**:
```python
# Adjust anomaly thresholds in production_monitoring.py
# Line ~200: Change score_change_percent threshold
if score_change_percent > 40:  # Increase from 25 to 40
```

#### 3. Performance Regression False Alarms

**Symptoms**: Performance alerts during normal operation
**Causes**:
- Cold start effects
- Normal load variations
- Insufficient baseline data

**Solution**:
```python
# Adjust baseline calculation period
baseline = benchmark.calculate_baseline(endpoint, method, hours=72)  # Increase from 24
```

### Debugging Commands

```bash
# Check monitoring function logs
aws logs tail /aws/lambda/agentpier-production-monitoring-prod

# List current CloudWatch alarms
aws cloudwatch describe-alarms --state-value ALARM

# Get recent metrics
aws cloudwatch get-metric-statistics \
  --namespace "AgentPier/prod" \
  --metric-name "TrustScoresCalculated" \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-02T00:00:00Z" \
  --period 3600 \
  --statistics Sum
```

## Performance Impact

### Resource Overhead

| Component | CPU Impact | Memory Impact | Network Impact |
|-----------|------------|---------------|----------------|
| APM Tracing | < 5% | ~50MB | < 1KB/request |
| Metrics Collection | < 2% | ~20MB | ~500B/metric |
| Anomaly Detection | < 3% | ~30MB | ~1KB/alert |

### Cost Estimation

- **CloudWatch Metrics**: ~$0.30/1000 metrics/month
- **CloudWatch Logs**: ~$0.50/GB/month
- **Lambda Execution**: ~$0.002/monitoring cycle
- **SNS Notifications**: ~$0.50/1000 notifications

**Total Monthly Cost (Production)**: ~$15-30/month depending on volume

## Migration Guide

### From Basic Monitoring

1. **Deploy new monitoring stack**:
   ```bash
   sam deploy --template-file infra/production-dashboard.yaml
   ```

2. **Update existing Lambda functions**:
   ```python
   # Add to existing functions
   from monitoring.integration import production_monitor
   
   @production_monitor("existing_operation")
   def existing_function(event, context):
       # Existing code unchanged
       return result
   ```

3. **Validate migration**:
   - Check new dashboards for data
   - Verify alerts are firing correctly
   - Monitor for 24-48 hours before relying on new system

### From No Monitoring

1. **Baseline establishment**: Run system for 7 days to establish baselines
2. **Threshold tuning**: Adjust alert thresholds based on actual patterns
3. **Team training**: Ensure operations team understands new dashboards

## Best Practices

### 1. Monitoring Hygiene

- **Review dashboards weekly**: Look for trends and anomalies
- **Update thresholds quarterly**: Adjust based on growth and changes
- **Test alert channels monthly**: Ensure notifications work
- **Archive old alerts**: Clean up resolved issues

### 2. Performance Optimization

- **Batch metrics**: Send multiple metrics in single CloudWatch call
- **Use sampling**: Not every request needs full tracing
- **Cache baselines**: Avoid recalculating frequently
- **Async processing**: Don't block main operation for monitoring

### 3. Cost Management

- **Set metric retention**: Use appropriate CloudWatch retention periods
- **Filter noisy metrics**: Only track actionable data
- **Use log sampling**: Reduce log volume for high-frequency operations
- **Monitor monitoring costs**: Track CloudWatch charges monthly

## Support and Maintenance

### Regular Tasks

- **Weekly**: Review capacity planning reports
- **Monthly**: Analyze SLA performance trends
- **Quarterly**: Update monitoring thresholds and baselines
- **Annually**: Review and optimize monitoring costs

### Emergency Procedures

1. **Critical SLA Breach**: Follow incident response plan
2. **Monitoring System Down**: Switch to basic CloudWatch metrics
3. **False Alert Storm**: Temporarily disable affected alarms
4. **Capacity Emergency**: Implement emergency scaling procedures

For additional support, see [AgentPier Operations Runbook](./operations-runbook.md).