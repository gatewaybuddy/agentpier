"""
AgentPier V3 Multi-Agent Coordination Framework POC  
Trust Propagation Engine - Handles trust score sharing and verification between agents
"""

import json
import time
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import hmac

try:
    from .agent_registry import AgentRegistry, AgentIdentity
except ImportError:
    # Standalone import
    from agent_registry import AgentRegistry, AgentIdentity

class TrustEventType(Enum):
    COLLABORATION_SUCCESS = "collaboration_success"
    COLLABORATION_FAILURE = "collaboration_failure"
    TASK_COMPLETION = "task_completion"
    TASK_FAILURE = "task_failure"
    COMMUNICATION_SUCCESS = "communication_success"
    COMMUNICATION_FAILURE = "communication_failure"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"

@dataclass
class TrustEvent:
    """Represents an event that affects trust between agents"""
    event_id: str
    source_agent: str
    target_agent: str
    event_type: TrustEventType
    impact: float  # -1.0 to +1.0
    context: Dict
    timestamp: datetime
    verified: bool = False
    verification_signature: Optional[str] = None

@dataclass
class TrustScore:
    """Comprehensive trust score with components and metadata"""
    overall_score: float  # 0.0 to 1.0
    collaboration_score: float
    reliability_score: float
    communication_score: float
    verification_score: float
    last_updated: datetime
    confidence: float  # How confident we are in this score
    sample_size: int  # Number of interactions this is based on

@dataclass 
class TrustPropagationResult:
    """Result of trust score propagation"""
    success: bool
    updated_relationships: List[Tuple[str, str, float]]  # (agent_a, agent_b, new_score)
    trust_events_processed: int
    propagation_depth: int
    timestamp: datetime

