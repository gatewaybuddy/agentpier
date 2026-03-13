#!/usr/bin/env python3
"""
Fix provisioned concurrency configuration to use correct SAM syntax.
"""

import re
from pathlib import Path

def fix_provisioned_concurrency():
    """Fix provisioned concurrency to use correct SAM syntax."""
    
    template_path = Path("infra/template.yaml")
    
    # Read the template
    with open(template_path, 'r') as f:
        content = f.read()
    
    print("🔧 Fixing Provisioned Concurrency Configuration")
    print("=" * 50)
    
    # Remove the incorrect AWS::Lambda::ProvisionedConcurrencyConfig sections
    # Pattern to match the entire provisioned concurrency section
    pattern = r'\n  # ============================================\n  # Provisioned Concurrency for High-Traffic Functions  \n  # ============================================\n  \n  SearchListingsProvisionedConcurrency:.*?\n      ProvisionedConcurrencyUnits: 1\n\n'
    
    content = re.sub(pattern, '\n', content, flags=re.DOTALL)
    
    # Find the functions that need provisioned concurrency and add it correctly
    functions_to_optimize = [
        ("SearchListingsFunction", "handlers.listings.search_listings"),
        ("GetListingFunction", "handlers.listings.get_listing"), 
        ("TrustQueryFunction", "handlers.trust.trust_query")
    ]
    
    for func_name, handler in functions_to_optimize:
        # Add ProvisionedConcurrencyConfig to function properties
        pattern = rf"({func_name}:\s*\n\s*Type: AWS::Serverless::Function\s*\n\s*Properties:.*?Events:.*?\n(?:\s*.*\n)*?)(?=\n  \w|\nOutputs:)"
        
        def add_provisioned_concurrency(match):
            function_def = match.group(1)
            if "ProvisionedConcurrencyConfig" not in function_def:
                # Add ProvisionedConcurrencyConfig before Events
                function_def = function_def.replace("Events:", """ProvisionedConcurrencyConfig:
        - !If
          - IsProduction
          - 2  # Provisioned instances for prod
          - 0  # No provisioned concurrency for dev
      Events:""")
            return function_def
        
        content = re.sub(pattern, add_provisioned_concurrency, content, flags=re.DOTALL)
        print(f"✅ Added provisioned concurrency to {func_name}")
    
    # Write the fixed template
    with open(template_path, 'w') as f:
        f.write(content)
    
    print("\n✅ Provisioned concurrency configuration fixed")
    print("🔍 Run 'sam validate --lint' to verify")

if __name__ == "__main__":
    fix_provisioned_concurrency()