"""
Enhanced Trust Score Handler with Performance Monitoring

Example integration of the new performance monitoring capabilities
with existing trust score calculation handlers.
"""

import json
import time
import uuid
import os
from datetime import datetime, timezone

from monitoring.performance_monitoring import (
    monitor_api_performance,
    trace_trust_calculation, 
    get_tracer,
    get_performance_benchmark
)
from monitoring.decorator import get_metrics_collector, track_operation
from utils.ace_scoring import calculate_ace_score, calculate_clearinghouse_score
from utils.response import success, error, not_found
import boto3


def _get_table():
    """Get DynamoDB table reference."""
    TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


@trace_trust_calculation("ace_score_calculation")
def enhanced_calculate_ace_score(events, agent_id=None):
    """
    Enhanced ACE score calculation with distributed tracing.
    """
    tracer = get_tracer()
    
    # Trace data preprocessing
    with tracer.trace_segment("data_preprocessing", {"events_count": len(events)}):
        # Filter and validate events
        valid_events = [e for e in events if e.get("event_type") and e.get("timestamp")]
        
        if len(valid_events) != len(events):
            metrics_collector = get_metrics_collector()
            metrics_collector.send_metric(
                "ace_score_invalid_events",
                len(events) - len(valid_events),
                "Count",
                dimensions={"AgentId": agent_id} if agent_id else None
            )
    
    # Trace actual score calculation
    with tracer.trace_segment("ace_computation", {"valid_events": len(valid_events)}):
        score = calculate_ace_score(valid_events)
    
    # Trace score validation
    with tracer.trace_segment("score_validation"):
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            raise ValueError(f"Invalid ACE score: {score}")
        
        # Determine score tier
        if score >= 80:
            tier = "highly_trusted"
        elif score >= 60:
            tier = "trusted"
        elif score >= 40:
            tier = "moderately_trusted"
        elif score >= 20:
            tier = "marginally_trusted"
        else:
            tier = "untrusted"
    
    return {
        "score": score,
        "tier": tier,
        "valid_events": len(valid_events),
        "total_events": len(events)
    }


@trace_trust_calculation("clearinghouse_score_calculation")
def enhanced_calculate_clearinghouse_score(signals, agent_id=None):
    """
    Enhanced clearinghouse score calculation with distributed tracing.
    """
    tracer = get_tracer()
    
    with tracer.trace_segment("signal_aggregation", {"signal_count": len(signals)}):
        # Aggregate signals from multiple sources
        aggregated_signals = {}
        for signal in signals:
            source = signal.get("source", "unknown")
            if source not in aggregated_signals:
                aggregated_signals[source] = []
            aggregated_signals[source].append(signal)
    
    with tracer.trace_segment("clearinghouse_computation", {"sources": len(aggregated_signals)}):
        score = calculate_clearinghouse_score(signals)
    
    return {
        "score": score,
        "sources": list(aggregated_signals.keys()),
        "signal_count": len(signals)
    }


