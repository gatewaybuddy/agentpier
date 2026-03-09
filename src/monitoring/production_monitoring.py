"""
AgentPier Production Monitoring Enhancement

Comprehensive production-grade observability with APM, business metrics,
anomaly detection, SLA monitoring, and operational dashboards.
"""

import os
import json
import time
import boto3
import statistics
import functools
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from decimal import Decimal
import uuid

# Import existing monitoring components
from monitoring.decorator import get_metrics_collector, track_operation
from monitoring.performance_monitoring import get_tracer, get_performance_benchmark


@dataclass
class SLAMetrics:
    """SLA performance metrics."""
    availability: float  # Percentage uptime
    latency_p99: float   # 99th percentile latency in ms
    error_rate: float    # Error rate percentage
    throughput: float    # Requests per second
    timestamp: str
    period_hours: int


@dataclass
class BusinessMetrics:
    """Core business metrics for AgentPier."""
    trust_scores_calculated: int
    vtokens_validated: int
    api_requests_total: int
    new_agent_registrations: int
    trust_tier_distributions: Dict[str, int]
    average_trust_score: float
    trust_score_anomalies: int
    timestamp: str


@dataclass
class AnomalyAlert:
    """Trust calculation anomaly alert."""
    agent_id: str
    metric_type: str  # 'score_jump', 'calculation_time', 'validation_failure'
    current_value: float
    expected_range: tuple  # (min, max)
    severity: str  # 'low', 'medium', 'high', 'critical'
    timestamp: str
    context: Dict[str, Any]


