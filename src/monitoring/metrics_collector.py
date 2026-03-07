"""
AgentPier Metrics Collector

Scheduled Lambda function that collects custom metrics and sends them to CloudWatch.
Focuses on trust score calculation accuracy, performance, and system health.
"""

import json
import os
import boto3
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional

# Import scoring utilities
from utils.ace_scoring import calculate_ace_score, calculate_clearinghouse_score
from utils.response import success, error


TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "AgentPier/dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _get_cloudwatch():
    return boto3.client("cloudwatch")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def collect_trust_score_metrics(table, cloudwatch) -> Dict[str, Any]:
    """
    Collect metrics about trust score calculations.
    
    Returns:
        Dict with collected metrics
    """
    metrics = {
        "calculations_attempted": 0,
        "calculations_succeeded": 0,
        "calculations_failed": 0,
        "average_calculation_time": 0.0,
        "score_accuracy_samples": [],
        "error_types": []
    }
    
    try:
        # Get agents with recent trust score calculations (last 5 minutes)
        five_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        
        response = table.scan(
            FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :timestamp",
            ExpressionAttributeNames={
                "#ts": "last_calculated"
            },
            ExpressionAttributeValues={
                ":pk_prefix": "AGENT#",
                ":timestamp": five_minutes_ago
            },
            ProjectionExpression="PK, SK, agent_id, trust_score, last_calculated, calculation_time_ms"
        )
        
        agents = response.get("Items", [])
        
        for agent in agents:
            metrics["calculations_attempted"] += 1
            
            # Test score calculation accuracy by recalculating
            agent_id = agent.get("agent_id")
            if agent_id:
                start_time = time.time()
                
                try:
                    # Get agent events for scoring
                    events_response = table.query(
                        KeyConditionExpression="PK = :pk",
                        ExpressionAttributeValues={
                            ":pk": f"AGENT#{agent_id}#EVENTS"
                        }
                    )
                    
                    events = events_response.get("Items", [])
                    
                    # Recalculate trust score
                    calculated_score = calculate_ace_score(events)
                    stored_score = float(agent.get("trust_score", 0))
                    
                    calculation_time = (time.time() - start_time) * 1000  # ms
                    metrics["calculations_succeeded"] += 1
                    
                    # Track calculation time
                    if metrics["average_calculation_time"] == 0:
                        metrics["average_calculation_time"] = calculation_time
                    else:
                        metrics["average_calculation_time"] = (
                            metrics["average_calculation_time"] + calculation_time
                        ) / 2
                    
                    # Check accuracy (difference between stored and calculated)
                    score_difference = abs(stored_score - calculated_score)
                    accuracy = max(0, 100 - score_difference)  # Simple accuracy metric
                    metrics["score_accuracy_samples"].append(accuracy)
                    
                except Exception as e:
                    metrics["calculations_failed"] += 1
                    metrics["error_types"].append(str(type(e).__name__))
                    print(f"Error calculating score for agent {agent_id}: {str(e)}")
    
    except Exception as e:
        print(f"Error collecting trust score metrics: {str(e)}")
        return metrics
    
    return metrics


def collect_api_performance_metrics(table) -> Dict[str, Any]:
    """
    Collect metrics about API performance from recent requests.
    
    Returns:
        Dict with API performance metrics
    """
    metrics = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "average_response_time": 0.0
    }
    
    try:
        # Get API request logs from last 5 minutes
        five_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        
        response = table.scan(
            FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :timestamp",
            ExpressionAttributeNames={
                "#ts": "timestamp"
            },
            ExpressionAttributeValues={
                ":pk_prefix": "API_LOG#",
                ":timestamp": five_minutes_ago
            },
            ProjectionExpression="PK, SK, status_code, response_time_ms"
        )
        
        logs = response.get("Items", [])
        
        total_time = 0
        for log in logs:
            metrics["total_requests"] += 1
            
            status_code = log.get("status_code", 500)
            response_time = float(log.get("response_time_ms", 0))
            
            if 200 <= status_code < 400:
                metrics["successful_requests"] += 1
            else:
                metrics["failed_requests"] += 1
            
            total_time += response_time
        
        if metrics["total_requests"] > 0:
            metrics["average_response_time"] = total_time / metrics["total_requests"]
    
    except Exception as e:
        print(f"Error collecting API performance metrics: {str(e)}")
    
    return metrics