class TrustPropagationEngine:
    """Engine for managing trust propagation between agents"""
    
    def __init__(self, agent_registry: AgentRegistry, 
                 storage_path: str = "data/trust_events.json"):
        self.registry = agent_registry
        self.storage_path = storage_path
        self.trust_events: List[TrustEvent] = []
        self.trust_scores: Dict[Tuple[str, str], TrustScore] = {}
        self.propagation_config = {
            'decay_factor': 0.95,  # How much trust decays over distance
            'time_decay_factor': 0.99,  # How much trust decays over time
            'max_propagation_depth': 3,  # Maximum hops for trust propagation
            'min_confidence_threshold': 0.3,  # Minimum confidence for propagation
            'verification_weight': 2.0,  # How much to weight verified interactions
            'sample_size_weight': 0.1,  # How sample size affects confidence
        }
        self.load_trust_data()
    
    def record_trust_event(self, 
                          source_agent: str,
                          target_agent: str,
                          event_type: TrustEventType,
                          impact: float,
                          context: Dict,
                          verification_key: Optional[str] = None) -> str:
        """Record a trust-affecting event between agents"""
        
        event_id = f"{source_agent}-{target_agent}-{int(time.time())}"
        
        event = TrustEvent(
            event_id=event_id,
            source_agent=source_agent,
            target_agent=target_agent,
            event_type=event_type,
            impact=max(-1.0, min(1.0, impact)),  # Clamp to valid range
            context=context,
            timestamp=datetime.now(timezone.utc),
            verified=verification_key is not None
        )
        
        # Add verification signature if provided
        if verification_key:
            event.verification_signature = self._create_verification_signature(
                event, verification_key
            )
        
        self.trust_events.append(event)
        self._update_trust_scores(source_agent, target_agent)
        self.save_trust_data()
        
        return event_id
    
    def _create_verification_signature(self, event: TrustEvent, key: str) -> str:
        """Create verification signature for trust event"""
        message = f"{event.source_agent}:{event.target_agent}:{event.event_type.value}:{event.impact}:{event.timestamp.isoformat()}"
        signature = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
        return signature
    
    def verify_trust_event(self, event_id: str, verification_key: str) -> bool:
        """Verify a trust event with provided key"""
        for event in self.trust_events:
            if event.event_id == event_id:
                expected_signature = self._create_verification_signature(event, verification_key)
                if event.verification_signature == expected_signature:
                    event.verified = True
                    self.save_trust_data()
                    return True
                break
        return False
    
    def _update_trust_scores(self, agent_a: str, agent_b: str):
        """Update trust scores based on recent events"""
        
        # Get relevant events between these agents
        relevant_events = [
            e for e in self.trust_events 
            if (e.source_agent == agent_a and e.target_agent == agent_b) or
               (e.source_agent == agent_b and e.target_agent == agent_a)
        ]
        
        if not relevant_events:
            return
        
        # Calculate component scores
        collaboration_events = [e for e in relevant_events if 'collaboration' in e.event_type.value]
        task_events = [e for e in relevant_events if 'task' in e.event_type.value]
        communication_events = [e for e in relevant_events if 'communication' in e.event_type.value]
        verification_events = [e for e in relevant_events if 'verification' in e.event_type.value]
        
        collaboration_score = self._calculate_component_score(collaboration_events)
        reliability_score = self._calculate_component_score(task_events)
        communication_score = self._calculate_component_score(communication_events)
        verification_score = self._calculate_component_score(verification_events)
        
        # Calculate overall score (weighted average)
        weights = {
            'collaboration': 0.3,
            'reliability': 0.3,
            'communication': 0.2,
            'verification': 0.2
        }
        
        overall_score = (
            collaboration_score * weights['collaboration'] +
            reliability_score * weights['reliability'] +
            communication_score * weights['communication'] +
            verification_score * weights['verification']
        )
        
        # Calculate confidence based on sample size and verification
        verified_events = len([e for e in relevant_events if e.verified])
        total_events = len(relevant_events)
        verification_ratio = verified_events / max(1, total_events)
        
        base_confidence = min(0.9, total_events * self.propagation_config['sample_size_weight'])
        confidence = base_confidence * (0.5 + 0.5 * verification_ratio)
        
        # Store trust score
        trust_score = TrustScore(
            overall_score=overall_score,
            collaboration_score=collaboration_score,
            reliability_score=reliability_score,
            communication_score=communication_score,
            verification_score=verification_score,
            last_updated=datetime.now(timezone.utc),
            confidence=confidence,
            sample_size=total_events
        )
        
        self.trust_scores[(agent_a, agent_b)] = trust_score
        
        # Also update the registry's trust relationship
        self.registry.establish_trust_relationship(agent_a, agent_b, overall_score)
    
    def _calculate_component_score(self, events: List[TrustEvent]) -> float:
        """Calculate trust component score from events"""
        if not events:
            return 0.5  # Neutral score if no events
        
        # Time-weighted average of impacts
        now = datetime.now(timezone.utc)
        total_weight = 0
        weighted_sum = 0
        
        for event in events:
            # Calculate time decay
            days_old = (now - event.timestamp).days
            time_weight = self.propagation_config['time_decay_factor'] ** days_old
            
            # Apply verification weight
            verification_weight = self.propagation_config['verification_weight'] if event.verified else 1.0
            
            final_weight = time_weight * verification_weight
            weighted_sum += event.impact * final_weight
            total_weight += final_weight
        
        if total_weight == 0:
            return 0.5
        
        # Convert from -1:1 range to 0:1 range
        raw_score = weighted_sum / total_weight
        normalized_score = (raw_score + 1.0) / 2.0
        
        return max(0.0, min(1.0, normalized_score))
    
    def get_trust_score(self, agent_a: str, agent_b: str) -> Optional[TrustScore]:
        """Get detailed trust score between two agents"""
        return self.trust_scores.get((agent_a, agent_b)) or self.trust_scores.get((agent_b, agent_a))
    
    def propagate_trust(self, starting_agent: str, max_depth: Optional[int] = None) -> TrustPropagationResult:
        """Propagate trust scores through the agent network"""
        
        max_depth = max_depth or self.propagation_config['max_propagation_depth']
        updated_relationships = []
        processed_events = 0
        
        # Get all agents that have relationships with starting agent
        direct_relationships = []
        for (agent_a, agent_b), trust_score in self.trust_scores.items():
            if agent_a == starting_agent or agent_b == starting_agent:
                other_agent = agent_b if agent_a == starting_agent else agent_a
                direct_relationships.append((other_agent, trust_score.overall_score, trust_score.confidence))
        
        # Propagate trust through network
        for depth in range(1, max_depth + 1):
            depth_updates = []
            
            # For each direct relationship, look for indirect relationships
            for agent_id, trust_level, confidence in direct_relationships:
                if confidence < self.propagation_config['min_confidence_threshold']:
                    continue
                
                # Find agents connected to this agent
                for (agent_c, agent_d), secondary_trust in self.trust_scores.items():
                    if agent_c == agent_id:
                        indirect_agent = agent_d
                    elif agent_d == agent_id:
                        indirect_agent = agent_c
                    else:
                        continue
                    
                    # Skip if we already have direct relationship
                    if indirect_agent == starting_agent:
                        continue
                    
                    if self.trust_scores.get((starting_agent, indirect_agent)) is not None:
                        continue
                    
                    # Calculate propagated trust
                    decay_factor = self.propagation_config['decay_factor'] ** depth
                    propagated_trust = trust_level * secondary_trust.overall_score * decay_factor
                    propagated_confidence = confidence * secondary_trust.confidence * decay_factor
                    
                    if propagated_confidence >= self.propagation_config['min_confidence_threshold']:
                        depth_updates.append((starting_agent, indirect_agent, propagated_trust))
                        updated_relationships.append((starting_agent, indirect_agent, propagated_trust))
                        processed_events += 1
            
            # Apply depth updates to registry
            for agent_a, agent_b, trust_score in depth_updates:
                self.registry.establish_trust_relationship(agent_a, agent_b, trust_score)
        
        return TrustPropagationResult(
            success=True,
            updated_relationships=updated_relationships,
            trust_events_processed=processed_events,
            propagation_depth=max_depth,
            timestamp=datetime.now(timezone.utc)
        )
    
    def calculate_workflow_trust(self, agents: List[str], workflow_type: str = "collaborative") -> Dict:
        """Calculate overall trust for a multi-agent workflow"""
        
        if len(agents) < 2:
            return {'error': 'Need at least 2 agents for workflow trust calculation'}
        
        # Get all pairwise trust scores
        trust_pairs = []
        missing_relationships = []
        
        for i, agent_a in enumerate(agents):
            for agent_b in agents[i+1:]:
                trust_score = self.get_trust_score(agent_a, agent_b)
                if trust_score:
                    trust_pairs.append({
                        'agent_a': agent_a,
                        'agent_b': agent_b,
                        'trust_score': trust_score.overall_score,
                        'confidence': trust_score.confidence
                    })
                else:
                    missing_relationships.append((agent_a, agent_b))
        
        if not trust_pairs:
            return {'error': 'No trust relationships found between agents'}
        
        # Calculate workflow trust based on type
        if workflow_type == "collaborative":
            # All agents need to trust each other - use minimum trust
            min_trust = min(pair['trust_score'] for pair in trust_pairs)
            avg_confidence = sum(pair['confidence'] for pair in trust_pairs) / len(trust_pairs)
            workflow_score = min_trust
            
        elif workflow_type == "sequential":
            # Chain of trust - multiply probabilities
            trust_product = 1.0
            for pair in trust_pairs:
                trust_product *= pair['trust_score']
            workflow_score = trust_product
            avg_confidence = sum(pair['confidence'] for pair in trust_pairs) / len(trust_pairs)
            
        elif workflow_type == "distributed":
            # Average trust across all pairs
            workflow_score = sum(pair['trust_score'] for pair in trust_pairs) / len(trust_pairs)
            avg_confidence = sum(pair['confidence'] for pair in trust_pairs) / len(trust_pairs)
            
        else:
            return {'error': f'Unknown workflow type: {workflow_type}'}
        
        return {
            'workflow_trust_score': workflow_score,
            'confidence': avg_confidence,
            'participating_agents': agents,
            'trust_relationships': trust_pairs,
            'missing_relationships': missing_relationships,
            'workflow_type': workflow_type,
            'recommendation': 'APPROVED' if workflow_score > 0.7 and avg_confidence > 0.5 else 'REVIEW_REQUIRED'
        }
    
    def get_trust_network_analysis(self) -> Dict:
        """Analyze the trust network topology and health"""
        
        # Build network graph
        nodes = set()
        edges = []
        
        for (agent_a, agent_b), trust_score in self.trust_scores.items():
            nodes.add(agent_a)
            nodes.add(agent_b)
            edges.append({
                'source': agent_a,
                'target': agent_b,
                'weight': trust_score.overall_score,
                'confidence': trust_score.confidence
            })
        
        # Calculate network metrics
        total_nodes = len(nodes)
        total_edges = len(edges)
        avg_trust = sum(edge['weight'] for edge in edges) / max(1, total_edges)
        avg_confidence = sum(edge['confidence'] for edge in edges) / max(1, total_edges)
        
        # Calculate trust distribution
        trust_levels = [edge['weight'] for edge in edges]
        high_trust = len([t for t in trust_levels if t > 0.8])
        medium_trust = len([t for t in trust_levels if 0.5 < t <= 0.8])
        low_trust = len([t for t in trust_levels if t <= 0.5])
        
        # Identify highly trusted agents (centrality)
        agent_trust_scores = {}
        for node in nodes:
            connected_edges = [e for e in edges if e['source'] == node or e['target'] == node]
            if connected_edges:
                avg_node_trust = sum(e['weight'] for e in connected_edges) / len(connected_edges)
                agent_trust_scores[node] = avg_node_trust
        
        # Find trust leaders
        trust_leaders = sorted(agent_trust_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'network_stats': {
                'total_agents': total_nodes,
                'total_relationships': total_edges,
                'average_trust': avg_trust,
                'average_confidence': avg_confidence
            },
            'trust_distribution': {
                'high_trust': high_trust,
                'medium_trust': medium_trust,
                'low_trust': low_trust
            },
            'trust_leaders': trust_leaders,
            'network_health': 'HEALTHY' if avg_trust > 0.6 and avg_confidence > 0.5 else 'NEEDS_ATTENTION',
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def save_trust_data(self):
        """Save trust events and scores to storage"""
        try:
            import os
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Prepare data for serialization
            events_data = []
            for event in self.trust_events:
                event_dict = asdict(event)
                event_dict['timestamp'] = event.timestamp.isoformat()
                event_dict['event_type'] = event.event_type.value
                events_data.append(event_dict)
            
            scores_data = {}
            for (agent_a, agent_b), trust_score in self.trust_scores.items():
                key = f"{agent_a}:{agent_b}"
                score_dict = asdict(trust_score)
                score_dict['last_updated'] = trust_score.last_updated.isoformat()
                scores_data[key] = score_dict
            
            trust_data = {
                'trust_events': events_data,
                'trust_scores': scores_data,
                'propagation_config': self.propagation_config,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(trust_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving trust data: {e}")
    
    def load_trust_data(self):
        """Load trust events and scores from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                trust_data = json.load(f)
            
            # Load events
            for event_dict in trust_data.get('trust_events', []):
                event_dict['timestamp'] = datetime.fromisoformat(event_dict['timestamp'])
                event_dict['event_type'] = TrustEventType(event_dict['event_type'])
                self.trust_events.append(TrustEvent(**event_dict))
            
            # Load scores
            for key, score_dict in trust_data.get('trust_scores', {}).items():
                agent_a, agent_b = key.split(':')
                score_dict['last_updated'] = datetime.fromisoformat(score_dict['last_updated'])
                self.trust_scores[(agent_a, agent_b)] = TrustScore(**score_dict)
            
            # Load config
            if 'propagation_config' in trust_data:
                self.propagation_config.update(trust_data['propagation_config'])
                
        except FileNotFoundError:
            # First run, data will be empty
            pass
        except Exception as e:
            print(f"Error loading trust data: {e}")


# Example usage and testing
if __name__ == "__main__":
    from agent_registry import AgentRegistry, CapabilityType, AgentCapability
    
    # Create registry and trust engine
    registry = AgentRegistry("data/test_agent_registry.json")
    trust_engine = TrustPropagationEngine(registry, "data/test_trust_events.json")
    
    # Create test agents
    forge_capabilities = [
        AgentCapability(CapabilityType.CODE_GENERATION, "development", "Software development", 0.9)
    ]
    scout_capabilities = [
        AgentCapability(CapabilityType.DATA_ANALYSIS, "research", "Research and analysis", 0.9)
    ]
    
    forge_id = registry.register_agent("Forge", "Builder agent", "constellation", "1.0.0", forge_capabilities)
    scout_id = registry.register_agent("Scout", "Research agent", "constellation", "1.0.0", scout_capabilities)
    
    # Record some trust events
    trust_engine.record_trust_event(
        forge_id, scout_id,
        TrustEventType.COLLABORATION_SUCCESS,
        0.8,
        {'task': 'research_collaboration', 'outcome': 'excellent_results'}
    )
    
    trust_engine.record_trust_event(
        scout_id, forge_id,
        TrustEventType.TASK_COMPLETION,
        0.7,
        {'task': 'data_analysis', 'quality': 'high'}
    )
    
    # Test trust propagation
    result = trust_engine.propagate_trust(forge_id)
    print(f"Trust propagation result: {result}")
    
    # Test workflow trust
    workflow_trust = trust_engine.calculate_workflow_trust([forge_id, scout_id], "collaborative")
    print(f"Workflow trust: {json.dumps(workflow_trust, indent=2)}")
    
    # Test network analysis
    network_analysis = trust_engine.get_trust_network_analysis()
    print(f"Network analysis: {json.dumps(network_analysis, indent=2)}")