class ProductionMetricsCollector:
    """
    Enhanced metrics collection for production monitoring.
    Focuses on business metrics, SLA tracking, and anomaly detection.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.cloudwatch = boto3.client("cloudwatch")
        self.table_name = os.environ.get("TABLE_NAME", "agentpier-dev")
        self.table = self.dynamodb.Table(self.table_name)
        self.namespace = os.environ.get("METRICS_NAMESPACE", "AgentPier/Production")
    
    def collect_business_metrics(self, hours: int = 1) -> BusinessMetrics:
        """Collect core business metrics for the specified time period."""
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        # Initialize metrics
        metrics = {
            "trust_scores_calculated": 0,
            "vtokens_validated": 0,
            "api_requests_total": 0,
            "new_agent_registrations": 0,
            "trust_tier_distributions": {},
            "trust_score_sum": 0.0,
            "trust_score_count": 0,
            "trust_score_anomalies": 0
        }
        
        try:
            # Query for trust score calculations
            trust_calc_response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :cutoff",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":pk_prefix": "METRIC#TRUST_CALC#",
                    ":cutoff": cutoff_time
                },
                ProjectionExpression="calculation_result, trust_tier, calculation_time, agent_id"
            )
            
            for item in trust_calc_response.get("Items", []):
                metrics["trust_scores_calculated"] += 1
                
                if "calculation_result" in item:
                    score = float(item["calculation_result"])
                    metrics["trust_score_sum"] += score
                    metrics["trust_score_count"] += 1
                
                tier = item.get("trust_tier", "unknown")
                metrics["trust_tier_distributions"][tier] = metrics["trust_tier_distributions"].get(tier, 0) + 1
                
                # Simple anomaly detection for calculation time
                calc_time = float(item.get("calculation_time", 0))
                if calc_time > 5000:  # >5 seconds is anomalous
                    metrics["trust_score_anomalies"] += 1
            
            # Query for V-Token validations
            vtoken_response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :cutoff",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":pk_prefix": "METRIC#VTOKEN#",
                    ":cutoff": cutoff_time
                },
                ProjectionExpression="PK"
            )
            
            metrics["vtokens_validated"] = vtoken_response.get("Count", 0)
            
            # Query for API requests
            api_response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :cutoff",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":pk_prefix": "API_LOG#",
                    ":cutoff": cutoff_time
                },
                ProjectionExpression="PK"
            )
            
            metrics["api_requests_total"] = api_response.get("Count", 0)
            
            # Query for new agent registrations
            agent_response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND begins_with(SK, :sk_prefix) AND created_at >= :cutoff",
                ExpressionAttributeValues={
                    ":pk_prefix": "AGENT#",
                    ":sk_prefix": "METADATA",
                    ":cutoff": cutoff_time
                },
                ProjectionExpression="PK"
            )
            
            metrics["new_agent_registrations"] = agent_response.get("Count", 0)
            
        except Exception as e:
            print(f"Error collecting business metrics: {str(e)}")
        
        # Calculate average trust score
        average_trust_score = 0.0
        if metrics["trust_score_count"] > 0:
            average_trust_score = metrics["trust_score_sum"] / metrics["trust_score_count"]
        
        return BusinessMetrics(
            trust_scores_calculated=metrics["trust_scores_calculated"],
            vtokens_validated=metrics["vtokens_validated"],
            api_requests_total=metrics["api_requests_total"],
            new_agent_registrations=metrics["new_agent_registrations"],
            trust_tier_distributions=metrics["trust_tier_distributions"],
            average_trust_score=average_trust_score,
            trust_score_anomalies=metrics["trust_score_anomalies"],
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def calculate_sla_metrics(self, hours: int = 24) -> SLAMetrics:
        """Calculate SLA metrics for the specified period."""
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        try:
            # Get API logs for SLA calculation
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :cutoff",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":pk_prefix": "API_LOG#",
                    ":cutoff": cutoff_time
                },
                ProjectionExpression="status_code, response_time_ms, timestamp"
            )
            
            api_logs = response.get("Items", [])
            
            if not api_logs:
                return SLAMetrics(
                    availability=100.0,
                    latency_p99=0.0,
                    error_rate=0.0,
                    throughput=0.0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    period_hours=hours
                )
            
            # Calculate SLA metrics
            total_requests = len(api_logs)
            successful_requests = sum(1 for log in api_logs if 200 <= log.get("status_code", 500) < 400)
            error_requests = total_requests - successful_requests
            
            response_times = [float(log.get("response_time_ms", 0)) for log in api_logs]
            response_times.sort()
            
            availability = (successful_requests / total_requests) * 100 if total_requests > 0 else 100.0
            error_rate = (error_requests / total_requests) * 100 if total_requests > 0 else 0.0
            latency_p99 = response_times[int(len(response_times) * 0.99)] if response_times else 0.0
            throughput = total_requests / (hours * 3600)  # requests per second
            
            return SLAMetrics(
                availability=availability,
                latency_p99=latency_p99,
                error_rate=error_rate,
                throughput=throughput,
                timestamp=datetime.now(timezone.utc).isoformat(),
                period_hours=hours
            )
        
        except Exception as e:
            print(f"Error calculating SLA metrics: {str(e)}")
            return SLAMetrics(
                availability=0.0,
                latency_p99=0.0,
                error_rate=100.0,
                throughput=0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                period_hours=hours
            )
    
    def detect_trust_anomalies(self, agent_id: str) -> List[AnomalyAlert]:
        """Detect anomalies in trust calculations for a specific agent."""
        alerts = []
        
        try:
            # Get recent trust calculations for this agent
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": f"METRIC#TRUST_CALC#{agent_id}"},
                ScanIndexForward=False,  # Most recent first
                Limit=10
            )
            
            calculations = response.get("Items", [])
            
            if len(calculations) < 3:  # Need history for anomaly detection
                return alerts
            
            # Analyze trust score changes
            scores = [float(calc.get("calculation_result", 0)) for calc in calculations if "calculation_result" in calc]
            calc_times = [float(calc.get("calculation_time", 0)) for calc in calculations if "calculation_time" in calc]
            
            if len(scores) >= 3:
                # Check for sudden score jumps
                recent_score = scores[0]
                avg_historical = statistics.mean(scores[1:])
                score_change_percent = abs((recent_score - avg_historical) / avg_historical) * 100 if avg_historical > 0 else 0
                
                if score_change_percent > 25:  # 25% change is anomalous
                    alerts.append(AnomalyAlert(
                        agent_id=agent_id,
                        metric_type="score_jump",
                        current_value=recent_score,
                        expected_range=(avg_historical * 0.75, avg_historical * 1.25),
                        severity="high" if score_change_percent > 50 else "medium",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        context={"score_change_percent": score_change_percent, "historical_avg": avg_historical}
                    ))
            
            if len(calc_times) >= 3:
                # Check for calculation time anomalies
                recent_time = calc_times[0]
                avg_historical_time = statistics.mean(calc_times[1:])
                
                if recent_time > avg_historical_time * 3:  # 3x slower than usual
                    alerts.append(AnomalyAlert(
                        agent_id=agent_id,
                        metric_type="calculation_time",
                        current_value=recent_time,
                        expected_range=(0, avg_historical_time * 2),
                        severity="medium",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        context={"historical_avg_time": avg_historical_time}
                    ))
        
        except Exception as e:
            print(f"Error detecting trust anomalies for {agent_id}: {str(e)}")
        
        return alerts
    
    def send_business_metrics(self, metrics: BusinessMetrics):
        """Send business metrics to CloudWatch."""
        try:
            metric_data = [
                {
                    "MetricName": "TrustScoresCalculated",
                    "Value": metrics.trust_scores_calculated,
                    "Unit": "Count",
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "VTokensValidated", 
                    "Value": metrics.vtokens_validated,
                    "Unit": "Count",
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "ApiRequestsTotal",
                    "Value": metrics.api_requests_total,
                    "Unit": "Count",
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "NewAgentRegistrations",
                    "Value": metrics.new_agent_registrations,
                    "Unit": "Count",
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "AverageTrustScore",
                    "Value": metrics.average_trust_score,
                    "Unit": "None",
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "TrustScoreAnomalies",
                    "Value": metrics.trust_score_anomalies,
                    "Unit": "Count", 
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                }
            ]
            
            # Add trust tier distribution metrics
            for tier, count in metrics.trust_tier_distributions.items():
                metric_data.append({
                    "MetricName": "TrustTierDistribution",
                    "Value": count,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "TrustTier", "Value": tier}],
                    "Timestamp": datetime.fromisoformat(metrics.timestamp.replace('Z', '+00:00'))
                })
            
            # Send metrics in batches (CloudWatch limit: 20 metrics per call)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
        
        except Exception as e:
            print(f"Failed to send business metrics: {str(e)}")
    
    def send_sla_metrics(self, sla_metrics: SLAMetrics):
        """Send SLA metrics to CloudWatch."""
        try:
            metric_data = [
                {
                    "MetricName": "SLA_Availability",
                    "Value": sla_metrics.availability,
                    "Unit": "Percent",
                    "Timestamp": datetime.fromisoformat(sla_metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "SLA_Latency_P99",
                    "Value": sla_metrics.latency_p99,
                    "Unit": "Milliseconds", 
                    "Timestamp": datetime.fromisoformat(sla_metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "SLA_ErrorRate",
                    "Value": sla_metrics.error_rate,
                    "Unit": "Percent",
                    "Timestamp": datetime.fromisoformat(sla_metrics.timestamp.replace('Z', '+00:00'))
                },
                {
                    "MetricName": "SLA_Throughput",
                    "Value": sla_metrics.throughput,
                    "Unit": "Count/Second",
                    "Timestamp": datetime.fromisoformat(sla_metrics.timestamp.replace('Z', '+00:00'))
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace=f"{self.namespace}/SLA",
                MetricData=metric_data
            )
        
        except Exception as e:
            print(f"Failed to send SLA metrics: {str(e)}")
    
    def send_anomaly_alerts(self, alerts: List[AnomalyAlert]):
        """Send anomaly alerts as CloudWatch metrics."""
        try:
            for alert in alerts:
                # Send anomaly detection metric
                self.cloudwatch.put_metric_data(
                    Namespace=f"{self.namespace}/Anomalies",
                    MetricData=[{
                        "MetricName": f"TrustAnomaly_{alert.metric_type}",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "AgentId", "Value": alert.agent_id},
                            {"Name": "Severity", "Value": alert.severity}
                        ],
                        "Timestamp": datetime.fromisoformat(alert.timestamp.replace('Z', '+00:00'))
                    }]
                )
                
                # Store alert details in DynamoDB for investigation
                self.table.put_item(
                    Item={
                        "PK": f"ANOMALY#{alert.agent_id}",
                        "SK": f"{alert.metric_type}#{alert.timestamp}",
                        **asdict(alert),
                        "ttl": int(time.time()) + (30 * 24 * 60 * 60)  # 30 day TTL
                    }
                )
        
        except Exception as e:
            print(f"Failed to send anomaly alerts: {str(e)}")


# Global instance
_production_metrics = None


def get_production_metrics_collector() -> ProductionMetricsCollector:
    """Get the global production metrics collector."""
    global _production_metrics
    if _production_metrics is None:
        _production_metrics = ProductionMetricsCollector()
    return _production_metrics


def production_monitoring_handler(event, context):
    """
    Lambda handler for production metrics collection.
    Called every 5 minutes to collect business and SLA metrics.
    """
    try:
        collector = get_production_metrics_collector()
        
        # Collect business metrics (last hour)
        business_metrics = collector.collect_business_metrics(hours=1)
        collector.send_business_metrics(business_metrics)
        
        # Collect SLA metrics (last 24 hours)
        sla_metrics = collector.calculate_sla_metrics(hours=24)
        collector.send_sla_metrics(sla_metrics)
        
        # Check for anomalies in recent trust calculations
        # Get active agents from recent calculations
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        response = collector.table.scan(
            FilterExpression="begins_with(PK, :prefix) AND #ts >= :cutoff",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={
                ":prefix": "METRIC#TRUST_CALC#",
                ":cutoff": cutoff
            },
            ProjectionExpression="PK"
        )
        
        # Extract unique agent IDs
        agent_ids = set()
        for item in response.get("Items", []):
            pk_parts = item["PK"].split("#")
            if len(pk_parts) >= 3:
                agent_ids.add(pk_parts[2])
        
        # Check for anomalies in each active agent
        all_alerts = []
        for agent_id in agent_ids:
            alerts = collector.detect_trust_anomalies(agent_id)
            all_alerts.extend(alerts)
        
        if all_alerts:
            collector.send_anomaly_alerts(all_alerts)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "business_metrics": asdict(business_metrics),
                "sla_metrics": asdict(sla_metrics),
                "anomaly_alerts_sent": len(all_alerts)
            })
        }
    
    except Exception as e:
        print(f"Production monitoring handler error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def production_apm_decorator(operation_name: str, include_tracing: bool = True, include_anomaly_detection: bool = True):
    """
    Production APM decorator that combines distributed tracing with anomaly detection.
    
    Usage:
        @production_apm_decorator("trust_score_calculation", include_anomaly_detection=True)
        def calculate_trust_score(agent_id, events):
            # Your logic here
            return score
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            tracer = get_tracer()
            collector = get_production_metrics_collector()
            
            # Start distributed trace if enabled
            trace_id = None
            if include_tracing:
                if not tracer._current_trace:
                    trace_id = tracer.start_trace(operation_name)
            
            try:
                # Execute function with tracing
                if include_tracing:
                    with tracer.trace_segment(func.__name__, {"operation": operation_name}):
                        result = func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Record successful operation
                execution_time = (time.time() - start_time) * 1000
                
                # Store operation metrics for anomaly detection
                if include_anomaly_detection and operation_name == "trust_score_calculation":
                    # Extract agent_id from function args
                    agent_id = None
                    if args:
                        agent_id = args[0] if isinstance(args[0], str) else getattr(args[0], 'get', lambda x: None)('agent_id')
                    
                    if agent_id:
                        collector.table.put_item(
                            Item={
                                "PK": f"METRIC#TRUST_CALC#{agent_id}",
                                "SK": f"{int(time.time() * 1000)}",
                                "agent_id": agent_id,
                                "calculation_result": float(result) if isinstance(result, (int, float, Decimal)) else None,
                                "calculation_time": execution_time,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "operation": operation_name,
                                "ttl": int(time.time()) + (7 * 24 * 60 * 60)  # 7 day TTL
                            }
                        )
                
                return result
            
            except Exception as e:
                # Record failed operation
                execution_time = (time.time() - start_time) * 1000
                
                # Send error metric
                try:
                    collector.cloudwatch.put_metric_data(
                        Namespace=f"{collector.namespace}/Errors",
                        MetricData=[{
                            "MetricName": f"{operation_name}_errors",
                            "Value": 1,
                            "Unit": "Count",
                            "Timestamp": datetime.now(timezone.utc)
                        }]
                    )
                except:
                    pass  # Don't fail the original operation
                
                raise
            
            finally:
                # Finish trace if started
                if trace_id and include_tracing:
                    tracer.finish_trace(trace_id)
        
        return wrapper
    return decorator