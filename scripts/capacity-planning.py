#!/usr/bin/env python3
"""
AgentPier Capacity Planning and SLA Management

Automated capacity analysis, scaling recommendations, and SLA monitoring.
Generates actionable insights for production infrastructure management.
"""

import boto3
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
import statistics
import argparse
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class CapacityMetrics:
    """Capacity metrics for a service component."""
    service: str
    current_utilization_percent: float
    peak_utilization_percent: float
    average_utilization_percent: float
    growth_rate_percent: float  # Week over week
    projected_capacity_need: float
    days_until_capacity_limit: Optional[int]
    recommendations: List[str]


@dataclass
class SLAReport:
    """SLA performance report."""
    period_start: str
    period_end: str
    availability: float
    latency_p99: float
    latency_p95: float
    error_rate: float
    throughput_rps: float
    sla_breaches: List[Dict]
    overall_health: str  # 'healthy', 'warning', 'critical'


class CapacityPlanner:
    """Automated capacity planning and SLA monitoring."""
    
    def __init__(self, stage: str = "dev"):
        self.stage = stage
        self.cloudwatch = boto3.client("cloudwatch")
        self.dynamodb = boto3.resource("dynamodb")
        self.lambda_client = boto3.client("lambda")
        self.table_name = f"agentpier-{stage}"
        
        # SLA Targets
        self.sla_targets = {
            "availability": 99.5,      # 99.5% uptime
            "latency_p99": 2000,       # 2 seconds
            "error_rate": 1.0          # 1% error rate
        }
    
    def get_cloudwatch_metrics(self, namespace: str, metric_name: str, 
                             dimensions: List[Dict], hours: int = 24,
                             statistic: str = "Average") -> List[Dict]:
        """Fetch CloudWatch metrics for analysis."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            response = self.cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=[statistic]
            )
            
            return sorted(response.get("Datapoints", []), key=lambda x: x["Timestamp"])
        
        except Exception as e:
            print(f"Error fetching metrics {namespace}/{metric_name}: {str(e)}")
            return []
    
    def analyze_lambda_capacity(self) -> CapacityMetrics:
        """Analyze Lambda function capacity and performance."""
        function_name = f"agentpier-trust-scoring-{self.stage}"
        
        # Get concurrent executions
        concurrent_metrics = self.get_cloudwatch_metrics(
            "AWS/Lambda",
            "ConcurrentExecutions",
            [{"Name": "FunctionName", "Value": function_name}],
            hours=168,  # 7 days
            statistic="Maximum"
        )
        
        # Get duration metrics
        duration_metrics = self.get_cloudwatch_metrics(
            "AWS/Lambda", 
            "Duration",
            [{"Name": "FunctionName", "Value": function_name}],
            hours=168,
            statistic="Average"
        )
        
        if not concurrent_metrics:
            return CapacityMetrics(
                service="Lambda",
                current_utilization_percent=0,
                peak_utilization_percent=0,
                average_utilization_percent=0,
                growth_rate_percent=0,
                projected_capacity_need=0,
                days_until_capacity_limit=None,
                recommendations=["No metrics available - check Lambda deployment"]
            )
        
        # Calculate utilization metrics
        concurrent_values = [m["Maximum"] for m in concurrent_metrics]
        current_concurrent = concurrent_values[-1] if concurrent_values else 0
        peak_concurrent = max(concurrent_values) if concurrent_values else 0
        avg_concurrent = statistics.mean(concurrent_values) if concurrent_values else 0
        
        # Lambda has 1000 concurrent execution limit by default
        lambda_limit = 1000
        current_utilization = (current_concurrent / lambda_limit) * 100
        peak_utilization = (peak_concurrent / lambda_limit) * 100
        avg_utilization = (avg_concurrent / lambda_limit) * 100
        
        # Calculate growth rate (week over week)
        if len(concurrent_values) >= 168:  # 7 days of hourly data
            recent_week = concurrent_values[-168:]
            previous_week = concurrent_values[-336:-168] if len(concurrent_values) >= 336 else []
            
            if previous_week:
                recent_avg = statistics.mean(recent_week)
                previous_avg = statistics.mean(previous_week)
                growth_rate = ((recent_avg - previous_avg) / previous_avg) * 100 if previous_avg > 0 else 0
            else:
                growth_rate = 0
        else:
            growth_rate = 0
        
        # Project capacity needs
        if growth_rate > 0:
            weeks_to_limit = ((lambda_limit * 0.8) - avg_concurrent) / (avg_concurrent * (growth_rate / 100))
            days_until_limit = int(weeks_to_limit * 7) if weeks_to_limit > 0 else None
        else:
            days_until_limit = None
        
        projected_need = avg_concurrent * (1 + (growth_rate / 100) * 4)  # 4 weeks ahead
        
        # Generate recommendations
        recommendations = []
        if peak_utilization > 70:
            recommendations.append("Consider increasing Lambda concurrent execution limit")
        if growth_rate > 20:
            recommendations.append("High growth rate detected - monitor capacity closely")
        if len(duration_metrics) > 0:
            avg_duration = statistics.mean([m["Average"] for m in duration_metrics])
            if avg_duration > 10000:  # >10 seconds
                recommendations.append("Optimize Lambda function performance - high average duration")
        
        if not recommendations:
            recommendations.append("Lambda capacity is healthy")
        
        return CapacityMetrics(
            service="Lambda",
            current_utilization_percent=current_utilization,
            peak_utilization_percent=peak_utilization,
            average_utilization_percent=avg_utilization,
            growth_rate_percent=growth_rate,
            projected_capacity_need=projected_need,
            days_until_capacity_limit=days_until_limit,
            recommendations=recommendations
        )
    
    def analyze_dynamodb_capacity(self) -> CapacityMetrics:
        """Analyze DynamoDB capacity and performance."""
        table_name = self.table_name
        
        # Get read capacity metrics
        read_metrics = self.get_cloudwatch_metrics(
            "AWS/DynamoDB",
            "ConsumedReadCapacityUnits",
            [{"Name": "TableName", "Value": table_name}],
            hours=168,  # 7 days
            statistic="Sum"
        )
        
        # Get write capacity metrics
        write_metrics = self.get_cloudwatch_metrics(
            "AWS/DynamoDB",
            "ConsumedWriteCapacityUnits", 
            [{"Name": "TableName", "Value": table_name}],
            hours=168,
            statistic="Sum"
        )
        
        if not read_metrics and not write_metrics:
            return CapacityMetrics(
                service="DynamoDB",
                current_utilization_percent=0,
                peak_utilization_percent=0,
                average_utilization_percent=0,
                growth_rate_percent=0,
                projected_capacity_need=0,
                days_until_capacity_limit=None,
                recommendations=["No metrics available - check DynamoDB table"]
            )
        
        # Assume 25 RCU/WCU provisioned capacity (adjust based on your setup)
        provisioned_read = 25
        provisioned_write = 25
        
        # Calculate read utilization
        read_values = [m["Sum"] / 3600 for m in read_metrics] if read_metrics else [0]  # Convert to per-second
        current_read = read_values[-1] if read_values else 0
        peak_read = max(read_values) if read_values else 0
        avg_read = statistics.mean(read_values) if read_values else 0
        
        # Calculate write utilization  
        write_values = [m["Sum"] / 3600 for m in write_metrics] if write_metrics else [0]
        current_write = write_values[-1] if write_values else 0
        peak_write = max(write_values) if write_values else 0
        avg_write = statistics.mean(write_values) if write_values else 0
        
        # Use higher utilization between read and write
        current_utilization = max(
            (current_read / provisioned_read) * 100,
            (current_write / provisioned_write) * 100
        )
        peak_utilization = max(
            (peak_read / provisioned_read) * 100,
            (peak_write / provisioned_write) * 100
        )
        avg_utilization = max(
            (avg_read / provisioned_read) * 100,
            (avg_write / provisioned_write) * 100
        )
        
        # Calculate growth rate
        if len(read_values) >= 168 and len(write_values) >= 168:
            recent_read = statistics.mean(read_values[-168:])
            recent_write = statistics.mean(write_values[-168:])
            
            if len(read_values) >= 336:
                previous_read = statistics.mean(read_values[-336:-168])
                previous_write = statistics.mean(write_values[-336:-168])
                
                read_growth = ((recent_read - previous_read) / previous_read) * 100 if previous_read > 0 else 0
                write_growth = ((recent_write - previous_write) / previous_write) * 100 if previous_write > 0 else 0
                growth_rate = max(read_growth, write_growth)
            else:
                growth_rate = 0
        else:
            growth_rate = 0
        
        # Project capacity needs
        projected_read = avg_read * (1 + (growth_rate / 100) * 4)
        projected_write = avg_write * (1 + (growth_rate / 100) * 4)
        projected_need = max(projected_read, projected_write)
        
        # Days until capacity limit
        if growth_rate > 0:
            capacity_limit = max(provisioned_read * 0.8, provisioned_write * 0.8)
            current_usage = max(avg_read, avg_write)
            weeks_to_limit = (capacity_limit - current_usage) / (current_usage * (growth_rate / 100))
            days_until_limit = int(weeks_to_limit * 7) if weeks_to_limit > 0 else None
        else:
            days_until_limit = None
        
        # Generate recommendations
        recommendations = []
        if peak_utilization > 70:
            recommendations.append("Consider enabling DynamoDB auto-scaling or increasing provisioned capacity")
        if growth_rate > 30:
            recommendations.append("High growth rate - monitor DynamoDB capacity closely")
        if current_utilization < 20:
            recommendations.append("DynamoDB may be over-provisioned - consider reducing capacity")
        
        if not recommendations:
            recommendations.append("DynamoDB capacity is healthy")
        
        return CapacityMetrics(
            service="DynamoDB",
            current_utilization_percent=current_utilization,
            peak_utilization_percent=peak_utilization,
            average_utilization_percent=avg_utilization,
            growth_rate_percent=growth_rate,
            projected_capacity_need=projected_need,
            days_until_capacity_limit=days_until_limit,
            recommendations=recommendations
        )
    
    def generate_sla_report(self, hours: int = 24) -> SLAReport:
        """Generate comprehensive SLA performance report."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        # Get SLA metrics
        availability_metrics = self.get_cloudwatch_metrics(
            f"AgentPier/{self.stage}/SLA",
            "SLA_Availability",
            [],
            hours=hours
        )
        
        latency_metrics = self.get_cloudwatch_metrics(
            f"AgentPier/{self.stage}/SLA",
            "SLA_Latency_P99", 
            [],
            hours=hours
        )
        
        error_rate_metrics = self.get_cloudwatch_metrics(
            f"AgentPier/{self.stage}/SLA",
            "SLA_ErrorRate",
            [],
            hours=hours
        )
        
        throughput_metrics = self.get_cloudwatch_metrics(
            f"AgentPier/{self.stage}/SLA",
            "SLA_Throughput",
            [],
            hours=hours
        )
        
        # Calculate SLA performance
        availability = statistics.mean([m["Average"] for m in availability_metrics]) if availability_metrics else 0
        latency_p99 = statistics.mean([m["Average"] for m in latency_metrics]) if latency_metrics else 0
        error_rate = statistics.mean([m["Average"] for m in error_rate_metrics]) if error_rate_metrics else 0
        throughput = statistics.mean([m["Average"] for m in throughput_metrics]) if throughput_metrics else 0
        
        # Calculate P95 latency (approximate)
        latency_p95 = latency_p99 * 0.8 if latency_p99 > 0 else 0
        
        # Identify SLA breaches
        sla_breaches = []
        
        if availability < self.sla_targets["availability"]:
            sla_breaches.append({
                "metric": "availability",
                "target": self.sla_targets["availability"],
                "actual": availability,
                "severity": "high"
            })
        
        if latency_p99 > self.sla_targets["latency_p99"]:
            sla_breaches.append({
                "metric": "latency_p99",
                "target": self.sla_targets["latency_p99"],
                "actual": latency_p99,
                "severity": "medium" if latency_p99 < self.sla_targets["latency_p99"] * 1.5 else "high"
            })
        
        if error_rate > self.sla_targets["error_rate"]:
            sla_breaches.append({
                "metric": "error_rate",
                "target": self.sla_targets["error_rate"],
                "actual": error_rate,
                "severity": "high"
            })
        
        # Determine overall health
        if sla_breaches:
            high_severity_breaches = [b for b in sla_breaches if b["severity"] == "high"]
            if high_severity_breaches:
                overall_health = "critical"
            else:
                overall_health = "warning"
        else:
            overall_health = "healthy"
        
        return SLAReport(
            period_start=start_time.isoformat(),
            period_end=end_time.isoformat(),
            availability=availability,
            latency_p99=latency_p99,
            latency_p95=latency_p95,
            error_rate=error_rate,
            throughput_rps=throughput,
            sla_breaches=sla_breaches,
            overall_health=overall_health
        )
    
    def generate_capacity_report(self) -> Dict[str, Any]:
        """Generate comprehensive capacity planning report."""
        lambda_capacity = self.analyze_lambda_capacity()
        dynamodb_capacity = self.analyze_dynamodb_capacity()
        sla_report = self.generate_sla_report(hours=24)
        
        # Generate overall recommendations
        overall_recommendations = []
        
        critical_services = []
        if lambda_capacity.days_until_capacity_limit and lambda_capacity.days_until_capacity_limit < 30:
            critical_services.append("Lambda")
        if dynamodb_capacity.days_until_capacity_limit and dynamodb_capacity.days_until_capacity_limit < 30:
            critical_services.append("DynamoDB")
        
        if critical_services:
            overall_recommendations.append(f"URGENT: {', '.join(critical_services)} approaching capacity limits within 30 days")
        
        if sla_report.overall_health == "critical":
            overall_recommendations.append("CRITICAL: SLA breaches detected - immediate attention required")
        elif sla_report.overall_health == "warning":
            overall_recommendations.append("WARNING: SLA performance degraded - monitor closely")
        
        high_growth_services = []
        if lambda_capacity.growth_rate_percent > 25:
            high_growth_services.append("Lambda")
        if dynamodb_capacity.growth_rate_percent > 25:
            high_growth_services.append("DynamoDB")
        
        if high_growth_services:
            overall_recommendations.append(f"High growth detected in {', '.join(high_growth_services)} - plan capacity scaling")
        
        if not overall_recommendations:
            overall_recommendations.append("System capacity and SLA performance are healthy")
        
        return {
            "report_timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self.stage,
            "capacity_analysis": {
                "lambda": asdict(lambda_capacity),
                "dynamodb": asdict(dynamodb_capacity)
            },
            "sla_report": asdict(sla_report),
            "overall_recommendations": overall_recommendations,
            "summary": {
                "services_at_risk": len(critical_services),
                "sla_health": sla_report.overall_health,
                "immediate_action_required": len([r for r in overall_recommendations if "URGENT" in r or "CRITICAL" in r]) > 0
            }
        }