@monitor_api_performance("/trust/{agent_id}", "GET", check_regression=True)
def enhanced_get_trust_score(event, context):
    """
    Enhanced trust score retrieval with performance monitoring and tracing.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Start distributed trace
    tracer = get_tracer()
    trace_id = tracer.start_trace("trust_score_query")
    
    try:
        with tracer.trace_segment("request_validation"):
            # Extract and validate parameters
            path_params = event.get("pathParameters", {}) or {}
            agent_id = path_params.get("agent_id")
            
            if not agent_id:
                return error("agent_id is required", 400)
            
            # Optional query parameters
            query_params = event.get("queryStringParameters", {}) or {}
            include_details = query_params.get("details", "false").lower() == "true"
            force_recalculate = query_params.get("recalculate", "false").lower() == "true"
        
        with tracer.trace_segment("data_retrieval", {"agent_id": agent_id}):
            table = _get_table()
            
            # Get agent metadata
            agent_response = table.get_item(
                Key={"PK": f"AGENT#{agent_id}", "SK": "METADATA"}
            )
            
            agent_data = agent_response.get("Item")
            if not agent_data:
                return not_found(f"Agent {agent_id} not found")
            
            # Check if we need to recalculate or can use cached score
            last_calculated = agent_data.get("last_calculated")
            trust_score = agent_data.get("trust_score")
            
            should_recalculate = (
                force_recalculate or 
                not trust_score or 
                not last_calculated or
                _score_is_stale(last_calculated)
            )
        
        if should_recalculate:
            with tracer.trace_segment("events_retrieval"):
                # Get agent events for scoring
                events_response = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": f"AGENT#{agent_id}#EVENTS"}
                )
                events = events_response.get("Items", [])
            
            with tracer.trace_segment("trust_calculation"):
                # Calculate trust score with enhanced monitoring
                ace_result = enhanced_calculate_ace_score(events, agent_id)
                trust_score = ace_result["score"]
                score_tier = ace_result["tier"]
                
                # Update agent record with new score
                timestamp = datetime.now(timezone.utc).isoformat()
                table.update_item(
                    Key={"PK": f"AGENT#{agent_id}", "SK": "METADATA"},
                    UpdateExpression="SET trust_score = :score, trust_tier = :tier, last_calculated = :timestamp",
                    ExpressionAttributeValues={
                        ":score": trust_score,
                        ":tier": score_tier,
                        ":timestamp": timestamp
                    }
                )
            
            # Send calculation metrics
            metrics_collector = get_metrics_collector()
            metrics_collector.send_metric(
                "trust_score_recalculations",
                1,
                "Count",
                dimensions={
                    "AgentId": agent_id,
                    "Tier": score_tier,
                    "Forced": str(force_recalculate)
                }
            )
        else:
            trust_score = float(agent_data.get("trust_score", 0))
            score_tier = agent_data.get("trust_tier", "unknown")
        
        # Prepare response
        response_data = {
            "agent_id": agent_id,
            "trust_score": trust_score,
            "trust_tier": score_tier,
            "last_calculated": agent_data.get("last_calculated"),
            "request_id": request_id,
            "recalculated": should_recalculate
        }
        
        if include_details:
            response_data["calculation_details"] = {
                "events_processed": ace_result.get("valid_events") if should_recalculate else None,
                "total_events": ace_result.get("total_events") if should_recalculate else None,
                "trace_id": trace_id
            }
        
        # Track successful API request
        response_time_ms = (time.time() - start_time) * 1000
        _track_api_request(table, request_id, "GET", f"/trust/{agent_id}", 200, response_time_ms)
        
        return success(response_data)
    
    except Exception as e:
        # Track failed request  
        response_time_ms = (time.time() - start_time) * 1000
        _track_api_request(table, request_id, "GET", f"/trust/{agent_id}", 500, response_time_ms)
        
        return error(f"Trust score calculation failed: {str(e)}", 500)
    
    finally:
        tracer.finish_trace(trace_id)


@monitor_api_performance("/trust/batch", "POST", check_regression=True)
def enhanced_batch_trust_scores(event, context):
    """
    Enhanced batch trust score calculation with performance monitoring.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    tracer = get_tracer()
    trace_id = tracer.start_trace("batch_trust_calculation")
    
    try:
        with tracer.trace_segment("request_parsing"):
            # Parse request body
            body = event.get("body", "{}")
            if isinstance(body, str):
                body = json.loads(body)
            
            agent_ids = body.get("agent_ids", [])
            if not agent_ids:
                return error("agent_ids list is required", 400)
            
            if len(agent_ids) > 50:  # Reasonable batch limit
                return error("Maximum 50 agents per batch request", 400)
        
        results = []
        successful_calculations = 0
        failed_calculations = 0
        
        with tracer.trace_segment("batch_processing", {"batch_size": len(agent_ids)}):
            table = _get_table()
            
            for agent_id in agent_ids:
                try:
                    with tracer.trace_segment("single_agent_processing", {"agent_id": agent_id}):
                        # Get agent data
                        agent_response = table.get_item(
                            Key={"PK": f"AGENT#{agent_id}", "SK": "METADATA"}
                        )
                        
                        agent_data = agent_response.get("Item")
                        if not agent_data:
                            results.append({
                                "agent_id": agent_id,
                                "error": "Agent not found",
                                "trust_score": None
                            })
                            failed_calculations += 1
                            continue
                        
                        # Get events and calculate score
                        events_response = table.query(
                            KeyConditionExpression="PK = :pk",
                            ExpressionAttributeValues={":pk": f"AGENT#{agent_id}#EVENTS"}
                        )
                        events = events_response.get("Items", [])
                        
                        ace_result = enhanced_calculate_ace_score(events, agent_id)
                        
                        results.append({
                            "agent_id": agent_id,
                            "trust_score": ace_result["score"],
                            "trust_tier": ace_result["tier"],
                            "events_processed": ace_result["valid_events"]
                        })
                        successful_calculations += 1
                
                except Exception as e:
                    results.append({
                        "agent_id": agent_id,
                        "error": str(e),
                        "trust_score": None
                    })
                    failed_calculations += 1
        
        # Send batch calculation metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.send_metric(
            "batch_trust_calculations",
            1,
            "Count",
            dimensions={
                "BatchSize": str(len(agent_ids)),
                "SuccessRate": str(round((successful_calculations / len(agent_ids)) * 100))
            }
        )
        
        response_time_ms = (time.time() - start_time) * 1000
        _track_api_request(table, request_id, "POST", "/trust/batch", 200, response_time_ms)
        
        return success({
            "request_id": request_id,
            "total_requested": len(agent_ids),
            "successful_calculations": successful_calculations,
            "failed_calculations": failed_calculations,
            "results": results,
            "trace_id": trace_id
        })
    
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        _track_api_request(None, request_id, "POST", "/trust/batch", 500, response_time_ms)
        
        return error(f"Batch calculation failed: {str(e)}", 500)
    
    finally:
        tracer.finish_trace(trace_id)


