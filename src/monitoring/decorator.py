"""
AgentPier Monitoring Decorator

Provides decorators and context managers for automatic metrics collection
in Lambda functions and trust score calculations.
"""

import time
import json
import boto3
import functools
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager


class MetricsCollector:
    """
    Collects and sends metrics to CloudWatch.
    """
    
    def __init__(self, namespace: str = "AgentPier/dev"):
        self.namespace = namespace
        self._cloudwatch = None
    
    @property
    def cloudwatch(self):
        if self._cloudwatch is None:
            self._cloudwatch = boto3.client("cloudwatch")
        return self._cloudwatch
    
    def send_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[Dict[str, str]] = None
    ):
        """
        Send a single metric to CloudWatch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: CloudWatch unit (Count, Milliseconds, Percent, etc.)
            dimensions: Optional metric dimensions
        """
        try:
            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.now(timezone.utc)
            }
            
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
        except Exception as e:
            # Don't fail the main operation if metrics fail
            print(f"Failed to send metric {metric_name}: {str(e)}")
    
    def send_metrics_batch(self, metrics: list):
        """
        Send multiple metrics in a batch.
        
        Args:
            metrics: List of metric dicts
        """
        try:
            # Add timestamps if not present
            for metric in metrics:
                if "Timestamp" not in metric:
                    metric["Timestamp"] = datetime.now(timezone.utc)
            
            # Send in batches of 20 (CloudWatch limit)
            batch_size = 20
            for i in range(0, len(metrics), batch_size):
                batch = metrics[i:i + batch_size]
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
        except Exception as e:
            print(f"Failed to send metrics batch: {str(e)}")


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        namespace = f"AgentPier/{os.environ.get('STAGE', 'dev')}"
        _metrics_collector = MetricsCollector(namespace)
    return _metrics_collector


def monitor_lambda_function(
    function_name: Optional[str] = None,
    include_duration: bool = True,
    include_memory: bool = True,
    custom_metrics: Optional[Dict[str, Any]] = None
):
    """
    Decorator to monitor Lambda function execution.
    
    Args:
        function_name: Optional function name (defaults to decorated function name)
        include_duration: Whether to track execution duration
        include_memory: Whether to track memory usage
        custom_metrics: Additional metrics to send
    
    Usage:
        @monitor_lambda_function("trust_score_calculation")
        def calculate_trust_score(agent_id):
            # Your function logic
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics_collector = get_metrics_collector()
            func_name = function_name or func.__name__
            
            try:
                result = func(*args, **kwargs)
                
                # Success metrics
                metrics_collector.send_metric(
                    f"{func_name}_invocations",
                    1,
                    "Count"
                )
                
                metrics_collector.send_metric(
                    f"{func_name}_successes",
                    1,
                    "Count"
                )
                
                # Duration tracking
                if include_duration:
                    duration_ms = (time.time() - start_time) * 1000
                    metrics_collector.send_metric(
                        f"{func_name}_duration",
                        duration_ms,
                        "Milliseconds"
                    )
                
                # Custom metrics
                if custom_metrics:
                    for metric_name, value in custom_metrics.items():
                        metrics_collector.send_metric(
                            f"{func_name}_{metric_name}",
                            value,
                            "Count"
                        )
                
                return result
                
            except Exception as e:
                # Error metrics
                metrics_collector.send_metric(
                    f"{func_name}_errors",
                    1,
                    "Count",
                    dimensions={"ErrorType": type(e).__name__}
                )
                
                raise
        
        return wrapper
    return decorator


def monitor_trust_score_calculation(
    include_accuracy: bool = True,
    include_score_distribution: bool = False
):
    """
    Decorator specifically for trust score calculation monitoring.
    
    Args:
        include_accuracy: Whether to track score calculation accuracy
        include_score_distribution: Whether to track score distribution
    
    Usage:
        @monitor_trust_score_calculation(include_accuracy=True)
        def calculate_ace_score(events):
            # Your scoring logic
            return score
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics_collector = get_metrics_collector()
            
            try:
                result = func(*args, **kwargs)
                
                # Basic metrics
                metrics_collector.send_metric("trust_score_calculations", 1, "Count")
                
                calculation_time = (time.time() - start_time) * 1000
                metrics_collector.send_metric(
                    "trust_score_calculation_time",
                    calculation_time,
                    "Milliseconds"
                )
                
                # Score distribution tracking
                if include_score_distribution and isinstance(result, (int, float)):
                    score_tier = "tier_unknown"
                    if result >= 80:
                        score_tier = "tier_4_excellent"
                    elif result >= 60:
                        score_tier = "tier_3_good"
                    elif result >= 40:
                        score_tier = "tier_2_fair"
                    elif result >= 20:
                        score_tier = "tier_1_poor"
                    else:
                        score_tier = "tier_0_untrustworthy"
                    
                    metrics_collector.send_metric(
                        "trust_score_distribution",
                        1,
                        "Count",
                        dimensions={"ScoreTier": score_tier}
                    )
                
                return result
                
            except Exception as e:
                metrics_collector.send_metric(
                    "trust_score_calculation_errors",
                    1,
                    "Count",
                    dimensions={"ErrorType": type(e).__name__}
                )
                raise
        
        return wrapper
    return decorator


@contextmanager
def track_operation(operation_name: str, **kwargs):
    """
    Context manager for tracking operations.
    
    Args:
        operation_name: Name of the operation to track
        **kwargs: Additional dimensions for the metric
    
    Usage:
        with track_operation("database_query", table="agents"):
            # Your database operation
            result = table.query(...)
    """
    start_time = time.time()
    metrics_collector = get_metrics_collector()
    
    try:
        yield
        
        # Success metrics
        metrics_collector.send_metric(
            f"{operation_name}_count",
            1,
            "Count"
        )
        
        duration_ms = (time.time() - start_time) * 1000
        metrics_collector.send_metric(
            f"{operation_name}_duration",
            duration_ms,
            "Milliseconds",
            dimensions=kwargs
        )
        
    except Exception as e:
        # Error metrics
        metrics_collector.send_metric(
            f"{operation_name}_errors",
            1,
            "Count",
            dimensions={**kwargs, "ErrorType": type(e).__name__}
        )
        raise


def track_api_request(table, request_id: str, method: str, path: str, status_code: int, response_time_ms: float):
    """
    Track API request metrics in DynamoDB for later analysis.
    
    Args:
        table: DynamoDB table resource
        request_id: Unique request identifier
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        response_time_ms: Response time in milliseconds
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        table.put_item(
            Item={
                "PK": f"API_LOG#{timestamp[:10]}",  # Partition by date
                "SK": f"{timestamp}#{request_id}",
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "timestamp": timestamp,
                "ttl": int(time.time()) + (7 * 24 * 60 * 60)  # 7 day TTL
            }
        )
    except Exception as e:
        print(f"Failed to log API request metrics: {str(e)}")


# Import os module for environment variables
import os