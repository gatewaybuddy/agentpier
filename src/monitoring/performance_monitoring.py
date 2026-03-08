"""
AgentPier Performance Monitoring Enhancement

Advanced performance monitoring with regression testing, distributed tracing,
benchmarking, and automated alerting for API performance degradation.
"""

import time
import json
import boto3
import uuid
import statistics
import functools
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# Import existing monitoring utilities
from monitoring.decorator import get_metrics_collector, track_operation


@dataclass
class PerformanceBaseline:
    """Performance baseline data structure."""
    endpoint: str
    method: str
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    success_rate: float
    throughput_rps: float
    timestamp: str
    sample_size: int


@dataclass
class TraceSegment:
    """Distributed trace segment."""
    trace_id: str
    segment_id: str
    parent_id: Optional[str]
    operation: str
    start_time: float
    end_time: Optional[float]
    duration_ms: Optional[float]
    success: bool
    metadata: Dict[str, Any]


class DistributedTracer:
    """
    Lightweight distributed tracing for trust calculations and API flows.
    """
    
    def __init__(self):
        self._current_trace = None
        self._segments = {}
    
    def start_trace(self, operation: str) -> str:
        """Start a new distributed trace."""
        trace_id = str(uuid.uuid4())
        self._current_trace = trace_id
        self._segments[trace_id] = []
        
        root_segment = TraceSegment(
            trace_id=trace_id,
            segment_id=str(uuid.uuid4()),
            parent_id=None,
            operation=operation,
            start_time=time.time(),
            end_time=None,
            duration_ms=None,
            success=True,
            metadata={"type": "root", "operation": operation}
        )
        
        self._segments[trace_id].append(root_segment)
        return trace_id
    
    @contextmanager
    def trace_segment(self, operation: str, metadata: Optional[Dict] = None):
        """Context manager for tracing a segment within a trace."""
        if not self._current_trace:
            yield None
            return
        
        segment_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Find parent segment (most recent active segment)
        segments = self._segments.get(self._current_trace, [])
        parent_id = segments[-1].segment_id if segments else None
        
        segment = TraceSegment(
            trace_id=self._current_trace,
            segment_id=segment_id,
            parent_id=parent_id,
            operation=operation,
            start_time=start_time,
            end_time=None,
            duration_ms=None,
            success=True,
            metadata=metadata or {}
        )
        
        try:
            yield segment
            
            # Mark as successful
            segment.end_time = time.time()
            segment.duration_ms = (segment.end_time - segment.start_time) * 1000
            segment.success = True
            
        except Exception as e:
            segment.end_time = time.time()
            segment.duration_ms = (segment.end_time - segment.start_time) * 1000
            segment.success = False
            segment.metadata.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise
        
        finally:
            self._segments[self._current_trace].append(segment)
    
    def get_trace_data(self, trace_id: str) -> List[TraceSegment]:
        """Get all segments for a trace."""
        return self._segments.get(trace_id, [])
    
    def send_trace_to_cloudwatch(self, trace_id: str):
        """Send trace data to CloudWatch as custom metrics."""
        try:
            segments = self._segments.get(trace_id, [])
            if not segments:
                return
            
            metrics_collector = get_metrics_collector()
            
            # Calculate trace metrics
            total_duration = max(s.duration_ms or 0 for s in segments if s.duration_ms)
            segment_count = len(segments)
            error_count = sum(1 for s in segments if not s.success)
            
            # Send trace-level metrics
            metrics_collector.send_metric(
                "trace_total_duration",
                total_duration,
                "Milliseconds",
                dimensions={"TraceOperation": segments[0].operation}
            )
            
            metrics_collector.send_metric(
                "trace_segment_count",
                segment_count,
                "Count",
                dimensions={"TraceOperation": segments[0].operation}
            )
            
            metrics_collector.send_metric(
                "trace_error_count",
                error_count,
                "Count",
                dimensions={"TraceOperation": segments[0].operation}
            )
            
            # Send individual segment metrics
            for segment in segments:
                if segment.duration_ms:
                    metrics_collector.send_metric(
                        f"segment_duration_{segment.operation}",
                        segment.duration_ms,
                        "Milliseconds"
                    )
        
        except Exception as e:
            print(f"Failed to send trace data to CloudWatch: {str(e)}")
    
    def finish_trace(self, trace_id: Optional[str] = None):
        """Finish a trace and send to CloudWatch."""
        if trace_id is None:
            trace_id = self._current_trace
        
        if trace_id:
            self.send_trace_to_cloudwatch(trace_id)
            self._current_trace = None


# Global tracer instance
_tracer = DistributedTracer()


def get_tracer() -> DistributedTracer:
    """Get the global distributed tracer."""
    return _tracer