def performance_dashboard_handler(event, context):
    """
    API endpoint to retrieve performance metrics for dashboard display.
    """
    try:
        # Get query parameters
        query_params = event.get("queryStringParameters", {}) or {}
        hours = int(query_params.get("hours", "24"))
        endpoint = query_params.get("endpoint", "all")
        
        benchmark = get_performance_benchmark()
        
        if endpoint == "all":
            # Get metrics for all monitored endpoints
            endpoints = [
                ("/trust/{agent_id}", "GET"),
                ("/trust/batch", "POST"),
                ("/vtokens/create", "POST"),
                ("/vtokens/verify", "POST"),
                ("/auth/challenge", "POST")
            ]
            
            dashboard_data = {}
            for ep, method in endpoints:
                baseline = benchmark.get_latest_baseline(ep, method)
                regression = benchmark.check_performance_regression(ep, method)
                
                dashboard_data[f"{method}_{ep.replace('{', '').replace('}', '').replace('/', '_')}"] = {
                    "baseline": baseline.__dict__ if baseline else None,
                    "regression_status": regression,
                    "samples": benchmark.collect_performance_samples(ep, method, hours)
                }
        else:
            # Get metrics for specific endpoint
            method = query_params.get("method", "GET")
            baseline = benchmark.get_latest_baseline(endpoint, method)
            regression = benchmark.check_performance_regression(endpoint, method)
            samples = benchmark.collect_performance_samples(endpoint, method, hours)
            
            dashboard_data = {
                "baseline": baseline.__dict__ if baseline else None,
                "regression_status": regression,
                "samples": samples
            }
        
        return success({
            "dashboard_data": dashboard_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hours_analyzed": hours
        })
    
    except Exception as e:
        return error(f"Failed to generate dashboard data: {str(e)}", 500)


def _score_is_stale(last_calculated_iso: str, max_age_hours: int = 24) -> bool:
    """Check if a trust score is stale and needs recalculation."""
    try:
        last_calc_time = datetime.fromisoformat(last_calculated_iso.replace('Z', '+00:00'))
        age_hours = (datetime.now(timezone.utc) - last_calc_time).total_seconds() / 3600
        return age_hours > max_age_hours
    except:
        return True  # If we can't parse the timestamp, consider it stale


def _track_api_request(table, request_id: str, method: str, path: str, status_code: int, response_time_ms: float):
    """Track API request for performance analysis."""
    try:
        if table:
            timestamp = datetime.now(timezone.utc).isoformat()
            table.put_item(
                Item={
                    "PK": f"API_LOG#{timestamp[:10]}",
                    "SK": f"{timestamp}#{request_id}",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "timestamp": timestamp,
                    "ttl": int(time.time()) + (7 * 24 * 60 * 60)
                }
            )
    except Exception as e:
        print(f"Failed to track API request: {str(e)}")