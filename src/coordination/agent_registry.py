"""
AgentPier V3 Multi-Agent Coordination Framework POC
Agent Identity Registry - Manages agent identities and capabilities
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import hmac
import uuid

class AgentStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle" 
    BUSY = "busy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class CapabilityType(Enum):
    TASK_EXECUTION = "task_execution"
    DATA_ANALYSIS = "data_analysis"
    CODE_GENERATION = "code_generation"
    COMMUNICATION = "communication"
    DECISION_MAKING = "decision_making"
    MONITORING = "monitoring"
    SECURITY = "security"
    INTEGRATION = "integration"

@dataclass
class AgentCapability:
    """Represents a specific agent capability"""
    type: CapabilityType
    name: str
    description: str
    confidence: float  # 0.0 to 1.0
    last_used: Optional[datetime] = None
    performance_metrics: Optional[Dict] = None

@dataclass
class AgentIdentity:
    """Complete agent identity with capabilities and status"""
    agent_id: str
    name: str
    description: str
    agent_type: str  # e.g., "constellation", "openai-gpt", "anthropic-claude"
    version: str
    capabilities: List[AgentCapability]
    status: AgentStatus
    trust_score: float
    last_seen: datetime
    endpoint: Optional[str] = None  # MCP endpoint or communication channel
    metadata: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['last_seen'] = self.last_seen.isoformat()
        for cap in data['capabilities']:
            if cap['last_used']:
                cap['last_used'] = cap['last_used'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentIdentity':
        """Create from dictionary (JSON deserialization)"""
        # Convert ISO strings back to datetime objects
        data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        
        capabilities = []
        for cap_data in data['capabilities']:
            if cap_data['last_used']:
                cap_data['last_used'] = datetime.fromisoformat(cap_data['last_used'])
            cap_data['type'] = CapabilityType(cap_data['type'])
            capabilities.append(AgentCapability(**cap_data))
        
        data['capabilities'] = capabilities
        data['status'] = AgentStatus(data['status'])
        
        return cls(**data)

class AgentRegistry:
    """Registry for managing agent identities and capabilities"""
    
    def __init__(self, storage_path: str = "data/agent_registry.json"):
        self.storage_path = storage_path
        self.agents: Dict[str, AgentIdentity] = {}
        self.capability_index: Dict[CapabilityType, Set[str]] = {}
        self.trust_relationships: Dict[str, Dict[str, float]] = {}
        self.load_registry()
    
    def register_agent(self, 
                      name: str,
                      description: str, 
                      agent_type: str,
                      version: str,
                      capabilities: List[AgentCapability],
                      endpoint: Optional[str] = None,
                      metadata: Optional[Dict] = None) -> str:
        """Register a new agent and return its ID"""
        
        agent_id = str(uuid.uuid4())
        
        identity = AgentIdentity(
            agent_id=agent_id,
            name=name,
            description=description,
            agent_type=agent_type,
            version=version,
            capabilities=capabilities,
            status=AgentStatus.ACTIVE,
            trust_score=0.5,  # Default neutral trust
            last_seen=datetime.now(timezone.utc),
            endpoint=endpoint,
            metadata=metadata or {}
        )
        
        self.agents[agent_id] = identity
        self._update_capability_index(agent_id, capabilities)
        self.save_registry()
        
        return agent_id
    
    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def update_agent_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update agent status"""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
            self.agents[agent_id].last_seen = datetime.now(timezone.utc)
            self.save_registry()
            return True
        return False
    
    def update_trust_score(self, agent_id: str, trust_score: float) -> bool:
        """Update agent trust score"""
        if agent_id in self.agents and 0.0 <= trust_score <= 1.0:
            self.agents[agent_id].trust_score = trust_score
            self.save_registry()
            return True
        return False
    
    def establish_trust_relationship(self, agent_a: str, agent_b: str, trust_level: float) -> bool:
        """Establish trust relationship between two agents"""
        if agent_a in self.agents and agent_b in self.agents and 0.0 <= trust_level <= 1.0:
            if agent_a not in self.trust_relationships:
                self.trust_relationships[agent_a] = {}
            self.trust_relationships[agent_a][agent_b] = trust_level
            self.save_registry()
            return True
        return False
    
    def get_trust_relationship(self, agent_a: str, agent_b: str) -> Optional[float]:
        """Get trust level between two agents"""
        return self.trust_relationships.get(agent_a, {}).get(agent_b)
    
    def find_agents_by_capability(self, capability_type: CapabilityType, 
                                 min_confidence: float = 0.0,
                                 status_filter: Optional[Set[AgentStatus]] = None) -> List[AgentIdentity]:
        """Find agents with specific capabilities"""
        
        if status_filter is None:
            status_filter = {AgentStatus.ACTIVE, AgentStatus.IDLE}
        
        matching_agents = []
        agent_ids = self.capability_index.get(capability_type, set())
        
        for agent_id in agent_ids:
            agent = self.agents.get(agent_id)
            if not agent or agent.status not in status_filter:
                continue
                
            for capability in agent.capabilities:
                if (capability.type == capability_type and 
                    capability.confidence >= min_confidence):
                    matching_agents.append(agent)
                    break
        
        # Sort by trust score and capability confidence
        matching_agents.sort(key=lambda a: (
            a.trust_score,
            max(cap.confidence for cap in a.capabilities if cap.type == capability_type)
        ), reverse=True)
        
        return matching_agents
    
    def get_agent_recommendations(self, requesting_agent_id: str,
                                 required_capabilities: List[CapabilityType]) -> List[Dict]:
        """Get agent recommendations based on capabilities and trust relationships"""
        
        recommendations = []
        
        for capability in required_capabilities:
            candidates = self.find_agents_by_capability(capability)
            
            for candidate in candidates:
                if candidate.agent_id == requesting_agent_id:
                    continue  # Skip self
                
                # Calculate recommendation score
                trust_relationship = self.get_trust_relationship(requesting_agent_id, candidate.agent_id)
                base_score = candidate.trust_score
                
                if trust_relationship is not None:
                    # Weight relationship trust higher than general trust
                    final_score = (base_score * 0.3) + (trust_relationship * 0.7)
                else:
                    final_score = base_score
                
                capability_confidence = max(
                    cap.confidence for cap in candidate.capabilities 
                    if cap.type == capability
                )
                
                recommendations.append({
                    'agent_id': candidate.agent_id,
                    'agent_name': candidate.name,
                    'capability': capability.value,
                    'capability_confidence': capability_confidence,
                    'trust_score': candidate.trust_score,
                    'relationship_trust': trust_relationship,
                    'recommendation_score': final_score,
                    'endpoint': candidate.endpoint
                })
        
        # Sort by recommendation score
        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return recommendations
    
    def get_registry_stats(self) -> Dict:
        """Get registry statistics"""
        total_agents = len(self.agents)
        active_agents = len([a for a in self.agents.values() if a.status == AgentStatus.ACTIVE])
        
        capability_stats = {}
        for cap_type in CapabilityType:
            capability_stats[cap_type.value] = len(self.capability_index.get(cap_type, set()))
        
        trust_stats = {
            'total_relationships': sum(len(relationships) for relationships in self.trust_relationships.values()),
            'average_trust': sum(
                score for relationships in self.trust_relationships.values()
                for score in relationships.values()
            ) / max(1, sum(len(relationships) for relationships in self.trust_relationships.values()))
        }
        
        return {
            'total_agents': total_agents,
            'active_agents': active_agents,
            'capability_distribution': capability_stats,
            'trust_relationships': trust_stats,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
    
    def _update_capability_index(self, agent_id: str, capabilities: List[AgentCapability]):
        """Update the capability index for fast lookups"""
        for capability in capabilities:
            if capability.type not in self.capability_index:
                self.capability_index[capability.type] = set()
            self.capability_index[capability.type].add(agent_id)
    
    def save_registry(self):
        """Save registry to storage"""
        try:
            import os
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            registry_data = {
                'agents': {agent_id: agent.to_dict() for agent_id, agent in self.agents.items()},
                'trust_relationships': self.trust_relationships,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(registry_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving registry: {e}")
    
    def load_registry(self):
        """Load registry from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                registry_data = json.load(f)
            
            # Load agents
            for agent_id, agent_data in registry_data.get('agents', {}).items():
                self.agents[agent_id] = AgentIdentity.from_dict(agent_data)
                self._update_capability_index(agent_id, self.agents[agent_id].capabilities)
            
            # Load trust relationships
            self.trust_relationships = registry_data.get('trust_relationships', {})
            
        except FileNotFoundError:
            # First run, registry will be empty
            pass
        except Exception as e:
            print(f"Error loading registry: {e}")


# Factory function for creating constellation agents
def create_constellation_agent_identity(agent_name: str, 
                                      agent_description: str,
                                      specialization_capabilities: List[AgentCapability]) -> Dict:
    """Factory function to create constellation agent identity data"""
    
    base_capabilities = [
        AgentCapability(
            type=CapabilityType.COMMUNICATION,
            name="inter_agent_communication", 
            description="Can communicate with other agents in constellation",
            confidence=0.9
        ),
        AgentCapability(
            type=CapabilityType.TASK_EXECUTION,
            name="task_coordination",
            description="Can coordinate and execute tasks with other agents", 
            confidence=0.8
        )
    ]
    
    all_capabilities = base_capabilities + specialization_capabilities
    
    return {
        'name': agent_name,
        'description': agent_description,
        'agent_type': 'constellation',
        'version': '1.0.0',
        'capabilities': all_capabilities,
        'metadata': {
            'constellation': 'kael',
            'creation_time': datetime.now(timezone.utc).isoformat()
        }
    }

# Example usage and testing
if __name__ == "__main__":
    # Create registry
    registry = AgentRegistry("data/test_agent_registry.json")
    
    # Create example constellation agents
    forge_capabilities = [
        AgentCapability(CapabilityType.CODE_GENERATION, "development", "Software development and building", 0.9),
        AgentCapability(CapabilityType.TASK_EXECUTION, "automation", "Task automation and orchestration", 0.8),
        AgentCapability(CapabilityType.DATA_ANALYSIS, "planning", "Project planning and analysis", 0.7)
    ]
    
    scout_capabilities = [
        AgentCapability(CapabilityType.DATA_ANALYSIS, "research", "Information gathering and research", 0.9),
        AgentCapability(CapabilityType.MONITORING, "observation", "System and trend monitoring", 0.8),
        AgentCapability(CapabilityType.COMMUNICATION, "reporting", "Report generation and communication", 0.8)
    ]
    
    # Register agents
    forge_data = create_constellation_agent_identity("Forge", "Overnight builder and planner", forge_capabilities)
    scout_data = create_constellation_agent_identity("Scout", "Information gatherer and analyst", scout_capabilities)
    
    forge_id = registry.register_agent(**forge_data)
    scout_id = registry.register_agent(**scout_data)
    
    # Establish trust relationship
    registry.establish_trust_relationship(forge_id, scout_id, 0.9)
    registry.establish_trust_relationship(scout_id, forge_id, 0.85)
    
    # Test capability discovery
    code_agents = registry.find_agents_by_capability(CapabilityType.CODE_GENERATION)
    print(f"Code generation agents: {[a.name for a in code_agents]}")
    
    # Test recommendations
    recommendations = registry.get_agent_recommendations(forge_id, [CapabilityType.DATA_ANALYSIS])
    print(f"Data analysis recommendations for Forge: {recommendations}")
    
    # Print stats
    print(f"Registry stats: {json.dumps(registry.get_registry_stats(), indent=2)}")