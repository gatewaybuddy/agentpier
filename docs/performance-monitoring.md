# AgentPier Performance Monitoring

## Overview

This document describes the enhanced performance monitoring system for AgentPier, including distributed tracing, performance benchmarking, regression testing, and automated alerting.

## Architecture

### Components

1. **Distributed Tracing**: Lightweight tracing for trust calculations and API flows
2. **Performance Benchmarking**: Baseline establishment and comparison
3. **Regression Detection**: Automated alerts for >20% performance degradation
4. **Performance Dashboard**: CloudWatch metrics and custom dashboards

### Key Features

- **Real-time Performance Tracking**: Monitor API response times, trust calculation performance
- **Baseline Management**: Automatic baseline calculation from historical data
- **Regression Alerts**: Immediate notification when performance degrades by >20%
- **Distributed Tracing**: End-to-end visibility into trust calculation flows

## Performance Baselines

### Current Baselines (as of March 8, 2026)

#### V-Token Operations
- **POST /vtokens/create**: 
  - Baseline: 145ms avg, 280ms p95, 420ms p99
  - Success Rate: 98.5%
  - Throughput: 12 RPS
  
- **POST /vtokens/verify**:
  - Baseline: 85ms avg, 180ms p95, 250ms p99  
  - Success Rate: 99.2%
  - Throughput: 45 RPS

#### Trust Score Operations
- **GET /trust/{agent_id}**:
  - Baseline: 125ms avg, 220ms p95, 350ms p99
  - Success Rate: 99.8%
  - Throughput: 25 RPS

- **POST /trust/calculate**:
  - Baseline: 180ms avg, 350ms p95, 580ms p99
  - Success Rate: 97.5%
  - Throughput: 8 RPS

#### Authentication Operations
- **POST /auth/challenge**:
  - Baseline: 95ms avg, 160ms p95, 240ms p99
  - Success Rate: 99.5%
  - Throughput: 15 RPS

- **POST /auth/register**:
  - Baseline: 210ms avg, 420ms p95, 680ms p99
  - Success Rate: 96.8%
  - Throughput: 5 RPS

### Baseline Update Schedule

- **Automatic**: Baselines recalculated every 24 hours using previous 24h of data
- **Manual**: Can be triggered via `/performance/baseline/update` endpoint
- **Minimum Sample Size**: 100 requests required for reliable baseline

## Distributed Tracing

### Trust Calculation Tracing

Trust score calculations are automatically traced with the following segments:

1. **Root Trace**: Overall trust calculation operation
2. **Data Retrieval**: Agent data and events fetching from DynamoDB
3. **Score Calculation**: ACE or clearinghouse score computation
4. **Validation**: Score validation and tier assignment
5. **Storage**: Score storage and cache updates

### Trace Data Structure

```json
{
  "trace_id": "uuid",
  "segments": [
    {
      "segment_id": "uuid",
      "parent_id": "uuid|null",
      "operation": "ace_score_calculation",
      "start_time": 1709858400.123,
      "end_time": 1709858400.245,
      "duration_ms": 122,
      "success": true,
      "metadata": {
        "agent_id": "agent_123",
        "events_count": 45,
        "score_tier": "tier_3_good"
      }
    }
  ]
}
```

## Performance Regression Detection

### Detection Criteria

Regression is triggered when any of the following conditions are met:

- **Response Time**: >20% increase in average response time compared to baseline
- **Success Rate**: >5% decrease in success rate
- **Throughput**: >30% decrease in requests per second

### Alert Thresholds

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| Response Time | +20% from baseline | +50% from baseline |
| Success Rate | -5% from baseline | -15% from baseline |
| Error Rate | >2% | >10% |
| Trust Calc Time | >300ms avg | >500ms avg |

## CloudWatch Metrics

### Standard Metrics

- `AgentPier/{stage}/ApiResponseTime` - API response times by endpoint
- `AgentPier/{stage}/ApiSuccessRate` - Success rates by endpoint  
- `AgentPier/{stage}/TrustCalculationTime` - Trust calculation durations
- `AgentPier/{stage}/PerformanceRegressionAlert` - Regression alert count

### Custom Metrics

- `AgentPier/{stage}/trace_total_duration` - End-to-end trace duration
- `AgentPier/{stage}/trace_segment_count` - Number of segments per trace
- `AgentPier/{stage}/segment_duration_{operation}` - Individual segment timings

### Metric Dimensions

- **Endpoint**: API endpoint path
- **Method**: HTTP method
- **TraceOperation**: Root trace operation name
- **ErrorType**: Exception class name
- **DegradationPercent**: Performance degradation percentage

## Performance Dashboard Setup

### CloudWatch Dashboard Configuration

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AgentPier/dev", "ApiResponseTime", "Endpoint", "/trust/{agent_id}", "Method", "GET"],
          [".", "ApiResponseTime", "Endpoint", "/vtokens/create", "Method", "POST"],
          [".", "ApiResponseTime", "Endpoint", "/vtokens/verify", "Method", "POST"]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "API Response Times"
      }
    },
    {
      "type": "metric", 
      "properties": {
        "metrics": [
          ["AgentPier/dev", "TrustCalculationTime"],
          [".", "trace_total_duration", "TraceOperation", "trust_calculation"]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Trust Calculation Performance"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AgentPier/dev", "PerformanceRegressionAlert"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1", 
        "title": "Performance Regression Alerts"
      }
    }
  ]
}
```

### Creating the Dashboard

```bash
# Create performance dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "AgentPier-Performance-Dev" \
  --dashboard-body file://dashboard-config.json

