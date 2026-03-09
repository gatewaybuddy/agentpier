#!/usr/bin/env python3
"""
Test suite for AgentPier production monitoring system.
Validates monitoring infrastructure, decorators, and metrics collection.
"""

import pytest
import json
import time
import boto3
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from monitoring.production_monitoring import (
    ProductionMetricsCollector,
    SLAMetrics,
    BusinessMetrics,
    AnomalyAlert,
    production_apm_decorator
)
from monitoring.performance_monitoring import PerformanceBaseline
from monitoring.integration import (
    production_monitor,
    MonitoringHealthCheck,
    ProductionMonitoringMiddleware
)


class TestProductionMetricsCollector:
    """Test the production metrics collector."""
    
    @pytest.fixture
    def mock_collector(self):
        """Create a mock metrics collector."""
        with patch('boto3.resource'), patch('boto3.client'):
            collector = ProductionMetricsCollector()
            collector.table = Mock()
            collector.cloudwatch = Mock()
            return collector
    
    def test_collect_business_metrics_success(self, mock_collector):
        """Test successful business metrics collection."""
        # Mock DynamoDB responses
        mock_collector.table.scan.side_effect = [
            {"Items": [
                {"calculation_result": 85.0, "trust_tier": "Tier 3", "calculation_time": 250, "agent_id": "agent1"},
                {"calculation_result": 78.5, "trust_tier": "Tier 2", "calculation_time": 180, "agent_id": "agent2"}
            ]},
            {"Count": 45},  # V-token validations
            {"Count": 234}, # API requests
            {"Count": 12}   # New registrations
        ]
        
        metrics = mock_collector.collect_business_metrics(hours=1)
        
        assert isinstance(metrics, BusinessMetrics)
        assert metrics.trust_scores_calculated == 2
        assert metrics.vtokens_validated == 45
        assert metrics.api_requests_total == 234
        assert metrics.new_agent_registrations == 12
        assert metrics.average_trust_score == 81.75  # (85.0 + 78.5) / 2
        assert "Tier 2" in metrics.trust_tier_distributions
        assert "Tier 3" in metrics.trust_tier_distributions
        assert metrics.trust_score_anomalies == 0  # No calculation times > 5000ms
    
    def test_calculate_sla_metrics_success(self, mock_collector):
        """Test SLA metrics calculation."""
        # Mock API logs
        api_logs = [
            {"status_code": 200, "response_time_ms": 150, "timestamp": "2024-01-01T10:00:00Z"},
            {"status_code": 200, "response_time_ms": 220, "timestamp": "2024-01-01T10:01:00Z"},
            {"status_code": 404, "response_time_ms": 80, "timestamp": "2024-01-01T10:02:00Z"},
            {"status_code": 200, "response_time_ms": 300, "timestamp": "2024-01-01T10:03:00Z"},
            {"status_code": 500, "response_time_ms": 1200, "timestamp": "2024-01-01T10:04:00Z"}
        ]
        
        mock_collector.table.scan.return_value = {"Items": api_logs}
        
        sla_metrics = mock_collector.calculate_sla_metrics(hours=1)
        
        assert isinstance(sla_metrics, SLAMetrics)
        assert sla_metrics.availability == 60.0  # 3 success / 5 total
        assert sla_metrics.error_rate == 40.0    # 2 errors / 5 total
        assert sla_metrics.latency_p99 == 1200   # Highest response time
        assert sla_metrics.throughput > 0        # Calculated throughput
    
    def test_detect_trust_anomalies(self, mock_collector):
        """Test trust anomaly detection."""
        # Mock trust calculation history
        calculations = [
            {"calculation_result": 95.0, "calculation_time": 250},  # Recent - big jump
            {"calculation_result": 75.0, "calculation_time": 200},  # Historical
            {"calculation_result": 78.0, "calculation_time": 180},  # Historical
            {"calculation_result": 77.0, "calculation_time": 220}   # Historical
        ]
        
        mock_collector.table.query.return_value = {"Items": calculations}
        
        alerts = mock_collector.detect_trust_anomalies("agent123")
        
        assert len(alerts) > 0
        score_jump_alert = next((a for a in alerts if a.metric_type == "score_jump"), None)
        assert score_jump_alert is not None
        assert score_jump_alert.agent_id == "agent123"
        assert score_jump_alert.severity in ["high", "medium"]
    
    def test_send_business_metrics(self, mock_collector):
        """Test sending business metrics to CloudWatch."""
        metrics = BusinessMetrics(
            trust_scores_calculated=100,
            vtokens_validated=250,
            api_requests_total=1500,
            new_agent_registrations=25,
            trust_tier_distributions={"Tier 1": 10, "Tier 2": 15},
            average_trust_score=82.5,
            trust_score_anomalies=3,
            timestamp="2024-01-01T12:00:00Z"
        )
        
        mock_collector.send_business_metrics(metrics)
        
        # Verify CloudWatch calls were made
        assert mock_collector.cloudwatch.put_metric_data.called
        call_args = mock_collector.cloudwatch.put_metric_data.call_args_list
        
        # Check that metrics were sent
        metric_names = []
        for call in call_args:
            for metric in call[1]["MetricData"]:
                metric_names.append(metric["MetricName"])
        
        assert "TrustScoresCalculated" in metric_names
        assert "VTokensValidated" in metric_names
        assert "ApiRequestsTotal" in metric_names
        assert "AverageTrustScore" in metric_names


