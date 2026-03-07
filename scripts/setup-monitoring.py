#!/usr/bin/env python3
"""
Setup AgentPier Monitoring Infrastructure

This script integrates the monitoring resources into the existing CloudFormation template
and deploys the monitoring infrastructure.
"""

import os
import sys
import yaml
import json
import subprocess
from pathlib import Path


def load_yaml_file(file_path: Path) -> dict:
    """Load YAML file and return parsed content."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def save_yaml_file(file_path: Path, content: dict):
    """Save content as YAML file."""
    with open(file_path, 'w') as f:
        yaml.safe_dump(content, f, indent=2, default_flow_style=False)


def merge_cloudformation_templates():
    """
    Merge monitoring resources into the main CloudFormation template.
    """
    project_root = Path(__file__).parent.parent
    template_file = project_root / "infra" / "template.yaml"
    monitoring_file = project_root / "infra" / "monitoring.yaml"
    backup_file = project_root / "infra" / "template.yaml.backup"
    
    print("🔄 Merging monitoring resources into CloudFormation template...")
    
    # Load existing template
    if not template_file.exists():
        print(f"❌ Template file not found: {template_file}")
        return False
    
    template = load_yaml_file(template_file)
    
    # Load monitoring resources
    if not monitoring_file.exists():
        print(f"❌ Monitoring file not found: {monitoring_file}")
        return False
    
    monitoring = load_yaml_file(monitoring_file)
    
    # Create backup
    print(f"📋 Creating backup: {backup_file}")
    save_yaml_file(backup_file, template)
    
    # Merge resources
    if 'Resources' not in template:
        template['Resources'] = {}
    
    monitoring_resources = monitoring.get('Resources', {})
    template['Resources'].update(monitoring_resources)
    
    # Merge outputs
    if 'Outputs' not in template:
        template['Outputs'] = {}
    
    monitoring_outputs = monitoring.get('Outputs', {})
    template['Outputs'].update(monitoring_outputs)
    
    # Save updated template
    save_yaml_file(template_file, template)
    
    print("✅ Successfully merged monitoring resources")
    return True


def create_monitoring_init_file():
    """
    Create __init__.py file for monitoring package.
    """
    project_root = Path(__file__).parent.parent
    monitoring_dir = project_root / "src" / "monitoring"
    init_file = monitoring_dir / "__init__.py"
    
    init_content = '''"""
AgentPier Monitoring Package

Provides monitoring and metrics collection for AgentPier infrastructure.
"""

from .decorator import (
    monitor_lambda_function,
    monitor_trust_score_calculation,
    track_operation,
    track_api_request,
    get_metrics_collector
)

from .metrics_collector import lambda_handler as metrics_collector

__all__ = [
    "monitor_lambda_function",
    "monitor_trust_score_calculation", 
    "track_operation",
    "track_api_request",
    "get_metrics_collector",
    "metrics_collector"
]
'''
    
    with open(init_file, 'w') as f:
        f.write(init_content)
    
    print("✅ Created monitoring package __init__.py")


def validate_monitoring_setup():
    """
    Validate that all monitoring files are in place.
    """
    project_root = Path(__file__).parent.parent
    
    required_files = [
        "infra/template.yaml",
        "src/monitoring/__init__.py",
        "src/monitoring/metrics_collector.py",
        "src/monitoring/decorator.py",
        "src/monitoring/trust_monitoring.py"
    ]
    
    print("🔍 Validating monitoring setup...")
    
    missing_files = []
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path}")
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    print("✅ All monitoring files present")
    return True


def display_next_steps():
    """
    Display instructions for deploying the monitoring infrastructure.
    """
    print("\n" + "="*60)
    print("🎯 MONITORING SETUP COMPLETE")
    print("="*60)
    print()
    print("Next steps:")
    print()
    print("1. Deploy the updated CloudFormation stack:")
    print("   cd infra/")
    print("   sam deploy --guided")
    print()
    print("2. Set up SNS alerting (optional):")
    print("   aws sns subscribe --topic-arn <AlertingTopicArn> \\")
    print("     --protocol email --notification-endpoint your-email@domain.com")
    print()
    print("3. Access the monitoring dashboard:")
    print("   Check CloudFormation outputs for the dashboard URL")
    print()
    print("4. Test metrics collection:")
    print("   The metrics collector will run every 5 minutes automatically")
    print()
    print("5. Integrate monitoring decorators:")
    print("   See src/monitoring/trust_monitoring.py for examples")
    print("   Add @monitor_lambda_function and @monitor_trust_score_calculation")
    print("   decorators to your Lambda handlers")
    print()
    print("="*60)


def main():
    """
    Main setup function.
    """
    print("🚀 AgentPier Monitoring Setup")
    print("="*40)
    
    # Step 1: Create monitoring package init file
    create_monitoring_init_file()
    
    # Step 2: Merge CloudFormation templates
    if not merge_cloudformation_templates():
        print("❌ Failed to merge CloudFormation templates")
        return 1
    
    # Step 3: Validate setup
    if not validate_monitoring_setup():
        print("❌ Monitoring setup validation failed")
        return 1
    
    # Step 4: Display next steps
    display_next_steps()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())