def main():
    parser = argparse.ArgumentParser(description="AgentPier Capacity Planning and SLA Management")
    parser.add_argument("--stage", default="dev", help="Deployment stage")
    parser.add_argument("--hours", type=int, default=24, help="Analysis period in hours")
    parser.add_argument("--output", help="Output file for report (JSON format)")
    parser.add_argument("--format", choices=["json", "summary"], default="summary", help="Output format")
    
    args = parser.parse_args()
    
    planner = CapacityPlanner(stage=args.stage)
    report = planner.generate_capacity_report()
    
    if args.format == "json":
        output = json.dumps(report, indent=2)
    else:
        # Generate summary format
        summary_lines = [
            f"AgentPier Capacity Planning Report - {args.stage.upper()}",
            f"Generated: {report['report_timestamp']}",
            "=" * 60,
            "",
            "CAPACITY ANALYSIS:",
            f"  Lambda Utilization: {report['capacity_analysis']['lambda']['current_utilization_percent']:.1f}% (Peak: {report['capacity_analysis']['lambda']['peak_utilization_percent']:.1f}%)",
            f"  DynamoDB Utilization: {report['capacity_analysis']['dynamodb']['current_utilization_percent']:.1f}% (Peak: {report['capacity_analysis']['dynamodb']['peak_utilization_percent']:.1f}%)",
            "",
            "SLA PERFORMANCE:",
            f"  Availability: {report['sla_report']['availability']:.2f}% (Target: {planner.sla_targets['availability']}%)",
            f"  Latency P99: {report['sla_report']['latency_p99']:.0f}ms (Target: <{planner.sla_targets['latency_p99']}ms)",
            f"  Error Rate: {report['sla_report']['error_rate']:.2f}% (Target: <{planner.sla_targets['error_rate']}%)",
            f"  Overall Health: {report['sla_report']['overall_health'].upper()}",
            "",
            "RECOMMENDATIONS:",
        ]
        
        for rec in report['overall_recommendations']:
            summary_lines.append(f"  • {rec}")
        
        summary_lines.extend([
            "",
            "DETAILED RECOMMENDATIONS:",
            "  Lambda:",
        ])
        
        for rec in report['capacity_analysis']['lambda']['recommendations']:
            summary_lines.append(f"    • {rec}")
        
        summary_lines.append("  DynamoDB:")
        for rec in report['capacity_analysis']['dynamodb']['recommendations']:
            summary_lines.append(f"    • {rec}")
        
        output = "\n".join(summary_lines)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()