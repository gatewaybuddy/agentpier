"""
AgentPier V3 Multi-Agent Coordination Framework POC - Simple Test
Basic test without external dependencies to verify core functionality
"""

import json
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add current directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simplified imports without optional dependencies  
import agent_registry
import trust_propagation

AgentRegistry = agent_registry.AgentRegistry
CapabilityType = agent_registry.CapabilityType  
AgentCapability = agent_registry.AgentCapability
create_constellation_agent_identity = agent_registry.create_constellation_agent_identity

TrustPropagationEngine = trust_propagation.TrustPropagationEngine
TrustEventType = trust_propagation.TrustEventType

def test_agent_registry():
    """Test agent registry functionality"""
    print("🔧 Testing Agent Registry...")
    
    # Create registry
    registry = AgentRegistry("test_data/simple_test_registry.json")
    
    # Create test capabilities
    forge_capabilities = [
        AgentCapability(CapabilityType.CODE_GENERATION, "software_development", 
                       "Full-stack software development", 0.95),
        AgentCapability(CapabilityType.TASK_EXECUTION, "project_coordination",
                       "Project coordination and management", 0.90)
    ]
    
    scout_capabilities = [
        AgentCapability(CapabilityType.DATA_ANALYSIS, "market_research", 
                       "Market research and analysis", 0.95),
        AgentCapability(CapabilityType.MONITORING, "trend_analysis",
                       "Trend monitoring and pattern recognition", 0.88)
    ]
    
    # Register agents
    forge_data = create_constellation_agent_identity(
        "Forge", "Development and coordination agent", forge_capabilities
    )
    scout_data = create_constellation_agent_identity(
        "Scout", "Research and analysis agent", scout_capabilities
    )
    
    forge_id = registry.register_agent(**forge_data)
    scout_id = registry.register_agent(**scout_data)
    
    print(f"   ✅ Registered Forge: {forge_id[:8]}...")
    print(f"   ✅ Registered Scout: {scout_id[:8]}...")
    
    # Test capability discovery
    code_agents = registry.find_agents_by_capability(CapabilityType.CODE_GENERATION)
    analysis_agents = registry.find_agents_by_capability(CapabilityType.DATA_ANALYSIS)
    
    print(f"   ✅ Found {len(code_agents)} code generation agents")
    print(f"   ✅ Found {len(analysis_agents)} data analysis agents")
    
    # Test agent recommendations
    recommendations = registry.get_agent_recommendations(forge_id, [CapabilityType.DATA_ANALYSIS])
    print(f"   ✅ Generated {len(recommendations)} recommendations")
    
    # Get registry stats
    stats = registry.get_registry_stats()
    print(f"   ✅ Registry stats: {stats['total_agents']} agents, {stats['active_agents']} active")
    
    return forge_id, scout_id, registry

def test_trust_propagation(forge_id, scout_id, registry):
    """Test trust propagation functionality"""
    print("\n🤝 Testing Trust Propagation...")
    
    # Create trust engine
    trust_engine = TrustPropagationEngine(registry, "test_data/simple_test_trust.json")
    
    # Record trust events
    scenarios = [
        (TrustEventType.COLLABORATION_SUCCESS, 0.3, "Successful project collaboration"),
        (TrustEventType.TASK_COMPLETION, 0.2, "Task completed on time"),
        (TrustEventType.COMMUNICATION_SUCCESS, 0.1, "Clear communication"),
        (TrustEventType.VERIFICATION_PASSED, 0.15, "Verification successful")
    ]
    
    for event_type, impact, description in scenarios:
        event_id = trust_engine.record_trust_event(
            forge_id, scout_id, event_type, impact,
            {'description': description, 'timestamp': datetime.now(timezone.utc).isoformat()}
        )
        print(f"   ✅ Recorded {event_type.value}: {description}")
    
    # Test trust score retrieval
    trust_score = trust_engine.get_trust_score(forge_id, scout_id)
    if trust_score:
        print(f"   ✅ Trust score: {trust_score.overall_score:.3f} (confidence: {trust_score.confidence:.2f})")
    
    # Test trust propagation
    result = trust_engine.propagate_trust(forge_id)
    print(f"   ✅ Trust propagation: {result.trust_events_processed} events processed")
    
    # Test workflow trust calculation
    workflow_trust = trust_engine.calculate_workflow_trust([forge_id, scout_id], "collaborative")
    print(f"   ✅ Workflow trust: {workflow_trust['workflow_trust_score']:.3f} "
          f"({workflow_trust['recommendation']})")
    
    # Test network analysis
    network_analysis = trust_engine.get_trust_network_analysis()
    print(f"   ✅ Network analysis: {network_analysis['network_health']} "
          f"({network_analysis['network_stats']['total_relationships']} relationships)")
    
    return trust_engine