def send_metrics_to_cloudwatch(cloudwatch, metrics: Dict[str, Any]) -> bool:
    """
    Send collected metrics to CloudWatch.
    
    Args:
        cloudwatch: CloudWatch client
        metrics: Dict of metrics to send
        
    Returns:
        True if successful, False otherwise
    """
    try:
        metric_data = []
        timestamp = datetime.now(timezone.utc)
        
        # Trust score metrics
        trust_metrics = metrics.get("trust_score_metrics", {})
        if trust_metrics:
            metric_data.extend([
                {
                    "MetricName": "TrustScoreCalculations",
                    "Value": trust_metrics.get("calculations_attempted", 0),
                    "Unit": "Count",
                    "Timestamp": timestamp
                },
                {
                    "MetricName": "TrustScoreCalculationErrors",
                    "Value": trust_metrics.get("calculations_failed", 0),
                    "Unit": "Count",
                    "Timestamp": timestamp
                },
                {
                    "MetricName": "AverageScoreCalculationTime",
                    "Value": trust_metrics.get("average_calculation_time", 0),
                    "Unit": "Milliseconds",
                    "Timestamp": timestamp
                }
            ])
            
            # Trust score accuracy (average of samples)
            accuracy_samples = trust_metrics.get("score_accuracy_samples", [])
            if accuracy_samples:
                avg_accuracy = sum(accuracy_samples) / len(accuracy_samples)
                metric_data.append({
                    "MetricName": "TrustScoreAccuracy",
                    "Value": avg_accuracy,
                    "Unit": "Percent",
                    "Timestamp": timestamp
                })
        
        # API performance metrics
        api_metrics = metrics.get("api_performance_metrics", {})
        if api_metrics:
            metric_data.extend([
                {
                    "MetricName": "CustomAPIRequestCount",
                    "Value": api_metrics.get("total_requests", 0),
                    "Unit": "Count",
                    "Timestamp": timestamp
                },
                {
                    "MetricName": "CustomAPISuccessCount",
                    "Value": api_metrics.get("successful_requests", 0),
                    "Unit": "Count",
                    "Timestamp": timestamp
                },
                {
                    "MetricName": "CustomAPIErrorCount",
                    "Value": api_metrics.get("failed_requests", 0),
                    "Unit": "Count",
                    "Timestamp": timestamp
                },
                {
                    "MetricName": "CustomAPIAverageResponseTime",
                    "Value": api_metrics.get("average_response_time", 0),
                    "Unit": "Milliseconds",
                    "Timestamp": timestamp
                }
            ])
        
        # Send metrics in batches (CloudWatch limit is 20 metrics per call)
        batch_size = 20
        for i in range(0, len(metric_data), batch_size):
            batch = metric_data[i:i + batch_size]
            cloudwatch.put_metric_data(
                Namespace=METRICS_NAMESPACE,
                MetricData=batch
            )
        
        return True
    
    except Exception as e:
        print(f"Error sending metrics to CloudWatch: {str(e)}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler for metrics collection.
    
    Args:
        event: Lambda event (from scheduled trigger)
        context: Lambda context
        
    Returns:
        Dict with status and collected metrics
    """
    print(f"Starting metrics collection at {_now_iso()}")
    
    try:
        table = _get_table()
        cloudwatch = _get_cloudwatch()
        
        # Collect metrics
        trust_score_metrics = collect_trust_score_metrics(table, cloudwatch)
        api_performance_metrics = collect_api_performance_metrics(table)
        
        metrics = {
            "trust_score_metrics": trust_score_metrics,
            "api_performance_metrics": api_performance_metrics,
            "collection_timestamp": _now_iso()
        }
        
        # Send to CloudWatch
        success_sent = send_metrics_to_cloudwatch(cloudwatch, metrics)
        
        result = {
            "status": "success" if success_sent else "partial_failure",
            "metrics_collected": metrics,
            "cloudwatch_sent": success_sent,
            "timestamp": _now_iso()
        }
        
        print(f"Metrics collection completed: {json.dumps(result, indent=2, default=str)}")
        return success(result)
    
    except Exception as e:
        error_msg = f"Metrics collection failed: {str(e)}"
        print(error_msg)
        return error(error_msg, 500)


# Alias for CloudFormation handler reference
metrics_collector = lambda_handler