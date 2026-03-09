"""
AgentPier Production Monitoring Integration

Integrates production monitoring with existing AgentPier services.
Provides decorators and middleware for seamless monitoring integration.
"""

import functools
from typing import Callable, Any, Dict, Optional
from monitoring.production_monitoring import (
    production_apm_decorator,
    get_production_metrics_collector
)
from monitoring.performance_monitoring import (
    monitor_api_performance,
    trace_trust_calculation
)


def production_monitor(
    operation_name: str,
    include_business_metrics: bool = True,
    include_anomaly_detection: bool = True,
    include_performance_tracking: bool = True
):
    """
    Comprehensive production monitoring decorator.
    
    Combines APM, business metrics, anomaly detection, and performance tracking
    into a single decorator for easy integration with existing Lambda functions.
    
    Args:
        operation_name: Name of the operation being monitored
        include_business_metrics: Track business-specific metrics
        include_anomaly_detection: Enable anomaly detection for trust calculations
        include_performance_tracking: Enable performance regression monitoring
    
    Usage:
        @production_monitor("trust_score_calculation", include_anomaly_detection=True)
        def lambda_handler(event, context):
            # Your Lambda function logic
            return response
    """
    def decorator(func: Callable) -> Callable:
        # Apply production APM decorator
        wrapped_func = production_apm_decorator(
            operation_name,
            include_tracing=True,
            include_anomaly_detection=include_anomaly_detection
        )(func)
        
        # Apply performance monitoring for API endpoints
        if "api" in operation_name.lower():
            endpoint = f"/{operation_name.lower().replace('_', '/')}"
            method = "GET"  # Default, can be overridden
            wrapped_func = monitor_api_performance(
                endpoint, 
                method, 
                check_regression=include_performance_tracking
            )(wrapped_func)
        
        # Apply trust calculation tracing
        if "trust" in operation_name.lower():
            wrapped_func = trace_trust_calculation(operation_name)(wrapped_func)
        
        # Add business metrics collection
        if include_business_metrics:
            @functools.wraps(wrapped_func)
            def business_metrics_wrapper(*args, **kwargs):
                try:
                    result = wrapped_func(*args, **kwargs)
                    
                    # Extract business context from Lambda event
                    if args and isinstance(args[0], dict):
                        event = args[0]
                        
                        # Track API requests
                        if event.get("httpMethod"):
                            collector = get_production_metrics_collector()
                            collector.cloudwatch.put_metric_data(
                                Namespace=collector.namespace,
                                MetricData=[{
                                    "MetricName": "BusinessOperation",
                                    "Value": 1,
                                    "Unit": "Count",
                                    "Dimensions": [
                                        {"Name": "OperationType", "Value": operation_name},
                                        {"Name": "HttpMethod", "Value": event.get("httpMethod", "UNKNOWN")}
                                    ]
                                }]
                            )
                    
                    return result
                
                except Exception as e:
                    # Track business operation failures
                    try:
                        collector = get_production_metrics_collector()
                        collector.cloudwatch.put_metric_data(
                            Namespace=f"{collector.namespace}/Errors",
                            MetricData=[{
                                "MetricName": "BusinessOperationFailure",
                                "Value": 1,
                                "Unit": "Count",
                                "Dimensions": [
                                    {"Name": "OperationType", "Value": operation_name},
                                    {"Name": "ErrorType", "Value": type(e).__name__}
                                ]
                            }]
                        )
                    except:
                        pass  # Don't fail original operation
                    raise
            
            wrapped_func = business_metrics_wrapper
        
        return wrapped_func
    
    return decorator


# Convenience decorators for specific operations
def monitor_trust_api(endpoint: str, method: str = "GET"):
    """Monitor trust-related API endpoints."""
    return production_monitor(
        f"trust_api_{endpoint.replace('/', '_')}_{method.lower()}",
        include_business_metrics=True,
        include_anomaly_detection=True,
        include_performance_tracking=True
    )


def monitor_vtoken_operation(operation: str = "validation"):
    """Monitor V-Token operations."""
    return production_monitor(
        f"vtoken_{operation}",
        include_business_metrics=True,
        include_anomaly_detection=False,
        include_performance_tracking=True
    )


def monitor_agent_operation(operation: str = "registration"):
    """Monitor agent-related operations."""
    return production_monitor(
        f"agent_{operation}",
        include_business_metrics=True,
        include_anomaly_detection=False,
        include_performance_tracking=True
    )