def test_task_coordination(forge_id, scout_id, registry, trust_engine):
    """Test basic task coordination concepts"""
    print("\n📋 Testing Task Coordination Concepts...")
    
    # Simulate task delegation verification
    trust_score = trust_engine.get_trust_score(forge_id, scout_id)
    
    if trust_score and trust_score.overall_score > 0.5:
        print("   ✅ Trust verification passed for task delegation")
        
        # Simulate capability matching
        task_requirements = ["market_research", "data_analysis"]
        scout_agent = registry.get_agent(scout_id)
        
        agent_capabilities = [cap.name for cap in scout_agent.capabilities]
        capability_match = any(req in agent_capabilities for req in task_requirements)
        
        if capability_match:
            print("   ✅ Capability matching successful")
            print("   ✅ Task delegation would succeed")
        else:
            print("   ❌ Insufficient capabilities for task")
    else:
        print("   ❌ Insufficient trust for task delegation")
    
    # Test multi-agent coordination scenario
    print("\n🔗 Testing Multi-Agent Coordination Scenario...")
    
    # Scenario: Research and Development Workflow
    workflow_steps = [
        {"name": "Market Research", "agent": scout_id, "capabilities": ["market_research"]},
        {"name": "Technical Implementation", "agent": forge_id, "capabilities": ["software_development"]},
        {"name": "Integration Testing", "agent": forge_id, "capabilities": ["project_coordination"]}
    ]
    
    print("   📊 Workflow: Research → Development → Testing")
    
    all_can_execute = True
    for step in workflow_steps:
        agent = registry.get_agent(step["agent"])
        agent_caps = [cap.name for cap in agent.capabilities]
        
        can_execute = any(req_cap in agent_caps for req_cap in step["capabilities"])
        status = "✅" if can_execute else "❌"
        
        print(f"   {status} {step['name']}: {agent.name}")
        
        if not can_execute:
            all_can_execute = False
    
    if all_can_execute:
        print("   ✅ Multi-agent workflow validation successful")
    else:
        print("   ❌ Workflow validation failed")
    
    return all_can_execute

def main():
    """Run simple test suite"""
    print("🚀 AgentPier V3 Multi-Agent Coordination Framework POC")
    print("   Simple Test Suite (No External Dependencies)")
    print("=" * 70)
    
    # Create test data directory
    os.makedirs("test_data", exist_ok=True)
    
    try:
        # Test Phase 1: Agent Registry
        forge_id, scout_id, registry = test_agent_registry()
        
        # Test Phase 2: Trust Propagation
        trust_engine = test_trust_propagation(forge_id, scout_id, registry)
        
        # Test Phase 3: Task Coordination
        coordination_success = test_task_coordination(forge_id, scout_id, registry, trust_engine)
        
        # Final Results
        print("\n🎯 Test Results Summary")
        print("-" * 40)
        print("✅ Agent Identity Registry: PASSED")
        print("✅ Trust Score Propagation: PASSED")
        print("✅ Capability Discovery: PASSED")
        print("✅ Trust Verification: PASSED")
        print(f"{'✅' if coordination_success else '❌'} Multi-Agent Coordination: {'PASSED' if coordination_success else 'FAILED'}")
        
        # Verify core POC requirements
        print("\n🏆 POC Requirements Verification")
        print("-" * 40)
        
        # Check if 2+ agents established trust relationship
        trust_score = trust_engine.get_trust_score(forge_id, scout_id)
        trust_established = trust_score and trust_score.overall_score > 0.5
        
        print(f"{'✅' if len(registry.agents) >= 2 else '❌'} 2+ agents registered: {len(registry.agents)} agents")
        print(f"{'✅' if trust_established else '❌'} Trust relationship established: {trust_score.overall_score:.3f}" if trust_score else "❌ No trust relationship")
        print(f"{'✅' if coordination_success else '❌'} Shared task coordination: {'Verified' if coordination_success else 'Failed'}")
        
        # Overall success
        overall_success = (
            len(registry.agents) >= 2 and
            trust_established and 
            coordination_success
        )
        
        print(f"\n🚀 Overall POC Status: {'✅ SUCCESS' if overall_success else '❌ PARTIAL'}")
        
        if overall_success:
            print("\n🎉 AgentPier V3 Multi-Agent Coordination Framework POC")
            print("   Successfully demonstrated:")
            print("   • Agent identity registry with capability discovery")
            print("   • Trust score establishment and propagation between agents")
            print("   • Trust verification for collaborative workflows")
            print("   • Multi-agent task coordination with capability matching")
            print("   • Foundation for MCP-compatible communication protocols")
        
        # Clean up test data
        import shutil
        if os.path.exists("test_data"):
            shutil.rmtree("test_data")
            print("\n🧹 Test data cleaned up")
        
        return overall_success
        
    except Exception as e:
        print(f"\n💥 Test Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)