class TestProductionMonitoringDecorators:
    """Test monitoring decorators and integrations."""
    
    def test_production_apm_decorator_success(self):
        """Test APM decorator with successful function execution."""
        with patch('monitoring.production_monitoring.get_tracer') as mock_tracer, \
             patch('monitoring.production_monitoring.get_production_metrics_collector') as mock_collector:
            
            # Setup mocks
            mock_tracer_instance = Mock()
            mock_tracer_instance._current_trace = None
            mock_tracer.return_value = mock_tracer_instance
            
            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            
            @production_apm_decorator("test_operation")
            def test_function(agent_id, data):
                return {"result": "success", "agent_id": agent_id}
            
            result = test_function("agent123", {"test": "data"})
            
            assert result["result"] == "success"
            assert result["agent_id"] == "agent123"
    
    def test_production_monitor_decorator(self):
        """Test the main production monitor decorator."""
        with patch('monitoring.integration.production_apm_decorator') as mock_apm, \
             patch('monitoring.integration.get_production_metrics_collector') as mock_collector:
            
            # Setup decorator chain
            mock_apm.return_value = lambda x: x
            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            
            @production_monitor("api_test", include_business_metrics=True)
            def test_api_function(event, context):
                return {"statusCode": 200, "body": "success"}
            
            # Test with API Gateway event
            event = {
                "httpMethod": "GET",
                "resource": "/test/{id}",
                "pathParameters": {"id": "123"}
            }
            context = Mock()
            
            result = test_api_function(event, context)
            
            assert result["statusCode"] == 200
            assert result["body"] == "success"
    
    def test_lambda_middleware_automatic_detection(self):
        """Test automatic operation detection in Lambda middleware."""
        with patch('monitoring.integration.production_monitor') as mock_monitor:
            mock_monitor.return_value = lambda x: x
            
            @ProductionMonitoringMiddleware.lambda_middleware
            def lambda_handler(event, context):
                return {"statusCode": 200}
            
            # Test API Gateway event
            event = {
                "httpMethod": "POST",
                "resource": "/trust/{agent_id}",
                "pathParameters": {"agent_id": "agent123"}
            }
            context = Mock()
            
            result = lambda_handler(event, context)
            
            assert result["statusCode"] == 200
            
            # Verify monitor was called with correct operation name
            mock_monitor.assert_called_once()
            call_args = mock_monitor.call_args[0]
            assert "api_post_trust_agent_id" in call_args[0]


