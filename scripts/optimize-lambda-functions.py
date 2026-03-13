#!/usr/bin/env python3
"""
AgentPier Lambda Function Cold Start Optimization Script

Applies optimizations to CloudFormation template based on function frequency analysis.
"""

import yaml
import re
from pathlib import Path

def optimize_template():
    """Apply cold start optimizations to SAM template."""
    
    template_path = Path("infra/template.yaml")
    
    # Read the template
    with open(template_path, 'r') as f:
        content = f.read()
    
    # High-frequency functions that need provisioned concurrency and 512MB memory
    tier1_functions = [
        "SearchListingsFunction",
        "GetListingFunction", 
        "TrustQueryFunction",
        "GetMeFunction",
        "VerifyBadgeFunction"
    ]
    
    # Medium-frequency functions that need 384MB memory
    tier2_functions = [
        "CreateListingFunction",
        "TrustRegisterFunction", 
        "VerifyVtokenFunction",
        "GetMarketplaceScoreFunction",
        "CreateTransactionFunction"
    ]
    
    print("🚀 AgentPier Lambda Cold Start Optimization")
    print("=" * 50)
    
    # Apply optimizations
    optimizations_applied = 0
    
    # Add memory optimization to Tier 1 functions
    for func_name in tier1_functions:
        if func_name in content:
            # Add MemorySize: 512 after CodeUri
            pattern = rf"({func_name}:\s*\n\s*Type: AWS::Serverless::Function\s*\n\s*Properties:\s*\n(?:\s*.*\n)*?\s*CodeUri: \.\./src/)"
            replacement = r"\1\n      MemorySize: 512"
            
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                print(f"✅ Added 512MB memory to {func_name}")
                optimizations_applied += 1
    
    # Add memory optimization to Tier 2 functions  
    for func_name in tier2_functions:
        if func_name in content:
            pattern = rf"({func_name}:\s*\n\s*Type: AWS::Serverless::Function\s*\n\s*Properties:\s*\n(?:\s*.*\n)*?\s*CodeUri: \.\./src/)"
            replacement = r"\1\n      MemorySize: 384"
            
            if re.search(pattern, content, flags=re.MULTILINE):
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                print(f"✅ Added 384MB memory to {func_name}")
                optimizations_applied += 1
    
    # Add provisioned concurrency section before Outputs
    provisioned_concurrency = """
  # ============================================
  # Provisioned Concurrency for High-Traffic Functions  
  # ============================================
  
  SearchListingsProvisionedConcurrency:
    Type: AWS::Lambda::ProvisionedConcurrencyConfig
    Condition: IsProduction
    Properties:
      FunctionName: !Ref SearchListingsFunction
      Qualifier: !GetAtt SearchListingsFunction.Version
      ProvisionedConcurrencyUnits: 2
  
  GetListingProvisionedConcurrency:
    Type: AWS::Lambda::ProvisionedConcurrencyConfig
    Condition: IsProduction
    Properties:
      FunctionName: !Ref GetListingFunction
      Qualifier: !GetAtt GetListingFunction.Version
      ProvisionedConcurrencyUnits: 2
      
  TrustQueryProvisionedConcurrency:
    Type: AWS::Lambda::ProvisionedConcurrencyConfig
    Condition: IsProduction
    Properties:
      FunctionName: !Ref TrustQueryFunction
      Qualifier: !GetAtt TrustQueryFunction.Version
      ProvisionedConcurrencyUnits: 1

"""
    
    # Insert provisioned concurrency before Outputs
    outputs_match = re.search(r'\nOutputs:', content)
    if outputs_match:
        content = content[:outputs_match.start()] + provisioned_concurrency + content[outputs_match.start():]
        print("✅ Added provisioned concurrency configurations")
        optimizations_applied += 1
    
    # Write optimized template
    with open(template_path, 'w') as f:
        f.write(content)
    
    print(f"\n📊 Optimization Summary:")
    print(f"   - Total optimizations applied: {optimizations_applied}")
    print(f"   - Tier 1 functions (512MB): {len([f for f in tier1_functions if f in content])}")
    print(f"   - Tier 2 functions (384MB): {len([f for f in tier2_functions if f in content])}")
    print(f"   - Provisioned concurrency: 3 functions (prod only)")
    
    print(f"\n💰 Estimated Monthly Cost Impact:")
    print(f"   - Provisioned concurrency: ~$20-30")
    print(f"   - Memory increases: ~$10-15")
    print(f"   - Total additional: ~$30-45")
    
    print(f"\n⚡ Expected Performance Improvements:")
    print(f"   - Cold start P95: 2-3s → <1s")
    print(f"   - Provisioned functions: <100ms")
    print(f"   - Overall response time: 50-80% improvement")
    
    print(f"\n🔧 Next Steps:")
    print(f"   1. Validate template: sam validate")
    print(f"   2. Deploy to dev: sam deploy --config-env dev") 
    print(f"   3. Monitor cold start metrics")
    print(f"   4. Deploy to prod after validation")

if __name__ == "__main__":
    optimize_template()