class PerformanceBenchmark:
    """
    Performance benchmarking for API endpoints and trust calculations.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = os.environ.get("TABLE_NAME", "agentpier-dev")
        self.table = self.dynamodb.Table(self.table_name)
    
    def store_baseline(self, baseline: PerformanceBaseline):
        """Store performance baseline in DynamoDB."""
        try:
            self.table.put_item(
                Item={
                    "PK": f"PERF_BASELINE#{baseline.endpoint}",
                    "SK": f"{baseline.method}#{baseline.timestamp}",
                    **asdict(baseline),
                    "ttl": int(time.time()) + (90 * 24 * 60 * 60)  # 90 day TTL
                }
            )
        except Exception as e:
            print(f"Failed to store performance baseline: {str(e)}")
    
    def get_latest_baseline(self, endpoint: str, method: str) -> Optional[PerformanceBaseline]:
        """Get the most recent baseline for an endpoint."""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": f"PERF_BASELINE#{endpoint}"},
                ScanIndexForward=False,  # Get most recent first
                Limit=1
            )
            
            items = response.get("Items", [])
            if items:
                item = items[0]
                return PerformanceBaseline(**{k: v for k, v in item.items() if k not in ["PK", "SK", "ttl"]})
            
            return None
        except Exception as e:
            print(f"Failed to get performance baseline: {str(e)}")
            return None
    
    def collect_performance_samples(self, endpoint: str, method: str, hours: int = 1) -> List[Dict]:
        """Collect recent performance samples for analysis."""
        try:
            # Get recent API logs
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND #ts >= :cutoff AND #path = :endpoint AND #method = :method",
                ExpressionAttributeNames={
                    "#ts": "timestamp",
                    "#path": "path", 
                    "#method": "method"
                },
                ExpressionAttributeValues={
                    ":pk_prefix": "API_LOG#",
                    ":cutoff": cutoff_time,
                    ":endpoint": endpoint,
                    ":method": method
                },
                ProjectionExpression="response_time_ms, status_code, timestamp"
            )
            
            return response.get("Items", [])
        
        except Exception as e:
            print(f"Failed to collect performance samples: {str(e)}")
            return []
    
    def calculate_baseline(self, endpoint: str, method: str, hours: int = 24) -> Optional[PerformanceBaseline]:
        """Calculate performance baseline from recent data."""
        samples = self.collect_performance_samples(endpoint, method, hours)
        
        if len(samples) < 10:  # Need minimum samples for reliable baseline
            return None
        
        # Extract response times and success indicators
        response_times = []
        success_count = 0
        
        for sample in samples:
            response_times.append(float(sample.get("response_time_ms", 0)))
            if 200 <= sample.get("status_code", 500) < 400:
                success_count += 1
        
        if not response_times:
            return None
        
        # Calculate statistics
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
        success_rate = (success_count / len(samples)) * 100
        throughput_rps = len(samples) / (hours * 3600)  # requests per second
        
        baseline = PerformanceBaseline(
            endpoint=endpoint,
            method=method,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            success_rate=success_rate,
            throughput_rps=throughput_rps,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sample_size=len(samples)
        )
        
        # Store the baseline
        self.store_baseline(baseline)
        return baseline
    
    def check_performance_regression(self, endpoint: str, method: str) -> Dict[str, Any]:
        """Check for performance regression compared to baseline."""
        current_samples = self.collect_performance_samples(endpoint, method, hours=1)
        baseline = self.get_latest_baseline(endpoint, method)
        
        if not baseline or len(current_samples) < 5:
            return {"status": "insufficient_data", "samples": len(current_samples)}
        
        # Calculate current performance
        current_response_times = [float(s.get("response_time_ms", 0)) for s in current_samples]
        current_avg = statistics.mean(current_response_times)
        
        # Check for regression (>20% degradation)
        degradation_percent = ((current_avg - baseline.avg_response_time_ms) / baseline.avg_response_time_ms) * 100
        
        regression_detected = degradation_percent > 20.0
        
        result = {
            "status": "regression_detected" if regression_detected else "performance_ok",
            "endpoint": endpoint,
            "method": method,
            "baseline_avg_ms": baseline.avg_response_time_ms,
            "current_avg_ms": current_avg,
            "degradation_percent": degradation_percent,
            "threshold_percent": 20.0,
            "sample_size": len(current_samples),
            "baseline_timestamp": baseline.timestamp
        }
        
        # Send alert metric if regression detected
        if regression_detected:
            metrics_collector = get_metrics_collector()
            metrics_collector.send_metric(
                "performance_regression_alert",
                1,
                "Count",
                dimensions={
                    "Endpoint": endpoint,
                    "Method": method,
                    "DegradationPercent": str(int(degradation_percent))
                }
            )
        
        return result


# Global performance benchmark instance
_performance_benchmark = None


def get_performance_benchmark() -> PerformanceBenchmark:
    """Get the global performance benchmark instance."""
    global _performance_benchmark
    if _performance_benchmark is None:
        _performance_benchmark = PerformanceBenchmark()
    return _performance_benchmark


def trace_trust_calculation(operation: str = "trust_calculation"):
    """
    Decorator to add distributed tracing to trust calculation functions.
    
    Usage:
        @trace_trust_calculation("ace_score_calculation")
        def calculate_ace_score(events):
            # Your scoring logic
            return score
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            # Start trace if not already started
            if not tracer._current_trace:
                trace_id = tracer.start_trace(operation)
            
            with tracer.trace_segment(func.__name__, {"function": func.__name__}):
                result = func(*args, **kwargs)
            
            return result
        
        return wrapper
    return decorator


def monitor_api_performance(endpoint: str, method: str, check_regression: bool = True):
    """
    Decorator to monitor API endpoint performance and check for regressions.
    
    Usage:
        @monitor_api_performance("/trust/{agent_id}", "GET")
        def get_trust_score_handler(event, context):
            # Your API logic
            return response
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Track successful request
                response_time_ms = (time.time() - start_time) * 1000
                
                # Check for regression if enabled
                if check_regression:
                    benchmark = get_performance_benchmark()
                    regression_result = benchmark.check_performance_regression(endpoint, method)
                    
                    if regression_result.get("status") == "regression_detected":
                        print(f"Performance regression detected for {method} {endpoint}: {regression_result}")
                
                return result
                
            except Exception as e:
                # Track failed request
                response_time_ms = (time.time() - start_time) * 1000
                raise
        
        return wrapper
    return decorator


# Import os for environment variables
import os