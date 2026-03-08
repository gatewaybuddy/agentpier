#!/usr/bin/env python3
"""
Setup script for AgentPier performance monitoring infrastructure.

This script:
1. Creates CloudWatch dashboard for performance metrics
2. Sets up automated alerts for performance regressions  
3. Configures baseline update schedules
4. Validates monitoring setup

Usage:
    python scripts/setup-performance-monitoring.py --stage dev --region us-east-1
"""

import json
import boto3
import argparse
import sys
from typing import Dict, Any, List


def create_performance_dashboard(cloudwatch_client, dashboard_name: str, stage: str) -> bool:
    """Create CloudWatch dashboard for performance monitoring."""
    
    dashboard_config = {
        "widgets": [
            {
                "type": "metric",
                "x": 0,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [f"AgentPier/{stage}", "ApiResponseTime", "Endpoint", "/trust/{agent_id}", "Method", "GET"],
                        [".", "ApiResponseTime", "Endpoint", "/vtokens/create", "Method", "POST"],
                        [".", "ApiResponseTime", "Endpoint", "/vtokens/verify", "Method", "POST"],
                        [".", "ApiResponseTime", "Endpoint", "/auth/challenge", "Method", "POST"],
                        [".", "ApiResponseTime", "Endpoint", "/auth/register", "Method", "POST"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "API Response Times by Endpoint",
                    "period": 300,
                    "stat": "Average",
                    "yAxis": {
                        "left": {
                            "label": "Milliseconds",
                            "showUnits": False
                        }
                    }
                }
            },
            {
                "type": "metric", 
                "x": 12,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [f"AgentPier/{stage}", "TrustCalculationTime"],
                        [".", "trace_total_duration", "TraceOperation", "trust_calculation"],
                        [".", "segment_duration_ace_score_calculation"],
                        [".", "segment_duration_clearinghouse_score_calculation"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "Trust Calculation Performance",
                    "period": 300,
                    "stat": "Average",
                    "yAxis": {
                        "left": {
                            "label": "Milliseconds",
                            "showUnits": False
                        }
                    }
                }
            },
            {
                "type": "metric",
                "x": 0,
                "y": 6,
                "width": 8,
                "height": 6,
                "properties": {
                    "metrics": [
                        [f"AgentPier/{stage}", "PerformanceRegressionAlert"],
                        [".", "trust_score_calculation_errors"],
                        [".", "CustomAPIErrorCount"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "Performance Alerts & Errors",
                    "period": 300,
                    "stat": "Sum",
                    "yAxis": {
                        "left": {
                            "label": "Count",
                            "showUnits": False
                        }
                    }
                }
            },
            {
                "type": "metric",
                "x": 8,
                "y": 6,
                "width": 8,
                "height": 6,
                "properties": {
                    "metrics": [
                        [f"AgentPier/{stage}", "CustomAPISuccessCount"],
                        [".", "CustomAPIRequestCount"],
                        [".", "TrustScoreCalculations"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "API Request Volume",
                    "period": 300,
                    "stat": "Sum",
                    "yAxis": {
                        "left": {
                            "label": "Count",
                            "showUnits": False
                        }
                    }
                }
            },
            {
                "type": "metric",
                "x": 16,
                "y": 6,
                "width": 8,
                "height": 6,
                "properties": {
                    "metrics": [
                        [f"AgentPier/{stage}", "trace_segment_count", "TraceOperation", "trust_calculation"],
                        [".", "trace_error_count", "TraceOperation", "trust_calculation"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "Distributed Trace Metrics",
                    "period": 300,
                    "stat": "Average"
                }
            },
            {
                "type": "metric",
                "x": 0,
                "y": 12,
                "width": 24,
                "height": 6,
                "properties": {
                    "metrics": [
                        [f"AgentPier/{stage}", "ApiResponseTime", "Endpoint", "/trust/{agent_id}", "Method", "GET"],
                        ["...", "/vtokens/create", ".", "POST"],
                        ["...", "/vtokens/verify", ".", "POST"],
                        ["...", "/auth/challenge", ".", "POST"],
                        ["...", "/auth/register", ".", "POST"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1", 
                    "title": "95th Percentile Response Times",
                    "period": 300,
                    "stat": "p95",
                    "yAxis": {
                        "left": {
                            "label": "Milliseconds",
                            "showUnits": False
                        }
                    }
                }
            }
        ]
    }
    
    try:
        cloudwatch_client.put_dashboard(
            DashboardName=dashboard_name,
            DashboardBody=json.dumps(dashboard_config)
        )
        print(f"✅ Created CloudWatch dashboard: {dashboard_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to create dashboard: {str(e)}")
        return False


def create_performance_alarms(cloudwatch_client, stage: str) -> bool:
    """Create CloudWatch alarms for performance monitoring."""
    
    alarms = [
        {
            "AlarmName": f"AgentPier-{stage}-Performance-Regression",
            "AlarmDescription": "Alert when performance regression is detected",
            "MetricName": "PerformanceRegressionAlert",
            "Namespace": f"AgentPier/{stage}",
            "Statistic": "Sum",
            "Period": 300,
            "EvaluationPeriods": 1,
            "Threshold": 1.0,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "TreatMissingData": "notBreaching"
        },
        {
            "AlarmName": f"AgentPier-{stage}-Trust-Calculation-Slow",
            "AlarmDescription": "Alert when trust calculations are consistently slow",
            "MetricName": "TrustCalculationTime", 
            "Namespace": f"AgentPier/{stage}",
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 2,
            "Threshold": 500.0,  # 500ms average
            "ComparisonOperator": "GreaterThanThreshold",
            "TreatMissingData": "notBreaching"
        },
        {
            "AlarmName": f"AgentPier-{stage}-API-Error-Rate-High",
            "AlarmDescription": "Alert when API error rate is high",
            "MetricName": "CustomAPIErrorCount",
            "Namespace": f"AgentPier/{stage}",
            "Statistic": "Sum",
            "Period": 300,
            "EvaluationPeriods": 2,
            "Threshold": 10.0,  # 10 errors in 5 minutes
            "ComparisonOperator": "GreaterThanThreshold",
            "TreatMissingData": "notBreaching"
        },
        {
            "AlarmName": f"AgentPier-{stage}-Trace-Error-Rate-High",
            "AlarmDescription": "Alert when distributed trace error rate is high",
            "MetricName": "trace_error_count",
            "Namespace": f"AgentPier/{stage}",
            "Statistic": "Sum",
            "Period": 300,
            "EvaluationPeriods": 2,
            "Threshold": 5.0,  # 5 trace errors in 5 minutes
            "ComparisonOperator": "GreaterThanThreshold",
            "TreatMissingData": "notBreaching",
            "Dimensions": [
                {
                    "Name": "TraceOperation",
                    "Value": "trust_calculation"
                }
            ]
        }
    ]
    
    success_count = 0
    for alarm_config in alarms:
        try:
            cloudwatch_client.put_metric_alarm(**alarm_config)
            print(f"✅ Created alarm: {alarm_config['AlarmName']}")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed to create alarm {alarm_config['AlarmName']}: {str(e)}")
    
    return success_count == len(alarms)


def create_baseline_update_schedule(events_client, lambda_client, stage: str, function_arn: str) -> bool:
    """Create EventBridge schedule for baseline updates."""
    
    rule_name = f"AgentPier-{stage}-Baseline-Update"
    
    try:
        # Create EventBridge rule
        events_client.put_rule(
            Name=rule_name,
            ScheduleExpression="cron(0 6 * * ? *)",  # 6 AM UTC daily
            Description=f"Daily performance baseline update for AgentPier {stage}",
            State="ENABLED"
        )
        
        # Add Lambda target
        events_client.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    "Id": "1",
                    "Arn": function_arn,
                    "Input": json.dumps({
                        "source": "scheduled-baseline-update",
                        "stage": stage
                    })
                }
            ]
        )
        
        # Add permission for EventBridge to invoke Lambda
        try:
            lambda_client.add_permission(
                FunctionName=function_arn,
                StatementId=f"baseline-update-{stage}",
                Action="lambda:InvokeFunction",
                Principal="events.amazonaws.com",
                SourceArn=f"arn:aws:events:us-east-1:*:rule/{rule_name}"
            )
        except lambda_client.exceptions.ResourceConflictException:
            # Permission already exists
            pass
        
        print(f"✅ Created baseline update schedule: {rule_name}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create baseline update schedule: {str(e)}")
        return False


def validate_monitoring_setup(cloudwatch_client, stage: str) -> Dict[str, Any]:
    """Validate that monitoring components are working correctly."""
    
    validation_results = {
        "dashboard_exists": False,
        "alarms_configured": False,
        "metrics_available": False,
        "issues": []
    }
    
    # Check dashboard exists
    try:
        dashboard_name = f"AgentPier-Performance-{stage.title()}"
        response = cloudwatch_client.get_dashboard(DashboardName=dashboard_name)
        validation_results["dashboard_exists"] = True
    except Exception as e:
        validation_results["issues"].append(f"Dashboard not found: {str(e)}")
    
    # Check alarms configured
    try:
        response = cloudwatch_client.describe_alarms(
            AlarmNamePrefix=f"AgentPier-{stage}-"
        )
        alarm_count = len(response.get("MetricAlarms", []))
        validation_results["alarms_configured"] = alarm_count >= 3
        if alarm_count < 3:
            validation_results["issues"].append(f"Only {alarm_count} alarms configured, expected at least 3")
    except Exception as e:
        validation_results["issues"].append(f"Failed to check alarms: {str(e)}")
    
    # Check if metrics are being received
    try:
        response = cloudwatch_client.list_metrics(
            Namespace=f"AgentPier/{stage}",
            MetricName="TrustCalculationTime"
        )
        metrics_count = len(response.get("Metrics", []))
        validation_results["metrics_available"] = metrics_count > 0
        if metrics_count == 0:
            validation_results["issues"].append("No trust calculation metrics found - may need time to populate")
    except Exception as e:
        validation_results["issues"].append(f"Failed to check metrics: {str(e)}")
    
    return validation_results


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup AgentPier performance monitoring")
    parser.add_argument("--stage", required=True, choices=["dev", "staging", "prod"], 
                       help="Deployment stage")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--function-arn", help="Lambda function ARN for baseline updates")
    parser.add_argument("--validate-only", action="store_true", 
                       help="Only validate existing setup")
    
    args = parser.parse_args()
    
    # Initialize AWS clients
    session = boto3.Session(region_name=args.region)
    cloudwatch_client = session.client("cloudwatch")
    events_client = session.client("events")
    lambda_client = session.client("lambda")
    
    dashboard_name = f"AgentPier-Performance-{args.stage.title()}"
    
    if args.validate_only:
        print(f"🔍 Validating performance monitoring setup for stage: {args.stage}")
        results = validate_monitoring_setup(cloudwatch_client, args.stage)
        
        print(f"Dashboard exists: {'✅' if results['dashboard_exists'] else '❌'}")
        print(f"Alarms configured: {'✅' if results['alarms_configured'] else '❌'}")
        print(f"Metrics available: {'✅' if results['metrics_available'] else '❌'}")
        
        if results["issues"]:
            print("\\nIssues found:")
            for issue in results["issues"]:
                print(f"  - {issue}")
        else:
            print("\\n✅ All monitoring components are properly configured!")
        
        return 0 if not results["issues"] else 1
    
    print(f"🚀 Setting up performance monitoring for AgentPier {args.stage}")
    
    success_count = 0
    total_steps = 3
    
    # Step 1: Create dashboard
    print("\\n1. Creating CloudWatch dashboard...")
    if create_performance_dashboard(cloudwatch_client, dashboard_name, args.stage):
        success_count += 1
    
    # Step 2: Create alarms  
    print("\\n2. Creating performance alarms...")
    if create_performance_alarms(cloudwatch_client, args.stage):
        success_count += 1
    
    # Step 3: Create baseline update schedule (if function ARN provided)
    print("\\n3. Setting up baseline update schedule...")
    if args.function_arn:
        if create_baseline_update_schedule(events_client, lambda_client, args.stage, args.function_arn):
            success_count += 1
    else:
        print("⚠️  No function ARN provided - skipping baseline update schedule")
        total_steps -= 1
    
    # Validation
    print("\\n4. Validating setup...")
    validation_results = validate_monitoring_setup(cloudwatch_client, args.stage)
    
    print(f"\\n📊 Setup completed: {success_count}/{total_steps} steps successful")
    
    if success_count == total_steps:
        print(f"\\n✅ Performance monitoring successfully configured for {args.stage}!")
        print(f"   Dashboard: https://console.aws.amazon.com/cloudwatch/home?region={args.region}#dashboards:name={dashboard_name}")
        print(f"   Alarms: https://console.aws.amazon.com/cloudwatch/home?region={args.region}#alarmsV2:")
    else:
        print(f"\\n⚠️  Setup completed with issues. Check the output above for details.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())