# Middleware for API Gateway Lambda integration
class ProductionMonitoringMiddleware:
    """
    Middleware for automatic monitoring of Lambda functions invoked via API Gateway.
    """
    
    @staticmethod
    def lambda_middleware(handler: Callable) -> Callable:
        """
        Automatically apply monitoring to Lambda handlers based on API Gateway events.
        
        Usage:
            from monitoring.integration import ProductionMonitoringMiddleware
            
            @ProductionMonitoringMiddleware.lambda_middleware
            def lambda_handler(event, context):
                # Your Lambda function logic
                return response
        """
        @functools.wraps(handler)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Determine operation name from API Gateway event
            operation_name = "lambda_function"
            
            if event.get("httpMethod") and event.get("resource"):
                method = event["httpMethod"].lower()
                resource = event["resource"].replace("/", "_").replace("{", "").replace("}", "")
                operation_name = f"api_{method}_{resource}"
            
            # Apply production monitoring
            monitored_handler = production_monitor(
                operation_name,
                include_business_metrics=True,
                include_anomaly_detection="trust" in operation_name,
                include_performance_tracking=True
            )(handler)
            
            return monitored_handler(event, context)
        
        return wrapper


# Health check utilities
class MonitoringHealthCheck:
    """Health check utilities for monitoring infrastructure."""
    
    @staticmethod
    def verify_monitoring_setup() -> Dict[str, Any]:
        """Verify that production monitoring is properly configured."""
        try:
            collector = get_production_metrics_collector()
            
            # Test CloudWatch connection
            cloudwatch_healthy = True
            try:
                collector.cloudwatch.list_metrics(Namespace=collector.namespace, MaxRecords=1)
            except Exception:
                cloudwatch_healthy = False
            
            # Test DynamoDB connection
            dynamodb_healthy = True
            try:
                collector.table.scan(Limit=1)
            except Exception:
                dynamodb_healthy = False
            
            return {
                "monitoring_healthy": cloudwatch_healthy and dynamodb_healthy,
                "cloudwatch_connection": cloudwatch_healthy,
                "dynamodb_connection": dynamodb_healthy,
                "namespace": collector.namespace,
                "table_name": collector.table_name
            }
        
        except Exception as e:
            return {
                "monitoring_healthy": False,
                "error": str(e)
            }
    
    @staticmethod
    def test_monitoring_pipeline() -> Dict[str, Any]:
        """Test the monitoring pipeline with synthetic data."""
        try:
            collector = get_production_metrics_collector()
            
            # Send test metric
            test_metric_name = "MonitoringHealthCheck"
            collector.cloudwatch.put_metric_data(
                Namespace=collector.namespace,
                MetricData=[{
                    "MetricName": test_metric_name,
                    "Value": 1,
                    "Unit": "Count"
                }]
            )
            
            return {
                "test_successful": True,
                "test_metric_sent": test_metric_name,
                "namespace": collector.namespace
            }
        
        except Exception as e:
            return {
                "test_successful": False,
                "error": str(e)
            }


# Enhanced monitoring for specific AgentPier operations
def enhanced_trust_monitoring(func: Callable) -> Callable:
    """
    Enhanced monitoring specifically for trust score calculations.
    Includes business logic validation and anomaly detection.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import time
        from datetime import datetime, timezone
        
        start_time = time.time()
        collector = get_production_metrics_collector()
        
        try:
            result = func(*args, **kwargs)
            
            # Validate business logic
            if isinstance(result, (int, float)) and 0 <= result <= 100:
                # Valid trust score
                collector.cloudwatch.put_metric_data(
                    Namespace=collector.namespace,
                    MetricData=[{
                        "MetricName": "ValidTrustScoreCalculation",
                        "Value": 1,
                        "Unit": "Count"
                    }]
                )
            else:
                # Invalid trust score
                collector.cloudwatch.put_metric_data(
                    Namespace=f"{collector.namespace}/Anomalies",
                    MetricData=[{
                        "MetricName": "InvalidTrustScore",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [{"Name": "ScoreValue", "Value": str(result)}]
                    }]
                )
            
            # Track calculation performance
            calculation_time = (time.time() - start_time) * 1000
            collector.cloudwatch.put_metric_data(
                Namespace=collector.namespace,
                MetricData=[{
                    "MetricName": "TrustCalculationLatency",
                    "Value": calculation_time,
                    "Unit": "Milliseconds"
                }]
            )
            
            return result
        
        except Exception as e:
            # Track calculation errors
            collector.cloudwatch.put_metric_data(
                Namespace=f"{collector.namespace}/Errors",
                MetricData=[{
                    "MetricName": "TrustCalculationError",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "ErrorType", "Value": type(e).__name__}]
                }]
            )
            raise
    
    return wrapper


# Export key components
__all__ = [
    "production_monitor",
    "monitor_trust_api", 
    "monitor_vtoken_operation",
    "monitor_agent_operation",
    "ProductionMonitoringMiddleware",
    "MonitoringHealthCheck",
    "enhanced_trust_monitoring"
]