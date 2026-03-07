"""
Trust Score Monitoring Integration

Example integration of monitoring decorators with trust scoring functions.
This shows how to add monitoring to existing trust score calculation functions.
"""

import os
import time
import uuid
from datetime import datetime, timezone

from monitoring.decorator import (
    monitor_lambda_function,
    monitor_trust_score_calculation,
    track_operation,
    track_api_request,
    get_metrics_collector
)

from utils.ace_scoring import calculate_ace_score, calculate_clearinghouse_score
from utils.response import success, error


# Enhanced trust score calculation with monitoring
@monitor_trust_score_calculation(include_accuracy=True, include_score_distribution=True)
def calculate_monitored_ace_score(events):
    """
    Monitored version of ACE score calculation.
    Tracks timing, accuracy, and score distribution.
    """
    return calculate_ace_score(events)


@monitor_trust_score_calculation(include_score_distribution=True)
def calculate_monitored_clearinghouse_score(all_signals):
    """
    Monitored version of clearinghouse score calculation.
    """
    return calculate_clearinghouse_score(all_signals)


# Enhanced trust API handlers with monitoring
@monitor_lambda_function("trust_score_query", include_duration=True)
def monitored_get_trust_score(event, context):
    """
    Enhanced trust score query handler with monitoring.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        # Extract path parameters
        path_params = event.get("pathParameters", {}) or {}
        agent_id = path_params.get("agent_id")
        
        if not agent_id:
            track_api_request(
                table=None,  # Would need table reference
                request_id=request_id,
                method="GET",
                path="/trust/{agent_id}",
                status_code=400,
                response_time_ms=(time.time() - start_time) * 1000
            )
            return error("agent_id is required", 400)
        
        # Track the operation
        with track_operation("trust_score_lookup", agent_type="agent"):
            table = _get_table()
            
            # Get agent data
            response = table.get_item(
                Key={"PK": f"AGENT#{agent_id}", "SK": "METADATA"}
            )
            
            agent_data = response.get("Item")
            if not agent_data:
                track_api_request(
                    table=table,
                    request_id=request_id,
                    method="GET",
                    path=f"/trust/{agent_id}",
                    status_code=404,
                    response_time_ms=(time.time() - start_time) * 1000
                )
                return not_found(f"Agent {agent_id} not found")
            
            # Get agent events for scoring
            events_response = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": f"AGENT#{agent_id}#EVENTS"}
            )
            
            events = events_response.get("Items", [])
            
            # Calculate trust score with monitoring
            trust_score = calculate_monitored_ace_score(events)
            
            # Send additional custom metrics
            metrics_collector = get_metrics_collector()
            metrics_collector.send_metric(
                "trust_score_queries",
                1,
                "Count",
                dimensions={"AgentType": "agent"}
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            track_api_request(
                table=table,
                request_id=request_id,
                method="GET",
                path=f"/trust/{agent_id}",
                status_code=200,
                response_time_ms=response_time_ms
            )
            
            result = {
                "agent_id": agent_id,
                "trust_score": trust_score,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id
            }
            
            return success(result)
    
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        track_api_request(
            table=None,
            request_id=request_id,
            method="GET",
            path=f"/trust/{agent_id}",
            status_code=500,
            response_time_ms=response_time_ms
        )
        
        return error(f"Internal server error: {str(e)}", 500)


@monitor_lambda_function("trust_score_registration", include_duration=True)
def monitored_register_agent(event, context):
    """
    Enhanced agent registration handler with monitoring.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)
        
        agent_id = body.get("agent_id")
        if not agent_id:
            track_api_request(
                table=None,
                request_id=request_id,
                method="POST",
                path="/trust/register",
                status_code=400,
                response_time_ms=(time.time() - start_time) * 1000
            )
            return error("agent_id is required", 400)
        
        with track_operation("agent_registration", agent_type="new"):
            table = _get_table()
            
            # Register agent (simplified example)
            timestamp = datetime.now(timezone.utc).isoformat()
            
            table.put_item(
                Item={
                    "PK": f"AGENT#{agent_id}",
                    "SK": "METADATA",
                    "agent_id": agent_id,
                    "agent_name": body.get("agent_name", agent_id),
                    "trust_score": 20.0,  # Starting score
                    "trust_tier": "Tier 1",
                    "created_at": timestamp,
                    "last_updated": timestamp
                }
            )
            
            # Send custom metrics
            metrics_collector = get_metrics_collector()
            metrics_collector.send_metric(
                "agent_registrations",
                1,
                "Count"
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            track_api_request(
                table=table,
                request_id=request_id,
                method="POST",
                path="/trust/register",
                status_code=201,
                response_time_ms=response_time_ms
            )
            
            return success({
                "agent_id": agent_id,
                "trust_score": 20.0,
                "status": "registered",
                "timestamp": timestamp
            })
    
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        track_api_request(
            table=None,
            request_id=request_id,
            method="POST",
            path="/trust/register",
            status_code=500,
            response_time_ms=response_time_ms
        )
        
        return error(f"Registration failed: {str(e)}", 500)


def _get_table():
    """Get DynamoDB table reference."""
    import boto3
    TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)