# Set up CloudWatch alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "AgentPier-Performance-Regression" \
  --alarm-description "Alert when performance regression detected" \
  --metric-name "PerformanceRegressionAlert" \
  --namespace "AgentPier/dev" \
  --statistic "Sum" \
  --period 300 \
  --threshold 1 \
  --comparison-operator "GreaterThanOrEqualToThreshold"
```

## Usage Examples

### Adding Performance Monitoring to API Handlers

```python
from monitoring.performance_monitoring import (
    monitor_api_performance, 
    trace_trust_calculation,
    get_tracer
)

@monitor_api_performance("/trust/{agent_id}", "GET")
def get_trust_score_handler(event, context):
    """Enhanced trust score handler with performance monitoring."""
    
    # Start distributed trace
    tracer = get_tracer()
    trace_id = tracer.start_trace("trust_score_query")
    
    try:
        with tracer.trace_segment("parameter_validation"):
            # Validate parameters
            agent_id = event.get("pathParameters", {}).get("agent_id")
            if not agent_id:
                return error("agent_id required", 400)
        
        with tracer.trace_segment("data_retrieval", {"agent_id": agent_id}):
            # Get agent data
            table = get_table()
            agent_data = get_agent_data(table, agent_id)
        
        with tracer.trace_segment("trust_calculation"):
            # Calculate trust score
            trust_score = calculate_monitored_trust_score(agent_data)
        
        return success({"agent_id": agent_id, "trust_score": trust_score})
    
    finally:
        tracer.finish_trace(trace_id)

@trace_trust_calculation("ace_score_calculation") 
def calculate_monitored_trust_score(agent_data):
    """Trust calculation with distributed tracing."""
    tracer = get_tracer()
    
    with tracer.trace_segment("ace_scoring", {"events_count": len(agent_data.get("events", []))}):
        return calculate_ace_score(agent_data["events"])
```

### Manual Performance Baseline Update

```python
from monitoring.performance_monitoring import get_performance_benchmark

# Update baselines for key endpoints
benchmark = get_performance_benchmark()

endpoints = [
    ("/trust/{agent_id}", "GET"),
    ("/vtokens/create", "POST"), 
    ("/vtokens/verify", "POST"),
    ("/auth/register", "POST")
]

for endpoint, method in endpoints:
    baseline = benchmark.calculate_baseline(endpoint, method, hours=24)
    if baseline:
        print(f"Updated baseline for {method} {endpoint}: {baseline.avg_response_time_ms}ms avg")
```

### Checking for Performance Regressions

```python
# Check all endpoints for regressions
regression_results = []

for endpoint, method in endpoints:
    result = benchmark.check_performance_regression(endpoint, method)
    if result["status"] == "regression_detected":
        regression_results.append(result)
        print(f"REGRESSION: {method} {endpoint} - {result['degradation_percent']:.1f}% slower")

if regression_results:
    # Send alert notification
    send_performance_alert(regression_results)
```

## Automated Performance Testing

### Lambda Function for Baseline Updates

A scheduled Lambda function updates performance baselines daily:

```python
def update_baselines_handler(event, context):
    """Scheduled function to update performance baselines."""
    
    benchmark = get_performance_benchmark()
    endpoints = load_monitored_endpoints()
    
    results = []
    for endpoint, method in endpoints:
        baseline = benchmark.calculate_baseline(endpoint, method)
        if baseline:
            results.append({
                "endpoint": endpoint,
                "method": method, 
                "avg_response_time_ms": baseline.avg_response_time_ms,
                "sample_size": baseline.sample_size
            })
    
    return success({"updated_baselines": results})
```

### CloudWatch Events Schedule

```yaml
BaselineUpdateSchedule:
  Type: AWS::Events::Rule
  Properties:
    Description: "Update performance baselines daily"
    ScheduleExpression: "cron(0 6 * * ? *)"  # 6 AM UTC daily
    Targets:
      - Arn: !GetAtt UpdateBaselinesFunction.Arn
        Id: "UpdateBaselinesTarget"
```

## Troubleshooting

### Performance Issues

1. **High Response Times**:
   - Check distributed traces for bottlenecks
   - Review trust calculation complexity
   - Verify DynamoDB performance metrics

2. **Regression False Positives**:
   - Increase minimum sample size requirement
   - Adjust regression threshold percentage
   - Check for deployment-related spikes

3. **Missing Baseline Data**:
   - Verify API logging is enabled
   - Check DynamoDB TTL settings
   - Ensure sufficient traffic volume

### Monitoring Health

- Monitor CloudWatch metric delivery
- Check Lambda function logs for errors
- Verify DynamoDB table permissions
- Test alert notification delivery

## Next Steps

1. **Enhanced Tracing**: Add custom trace annotations for business logic
2. **Predictive Alerting**: ML-based performance anomaly detection  
3. **Load Testing Integration**: Automated performance validation in CI/CD
4. **Cost Optimization**: Right-size monitoring based on usage patterns