class TestMonitoringHealthCheck:
    """Test monitoring health check utilities."""
    
    def test_verify_monitoring_setup_healthy(self):
        """Test health check with healthy monitoring setup."""
        with patch('monitoring.integration.get_production_metrics_collector') as mock_getter:
            mock_collector = Mock()
            mock_collector.cloudwatch.list_metrics.return_value = {"Metrics": []}
            mock_collector.table.scan.return_value = {"Items": []}
            mock_collector.namespace = "AgentPier/test"
            mock_collector.table_name = "test-table"
            mock_getter.return_value = mock_collector
            
            result = MonitoringHealthCheck.verify_monitoring_setup()
            
            assert result["monitoring_healthy"] is True
            assert result["cloudwatch_connection"] is True
            assert result["dynamodb_connection"] is True
            assert result["namespace"] == "AgentPier/test"
            assert result["table_name"] == "test-table"
    
    def test_verify_monitoring_setup_unhealthy(self):
        """Test health check with unhealthy monitoring setup."""
        with patch('monitoring.integration.get_production_metrics_collector') as mock_getter:
            mock_collector = Mock()
            mock_collector.cloudwatch.list_metrics.side_effect = Exception("Connection failed")
            mock_collector.table.scan.side_effect = Exception("DynamoDB error")
            mock_getter.return_value = mock_collector
            
            result = MonitoringHealthCheck.verify_monitoring_setup()
            
            assert result["monitoring_healthy"] is False
            assert result["cloudwatch_connection"] is False
            assert result["dynamodb_connection"] is False
    
    def test_monitoring_pipeline_test(self):
        """Test monitoring pipeline with synthetic data."""
        with patch('monitoring.integration.get_production_metrics_collector') as mock_getter:
            mock_collector = Mock()
            mock_collector.cloudwatch.put_metric_data.return_value = {}
            mock_collector.namespace = "AgentPier/test"
            mock_getter.return_value = mock_collector
            
            result = MonitoringHealthCheck.test_monitoring_pipeline()
            
            assert result["test_successful"] is True
            assert result["test_metric_sent"] == "MonitoringHealthCheck"
            assert result["namespace"] == "AgentPier/test"
            
            # Verify metric was sent
            mock_collector.cloudwatch.put_metric_data.assert_called_once()


class TestBusinessLogicValidation:
    """Test business logic validation and anomaly detection."""
    
    def test_trust_score_validation(self):
        """Test trust score validation logic."""
        from monitoring.integration import enhanced_trust_monitoring
        
        with patch('monitoring.integration.get_production_metrics_collector') as mock_getter:
            mock_collector = Mock()
            mock_getter.return_value = mock_collector
            
            @enhanced_trust_monitoring
            def calculate_trust_score(agent_data):
                return 85.0  # Valid score
            
            result = calculate_trust_score({"agent_id": "test"})
            
            assert result == 85.0
            
            # Check that valid score metric was sent
            calls = mock_collector.cloudwatch.put_metric_data.call_args_list
            metric_names = []
            for call in calls:
                for metric in call[1]["MetricData"]:
                    metric_names.append(metric["MetricName"])
            
            assert "ValidTrustScoreCalculation" in metric_names
    
    def test_invalid_trust_score_detection(self):
        """Test detection of invalid trust scores."""
        from monitoring.integration import enhanced_trust_monitoring
        
        with patch('monitoring.integration.get_production_metrics_collector') as mock_getter:
            mock_collector = Mock()
            mock_getter.return_value = mock_collector
            
            @enhanced_trust_monitoring
            def calculate_invalid_trust_score(agent_data):
                return 150.0  # Invalid score (>100)
            
            result = calculate_invalid_trust_score({"agent_id": "test"})
            
            assert result == 150.0
            
            # Check that invalid score metric was sent
            calls = mock_collector.cloudwatch.put_metric_data.call_args_list
            metric_names = []
            namespaces = []
            for call in calls:
                namespaces.append(call[1]["Namespace"])
                for metric in call[1]["MetricData"]:
                    metric_names.append(metric["MetricName"])
            
            assert "InvalidTrustScore" in metric_names
            assert any("Anomalies" in ns for ns in namespaces)


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running AgentPier Production Monitoring Tests...")
    
    # Test health check
    try:
        from monitoring.integration import MonitoringHealthCheck
        health_result = MonitoringHealthCheck.verify_monitoring_setup()
        print(f"✓ Health check result: {health_result}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
    
    # Test decorator functionality
    try:
        from monitoring.integration import production_monitor
        
        @production_monitor("test_operation")
        def test_function():
            return "success"
        
        result = test_function()
        print(f"✓ Decorator test result: {result}")
    except Exception as e:
        print(f"✗ Decorator test failed: {e}")
    
    print("\nFor full test suite, run: pytest tests/test_production_monitoring.py -v")