"""
AgentPier V3 Multi-Agent Coordination Framework POC

This package provides a complete implementation of AgentPier's V3 multi-agent coordination 
framework with MCP compatibility, trust verification, and workflow orchestration.

Components:
- AgentRegistry: Agent identity and capability management
- TrustPropagationEngine: Trust score sharing and verification between agents  
- MCPProtocol: MCP-compatible agent-to-agent communication
- WorkflowOrchestrator: Multi-agent task coordination and workflow management
"""

from .agent_registry import (
    AgentRegistry, 
    AgentIdentity, 
    AgentCapability, 
    CapabilityType,
    AgentStatus,
    create_constellation_agent_identity
)

from .trust_propagation import (
    TrustPropagationEngine,
    TrustScore,
    TrustEvent,
    TrustEventType,
    TrustPropagationResult
)

from .mcp_protocol import (
    AgentCoordinationProtocol,
    MCPMessage,
    MessageType,
    CoordinationMessageType,
    MCPTransport,
    WebSocketTransport,
    HTTPTransport,
    TaskDelegation,
    TaskResult
)

from .workflow_orchestrator import (
    WorkflowOrchestrator,
    Workflow,
    WorkflowTask,
    WorkflowExecution,
    WorkflowStatus,
    TaskStatus
)

__version__ = "0.1.0"
__author__ = "AgentPier Team"
__description__ = "AgentPier V3 Multi-Agent Coordination Framework POC"

# Framework version and compatibility
FRAMEWORK_VERSION = "0.1.0"
MCP_COMPATIBILITY_VERSION = "2024-11-05"
AGENTPIER_VERSION_TARGET = "3.0.0"

def get_framework_info():
    """Get framework version and compatibility information"""
    return {
        'framework_version': FRAMEWORK_VERSION,
        'mcp_compatibility': MCP_COMPATIBILITY_VERSION,
        'target_agentpier_version': AGENTPIER_VERSION_TARGET,
        'components': [
            'AgentRegistry',
            'TrustPropagationEngine', 
            'AgentCoordinationProtocol',
            'WorkflowOrchestrator'
        ],
        'features': [
            'Agent identity management',
            'Trust score propagation',
            'MCP-compatible communication',
            'Multi-agent workflow orchestration',
            'Capability discovery and matching',
            'Trust verification for collaborations'
        ]
    }

# Quick start helpers
def create_basic_coordination_setup(data_dir: str = "data"):
    """Create a basic coordination setup for quick testing"""
    
    import os
    os.makedirs(data_dir, exist_ok=True)
    
    registry = AgentRegistry(f"{data_dir}/agent_registry.json")
    trust_engine = TrustPropagationEngine(registry, f"{data_dir}/trust_events.json")
    
    return registry, trust_engine

async def run_coordination_test():
    """Run a quick coordination test"""
    from .integration_test import run_integration_test
    return await run_integration_test()

__all__ = [
    # Core classes
    'AgentRegistry',
    'AgentIdentity', 
    'AgentCapability',
    'TrustPropagationEngine',
    'AgentCoordinationProtocol',
    'WorkflowOrchestrator',
    
    # Enums
    'CapabilityType',
    'AgentStatus', 
    'TrustEventType',
    'MessageType',
    'CoordinationMessageType',
    'WorkflowStatus',
    'TaskStatus',
    
    # Data classes
    'TrustScore',
    'TrustEvent', 
    'TrustPropagationResult',
    'MCPMessage',
    'TaskDelegation',
    'TaskResult',
    'Workflow',
    'WorkflowTask',
    'WorkflowExecution',
    
    # Transport classes
    'MCPTransport',
    'WebSocketTransport',
    'HTTPTransport',
    
    # Helpers
    'create_constellation_agent_identity',
    'create_basic_coordination_setup',
    'get_framework_info',
    'run_coordination_test'
]