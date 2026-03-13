#!/usr/bin/env python3
"""
AgentPier Lambda Cold Start Monitoring Script

Monitors and reports on Lambda cold start metrics post-optimization.
"""

import boto3
import json
from datetime import datetime, timedelta
from pathlib import Path

def get_function_metrics(function_name, region='us-east-1'):
    """Get CloudWatch metrics for a Lambda function."""
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    
    # Get metrics for the last 24 hours
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    try:
        # Get duration metrics
        duration_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Duration',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 hour periods
            Statistics=['Average', 'Maximum', 'Minimum']
        )
        
        # Get invocation count
        invocation_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Invocations',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum']
        )
        
        # Get error count
        error_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Errors',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum']
        )
        
        return {
            'duration': duration_response.get('Datapoints', []),
            'invocations': invocation_response.get('Datapoints', []),
            'errors': error_response.get('Datapoints', [])
        }
    except Exception as e:
        return {'error': str(e)}

def monitor_optimized_functions():
    """Monitor the performance of optimized Lambda functions."""
    
    # Functions we optimized
    optimized_functions = {
        'Tier 1 (512MB)': [
            'agentpier-search-listings-dev',
            'agentpier-get-listing-dev', 
            'agentpier-trust-query-dev',
            'agentpier-get-me-dev',
            'agentpier-verify-badge-dev'
        ],
        'Tier 2 (384MB)': [
            'agentpier-create-listing-dev',
            'agentpier-trust-register-dev',
            'agentpier-get-marketplace-score-dev', 
            'agentpier-create-transaction-dev'
        ]
    }
    
    print("🔍 AgentPier Lambda Cold Start Monitoring")
    print("=" * 60)
    print(f"Monitoring period: Last 24 hours")
    print(f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    
    monitoring_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'functions': {}
    }
    
    for tier, functions in optimized_functions.items():
        print(f"\n📊 {tier} Functions:")
        print("-" * 40)
        
        for function_name in functions:
            print(f"\n🔧 {function_name}")
            
            metrics = get_function_metrics(function_name)
            
            if 'error' in metrics:
                print(f"   ❌ Error retrieving metrics: {metrics['error']}")
                monitoring_data['functions'][function_name] = {'error': metrics['error']}
                continue
            
            # Process duration metrics
            durations = metrics.get('duration', [])
            if durations:
                avg_duration = sum(d['Average'] for d in durations) / len(durations)
                max_duration = max(d['Maximum'] for d in durations)
                min_duration = min(d['Minimum'] for d in durations)
                
                print(f"   ⏱️  Duration: Avg {avg_duration:.0f}ms, Max {max_duration:.0f}ms, Min {min_duration:.0f}ms")
                
                # Cold start detection (durations > 1000ms likely cold starts)
                cold_starts = sum(1 for d in durations if d['Maximum'] > 1000)
                print(f"   🥶 Potential cold starts: {cold_starts}/{len(durations)} periods")
            else:
                print(f"   📊 No duration data available")
                avg_duration = max_duration = min_duration = None
            
            # Process invocation metrics
            invocations = metrics.get('invocations', [])
            total_invocations = sum(i['Sum'] for i in invocations) if invocations else 0
            print(f"   📈 Total invocations: {total_invocations}")
            
            # Process error metrics
            errors = metrics.get('errors', [])
            total_errors = sum(e['Sum'] for e in errors) if errors else 0
            error_rate = (total_errors / total_invocations * 100) if total_invocations > 0 else 0
            print(f"   ❗ Errors: {total_errors} ({error_rate:.2f}%)")
            
            # Store monitoring data
            monitoring_data['functions'][function_name] = {
                'avg_duration_ms': avg_duration,
                'max_duration_ms': max_duration, 
                'min_duration_ms': min_duration,
                'total_invocations': total_invocations,
                'total_errors': total_errors,
                'error_rate_pct': error_rate
            }
    
    # Save monitoring data
    monitoring_file = Path("data/lambda-monitoring.json")
    monitoring_file.parent.mkdir(exist_ok=True)
    
    with open(monitoring_file, 'w') as f:
        json.dump(monitoring_data, f, indent=2)
    
    print(f"\n💾 Monitoring data saved to {monitoring_file}")
    
    # Generate summary
    print(f"\n📋 Optimization Summary:")
    print("-" * 30)
    
    functioning_functions = [f for f, data in monitoring_data['functions'].items() if 'error' not in data]
    total_invocations = sum(data.get('total_invocations', 0) for data in monitoring_data['functions'].values() if 'error' not in data)
    total_errors = sum(data.get('total_errors', 0) for data in monitoring_data['functions'].values() if 'error' not in data)
    
    print(f"   ✅ Functions monitored: {len(functioning_functions)}")
    print(f"   📊 Total invocations: {total_invocations}")
    print(f"   ❗ Total errors: {total_errors}")
    
    if total_invocations > 0:
        overall_error_rate = total_errors / total_invocations * 100
        print(f"   📈 Overall error rate: {overall_error_rate:.2f}%")
        
        if overall_error_rate < 1.0:
            print(f"   ✅ Error rate within acceptable limits (<1%)")
        else:
            print(f"   ⚠️  Error rate elevated - investigate cold start issues")
    
    print(f"\n🔄 Run this script again after deployment to compare metrics")
    print(f"📈 Expected improvements: 50-80% reduction in P95 response times")

if __name__ == "__main__":
    monitor_optimized_functions()