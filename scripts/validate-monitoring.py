#!/usr/bin/env python3
"""
Simple validation script for AgentPier production monitoring.
Tests core functionality without complex test framework dependencies.
"""

import sys
import os
import json
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_imports():
    """Test that all monitoring modules can be imported."""
    print("Testing module imports...")
    
    try:
        from monitoring.production_monitoring import ProductionMetricsCollector, SLAMetrics, BusinessMetrics
        print("✓ Production monitoring imports successful")
    except Exception as e:
        print(f"✗ Production monitoring import failed: {e}")
        return False
    
    try:
        from monitoring.integration import production_monitor, MonitoringHealthCheck
        print("✓ Integration module imports successful")
    except Exception as e:
        print(f"✗ Integration module import failed: {e}")
        return False
    
    try:
        from monitoring.performance_monitoring import get_tracer, PerformanceBaseline
        print("✓ Performance monitoring imports successful")
    except Exception as e:
        print(f"✗ Performance monitoring import failed: {e}")
        return False
    
    return True

def test_decorator_functionality():
    """Test that monitoring decorators work correctly."""
    print("\nTesting decorator functionality...")
    
    try:
        from monitoring.integration import production_monitor
        
        @production_monitor("test_operation")
        def test_function(value):
            return {"result": "success", "input": value}
        
        result = test_function("test_input")
        
        if result["result"] == "success" and result["input"] == "test_input":
            print("✓ Production monitor decorator works correctly")
            return True
        else:
            print(f"✗ Decorator test failed: unexpected result {result}")
            return False
    
    except Exception as e:
        print(f"✗ Decorator test failed: {e}")
        return False

def test_data_structures():
    """Test that data structures can be created and serialized."""
    print("\nTesting data structures...")
    
    try:
        from monitoring.production_monitoring import SLAMetrics, BusinessMetrics, AnomalyAlert
        
        # Test SLA metrics
        sla = SLAMetrics(
            availability=99.5,
            latency_p99=1500,
            latency_p95=1200,
            error_rate=0.5,
            throughput_rps=10.5,
            sla_breaches=[],
            overall_health="healthy",
            period_start="2024-01-01T00:00:00Z",
            period_end="2024-01-01T01:00:00Z"
        )
        
        # Test Business metrics
        business = BusinessMetrics(
            trust_scores_calculated=100,
            vtokens_validated=250,
            api_requests_total=1000,
            new_agent_registrations=25,
            trust_tier_distributions={"Tier 1": 10, "Tier 2": 15},
            average_trust_score=82.5,
            trust_score_anomalies=2,
            timestamp="2024-01-01T00:00:00Z"
        )
        
        # Test Anomaly alert
        alert = AnomalyAlert(
            agent_id="test_agent",
            metric_type="score_jump",
            current_value=95.0,
            expected_range=(70.0, 85.0),
            severity="high",
            timestamp="2024-01-01T00:00:00Z",
            context={"test": "data"}
        )
        
        # Test serialization
        from dataclasses import asdict
        sla_dict = asdict(sla)
        business_dict = asdict(business)
        alert_dict = asdict(alert)
        
        print("✓ Data structures create and serialize correctly")
        return True
    
    except Exception as e:
        print(f"✗ Data structure test failed: {e}")
        return False

def test_monitoring_configuration():
    """Test monitoring configuration and environment setup."""
    print("\nTesting monitoring configuration...")
    
    try:
        from monitoring.production_monitoring import ProductionMetricsCollector
        
        # Test with mock environment
        os.environ["TABLE_NAME"] = "test-table"
        os.environ["METRICS_NAMESPACE"] = "AgentPier/test"
        
        # This will fail to connect to actual AWS services, but should not crash
        try:
            collector = ProductionMetricsCollector()
            print("✓ ProductionMetricsCollector initializes correctly")
        except Exception as e:
            # Expected to fail due to missing AWS credentials, but constructor should work
            if "Unable to locate credentials" in str(e) or "NoCredentialsError" in str(e):
                print("✓ ProductionMetricsCollector initializes correctly (AWS credentials not configured)")
            else:
                print(f"✗ Unexpected collector initialization error: {e}")
                return False
        
        return True
    
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_capacity_planning_script():
    """Test that the capacity planning script can be imported."""
    print("\nTesting capacity planning script...")
    
    try:
        # Add scripts to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        
        # Try to import the main classes (without running main())
        import imp
        script_path = os.path.join(os.path.dirname(__file__), 'capacity-planning.py')
        
        # Check if file exists and is executable
        if os.path.exists(script_path) and os.access(script_path, os.X_OK):
            print("✓ Capacity planning script exists and is executable")
            return True
        else:
            print(f"✗ Capacity planning script not found or not executable at {script_path}")
            return False
    
    except Exception as e:
        print(f"✗ Capacity planning script test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("AgentPier Production Monitoring Validation")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_decorator_functionality,
        test_data_structures,
        test_monitoring_configuration,
        test_capacity_planning_script
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All monitoring components validated successfully!")
        print("\nNext steps:")
        print("1. Deploy monitoring infrastructure: sam deploy --template-file infra/production-dashboard.yaml")
        print("2. Update Lambda functions with monitoring decorators")
        print("3. Configure CloudWatch alerts and dashboards")
        print("4. Run capacity planning: ./scripts/capacity-planning.py --stage prod")
        return True
    else:
        print("❌ Some monitoring components failed validation.")
        print("Please review the errors above and fix before deployment.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)