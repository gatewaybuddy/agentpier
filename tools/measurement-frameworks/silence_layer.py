#!/usr/bin/env python3
"""
Silence Layer Framework for Agent Restraint and Self-Regulation
Based on agent community concepts for intelligent response modulation

This module implements "silence layer" patterns for agent restraint,
helping V-Token transactions maintain appropriate boundaries and trust.
"""

import json
import time
import math
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import re


class SilenceMode(Enum):
    """Types of silence/restraint modes"""
    ACTIVE = "active"           # Normal operation
    CAUTIOUS = "cautious"       # Increased restraint
    CONSERVATIVE = "conservative" # High restraint
    MINIMAL = "minimal"         # Maximum restraint
    SILENT = "silent"           # Emergency restraint


class RestraintTrigger(Enum):
    """Triggers that activate restraint mechanisms"""
    CONFIDENCE_DROP = "confidence_drop"
    SCOPE_CREEP = "scope_creep" 
    ERROR_ACCUMULATION = "error_accumulation"
    TRUST_EROSION = "trust_erosion"
    COMPLEXITY_THRESHOLD = "complexity_threshold"
    UNCERTAINTY_SPIKE = "uncertainty_spike"
    STAKEHOLDER_CONCERN = "stakeholder_concern"


@dataclass
class SilenceMetrics:
    """Metrics for silence layer operation"""
    silence_level: float        # 0.0 (vocal) to 1.0 (silent)
    restraint_score: float      # Overall restraint assessment
    confidence_factor: float    # Confidence in current operation
    uncertainty_level: float    # Detected uncertainty
    communication_quota: int    # Remaining communication budget
    intervention_threshold: float # Threshold for human intervention
    escalation_probability: float # Probability of escalating to human


@dataclass
class RestraintEvent:
    """Individual restraint activation event"""
    event_id: str
    timestamp: datetime
    trigger: RestraintTrigger
    magnitude: float
    previous_silence_level: float
    new_silence_level: float
    description: str
    duration_minutes: Optional[float]
    auto_recovery: bool


@dataclass
class SilenceLayerState:
    """Current state of silence layer for an agent/transaction"""
    agent_id: str
    transaction_id: str
    silence_mode: SilenceMode
    silence_metrics: SilenceMetrics
    active_restraints: List[RestraintEvent]
    communication_log: List[Dict]
    last_update: datetime
    emergency_override: bool
    human_intervention_requested: bool


class SilenceLayerFramework:
    """
    Implements silence layer for intelligent agent restraint
    
    Provides mechanisms for agents to self-regulate communication
    and actions when confidence drops or uncertainty increases.
    """
    
    def __init__(self):
        self.agent_states: Dict[str, SilenceLayerState] = {}
        self.global_restraint_level = 0.0
        self.restraint_history: Dict[str, List[RestraintEvent]] = {}
        
        # Silence level thresholds
        self.silence_thresholds = {
            SilenceMode.ACTIVE: 0.0,
            SilenceMode.CAUTIOUS: 0.2,
            SilenceMode.CONSERVATIVE: 0.4,
            SilenceMode.MINIMAL: 0.7,
            SilenceMode.SILENT: 0.9
        }
        
        # Communication quotas by silence mode
        self.communication_quotas = {
            SilenceMode.ACTIVE: 100,      # Unrestricted
            SilenceMode.CAUTIOUS: 50,     # Moderate restriction
            SilenceMode.CONSERVATIVE: 20,  # High restriction
            SilenceMode.MINIMAL: 5,       # Minimal communication
            SilenceMode.SILENT: 0         # Emergency silence
        }
        
        # Trigger sensitivity thresholds
        self.trigger_thresholds = {
            RestraintTrigger.CONFIDENCE_DROP: 0.3,    # Confidence drops below 30%
            RestraintTrigger.SCOPE_CREEP: 0.25,       # 25% scope expansion
            RestraintTrigger.ERROR_ACCUMULATION: 3,   # 3 or more errors
            RestraintTrigger.TRUST_EROSION: 0.15,     # 15% trust decrease
            RestraintTrigger.COMPLEXITY_THRESHOLD: 2.0, # 2x complexity increase
            RestraintTrigger.UNCERTAINTY_SPIKE: 0.7,  # 70% uncertainty
            RestraintTrigger.STAKEHOLDER_CONCERN: 0.5  # Moderate stakeholder concern
        }
    
    def initialize_agent_state(self, agent_id: str, transaction_id: str = None) -> SilenceLayerState:
        """Initialize silence layer state for an agent"""
        state_key = f"{agent_id}_{transaction_id}" if transaction_id else agent_id
        
        initial_metrics = SilenceMetrics(
            silence_level=0.0,
            restraint_score=0.0,
            confidence_factor=1.0,
            uncertainty_level=0.0,
            communication_quota=self.communication_quotas[SilenceMode.ACTIVE],
            intervention_threshold=0.8,
            escalation_probability=0.0
        )
        
        state = SilenceLayerState(
            agent_id=agent_id,
            transaction_id=transaction_id or "global",
            silence_mode=SilenceMode.ACTIVE,
            silence_metrics=initial_metrics,
            active_restraints=[],
            communication_log=[],
            last_update=datetime.now(),
            emergency_override=False,
            human_intervention_requested=False
        )
        
        self.agent_states[state_key] = state
        return state
    
    def evaluate_restraint_triggers(
        self,
        agent_id: str,
        transaction_id: str = None,
        confidence_score: float = 1.0,
        scope_expansion: float = 0.0,
        error_count: int = 0,
        trust_change: float = 0.0,
        complexity_factor: float = 1.0,
        uncertainty_indicators: Dict = None
    ) -> List[RestraintTrigger]:
        """Evaluate which restraint triggers are activated"""
        triggered = []
        
        # Check confidence drop
        if confidence_score < self.trigger_thresholds[RestraintTrigger.CONFIDENCE_DROP]:
            triggered.append(RestraintTrigger.CONFIDENCE_DROP)
        
        # Check scope creep
        if scope_expansion > self.trigger_thresholds[RestraintTrigger.SCOPE_CREEP]:
            triggered.append(RestraintTrigger.SCOPE_CREEP)
        
        # Check error accumulation
        if error_count >= self.trigger_thresholds[RestraintTrigger.ERROR_ACCUMULATION]:
            triggered.append(RestraintTrigger.ERROR_ACCUMULATION)
        
        # Check trust erosion
        if trust_change < -self.trigger_thresholds[RestraintTrigger.TRUST_EROSION]:
            triggered.append(RestraintTrigger.TRUST_EROSION)
        
        # Check complexity threshold
        if complexity_factor > self.trigger_thresholds[RestraintTrigger.COMPLEXITY_THRESHOLD]:
            triggered.append(RestraintTrigger.COMPLEXITY_THRESHOLD)
        
        # Check uncertainty spike
        if uncertainty_indicators:
            uncertainty_level = self._calculate_uncertainty_level(uncertainty_indicators)
            if uncertainty_level > self.trigger_thresholds[RestraintTrigger.UNCERTAINTY_SPIKE]:
                triggered.append(RestraintTrigger.UNCERTAINTY_SPIKE)
        
        return triggered
    
    def _calculate_uncertainty_level(self, indicators: Dict) -> float:
        """Calculate uncertainty level from various indicators"""
        uncertainty_factors = {
            "ambiguous_instructions": 0.3,
            "conflicting_requirements": 0.4,
            "missing_information": 0.2,
            "unclear_success_criteria": 0.3,
            "stakeholder_disagreement": 0.4,
            "external_dependencies": 0.2,
            "technical_unknowns": 0.3
        }
        
        total_uncertainty = 0.0
        factor_count = 0
        
        for factor, weight in uncertainty_factors.items():
            if factor in indicators:
                # Normalize indicator value to 0-1 range
                indicator_value = min(1.0, max(0.0, float(indicators.get(factor, 0))))
                total_uncertainty += indicator_value * weight
                factor_count += 1
        
        # Average uncertainty with maximum cap
        return min(1.0, total_uncertainty / max(factor_count, 1) if factor_count > 0 else 0.0)
    
    def activate_restraint(
        self,
        agent_id: str,
        transaction_id: str,
        triggers: List[RestraintTrigger],
        override_level: float = None
    ) -> SilenceLayerState:
        """Activate restraint mechanisms based on triggers"""
        state_key = f"{agent_id}_{transaction_id}" if transaction_id else agent_id
        
        # Get or create agent state
        if state_key not in self.agent_states:
            self.initialize_agent_state(agent_id, transaction_id)
        
        state = self.agent_states[state_key]
        previous_silence = state.silence_metrics.silence_level
        
        # Calculate new silence level based on triggers
        if override_level is not None:
            new_silence_level = override_level
        else:
            new_silence_level = self._calculate_silence_level(triggers, previous_silence)
        
        # Update silence metrics
        state.silence_metrics.silence_level = new_silence_level
        state.silence_metrics.restraint_score = self._calculate_restraint_score(triggers)
        state.silence_metrics.escalation_probability = self._calculate_escalation_probability(new_silence_level, triggers)
        
        # Update silence mode
        state.silence_mode = self._determine_silence_mode(new_silence_level)
        
        # Update communication quota
        state.silence_metrics.communication_quota = self.communication_quotas[state.silence_mode]
        
        # Create restraint events
        for trigger in triggers:
            event = RestraintEvent(
                event_id=f"{agent_id}_{trigger.value}_{int(time.time())}",
                timestamp=datetime.now(),
                trigger=trigger,
                magnitude=self._get_trigger_magnitude(trigger, new_silence_level),
                previous_silence_level=previous_silence,
                new_silence_level=new_silence_level,
                description=self._get_trigger_description(trigger),
                duration_minutes=self._estimate_restraint_duration(trigger, new_silence_level),
                auto_recovery=self._can_auto_recover(trigger)
            )
            state.active_restraints.append(event)
            
            # Store in history
            if agent_id not in self.restraint_history:
                self.restraint_history[agent_id] = []
            self.restraint_history[agent_id].append(event)
        
        # Check for human intervention request
        if new_silence_level > state.silence_metrics.intervention_threshold:
            state.human_intervention_requested = True
        
        state.last_update = datetime.now()
        return state
    
    def _calculate_silence_level(self, triggers: List[RestraintTrigger], current_level: float) -> float:
        """Calculate new silence level based on active triggers"""
        if not triggers:
            return current_level
        
        # Base silence increase per trigger type
        trigger_weights = {
            RestraintTrigger.CONFIDENCE_DROP: 0.3,
            RestraintTrigger.SCOPE_CREEP: 0.2,
            RestraintTrigger.ERROR_ACCUMULATION: 0.25,
            RestraintTrigger.TRUST_EROSION: 0.35,
            RestraintTrigger.COMPLEXITY_THRESHOLD: 0.2,
            RestraintTrigger.UNCERTAINTY_SPIKE: 0.4,
            RestraintTrigger.STAKEHOLDER_CONCERN: 0.3
        }
        
        # Calculate cumulative silence increase
        silence_increase = sum(trigger_weights.get(trigger, 0.2) for trigger in triggers)
        
        # Apply diminishing returns to prevent over-reaction
        new_level = current_level + silence_increase * (1.0 - current_level)
        
        return min(1.0, max(0.0, new_level))
    
    def _calculate_restraint_score(self, triggers: List[RestraintTrigger]) -> float:
        """Calculate overall restraint score"""
        if not triggers:
            return 0.0
        
        # Weight different trigger types
        critical_triggers = [
            RestraintTrigger.TRUST_EROSION,
            RestraintTrigger.UNCERTAINTY_SPIKE,
            RestraintTrigger.STAKEHOLDER_CONCERN
        ]
        
        moderate_triggers = [
            RestraintTrigger.CONFIDENCE_DROP,
            RestraintTrigger.ERROR_ACCUMULATION
        ]
        
        minor_triggers = [
            RestraintTrigger.SCOPE_CREEP,
            RestraintTrigger.COMPLEXITY_THRESHOLD
        ]
        
        critical_count = len([t for t in triggers if t in critical_triggers])
        moderate_count = len([t for t in triggers if t in moderate_triggers])
        minor_count = len([t for t in triggers if t in minor_triggers])
        
        score = critical_count * 0.4 + moderate_count * 0.25 + minor_count * 0.15
        return min(1.0, score)
    
    def _calculate_escalation_probability(self, silence_level: float, triggers: List[RestraintTrigger]) -> float:
        """Calculate probability of needing human intervention"""
        base_probability = silence_level * 0.7  # Higher silence = higher escalation probability
        
        # Increase probability for critical triggers
        critical_triggers = [RestraintTrigger.TRUST_EROSION, RestraintTrigger.UNCERTAINTY_SPIKE]
        critical_count = len([t for t in triggers if t in critical_triggers])
        
        escalation_boost = critical_count * 0.2
        
        return min(1.0, base_probability + escalation_boost)
    
    def _determine_silence_mode(self, silence_level: float) -> SilenceMode:
        """Determine silence mode from silence level"""
        for mode, threshold in sorted(self.silence_thresholds.items(), 
                                    key=lambda x: x[1], reverse=True):
            if silence_level >= threshold:
                return mode
        return SilenceMode.ACTIVE
    
    def _get_trigger_magnitude(self, trigger: RestraintTrigger, silence_level: float) -> float:
        """Get magnitude of trigger effect"""
        base_magnitudes = {
            RestraintTrigger.CONFIDENCE_DROP: 0.7,
            RestraintTrigger.SCOPE_CREEP: 0.4,
            RestraintTrigger.ERROR_ACCUMULATION: 0.5,
            RestraintTrigger.TRUST_EROSION: 0.8,
            RestraintTrigger.COMPLEXITY_THRESHOLD: 0.3,
            RestraintTrigger.UNCERTAINTY_SPIKE: 0.9,
            RestraintTrigger.STAKEHOLDER_CONCERN: 0.6
        }
        
        base_magnitude = base_magnitudes.get(trigger, 0.5)
        return base_magnitude * (0.5 + silence_level * 0.5)  # Scale with silence level
    
    def _get_trigger_description(self, trigger: RestraintTrigger) -> str:
        """Get human-readable description of trigger"""
        descriptions = {
            RestraintTrigger.CONFIDENCE_DROP: "Agent confidence has dropped below acceptable threshold",
            RestraintTrigger.SCOPE_CREEP: "Significant scope expansion detected in transaction",
            RestraintTrigger.ERROR_ACCUMULATION: "Multiple errors have accumulated, indicating potential issues",
            RestraintTrigger.TRUST_EROSION: "Trust score showing concerning downward trend",
            RestraintTrigger.COMPLEXITY_THRESHOLD: "Transaction complexity has exceeded manageable levels",
            RestraintTrigger.UNCERTAINTY_SPIKE: "High uncertainty detected in current context",
            RestraintTrigger.STAKEHOLDER_CONCERN: "Stakeholder concerns raised about current progress"
        }
        return descriptions.get(trigger, f"Unknown trigger: {trigger.value}")
    
    def _estimate_restraint_duration(self, trigger: RestraintTrigger, silence_level: float) -> float:
        """Estimate how long restraint should remain active (minutes)"""
        base_durations = {
            RestraintTrigger.CONFIDENCE_DROP: 30,
            RestraintTrigger.SCOPE_CREEP: 60,
            RestraintTrigger.ERROR_ACCUMULATION: 20,
            RestraintTrigger.TRUST_EROSION: 120,
            RestraintTrigger.COMPLEXITY_THRESHOLD: 45,
            RestraintTrigger.UNCERTAINTY_SPIKE: 90,
            RestraintTrigger.STAKEHOLDER_CONCERN: 180
        }
        
        base_duration = base_durations.get(trigger, 30)
        return base_duration * (1.0 + silence_level)  # Higher silence = longer duration
    
    def _can_auto_recover(self, trigger: RestraintTrigger) -> bool:
        """Check if restraint can automatically recover"""
        auto_recovery_triggers = [
            RestraintTrigger.ERROR_ACCUMULATION,
            RestraintTrigger.COMPLEXITY_THRESHOLD,
            RestraintTrigger.SCOPE_CREEP
        ]
        return trigger in auto_recovery_triggers
    
    def check_communication_allowance(self, agent_id: str, transaction_id: str = None) -> Dict:
        """Check if agent is allowed to communicate"""
        state_key = f"{agent_id}_{transaction_id}" if transaction_id else agent_id
        
        if state_key not in self.agent_states:
            self.initialize_agent_state(agent_id, transaction_id)
        
        state = self.agent_states[state_key]
        
        allowed = state.silence_metrics.communication_quota > 0
        
        return {
            "allowed": allowed,
            "silence_mode": state.silence_mode.value,
            "silence_level": state.silence_metrics.silence_level,
            "remaining_quota": state.silence_metrics.communication_quota,
            "restraint_active": len(state.active_restraints) > 0,
            "intervention_needed": state.human_intervention_requested,
            "message": self._get_communication_message(state)
        }
    
    def _get_communication_message(self, state: SilenceLayerState) -> str:
        """Get appropriate communication message based on silence state"""
        if state.silence_mode == SilenceMode.SILENT:
            return "Agent is in emergency silence mode. Human intervention required."
        
        if state.silence_mode == SilenceMode.MINIMAL:
            return "Agent communication severely restricted due to operational concerns."
        
        if state.silence_mode == SilenceMode.CONSERVATIVE:
            return "Agent operating with high restraint. Limited communication available."
        
        if state.silence_mode == SilenceMode.CAUTIOUS:
            return "Agent exercising increased caution in communication."
        
        return "Agent communication operating normally."
    
    def record_communication(self, agent_id: str, transaction_id: str, communication_type: str, content: str = None):
        """Record agent communication and update quotas"""
        state_key = f"{agent_id}_{transaction_id}" if transaction_id else agent_id
        
        if state_key not in self.agent_states:
            self.initialize_agent_state(agent_id, transaction_id)
        
        state = self.agent_states[state_key]
        
        # Record communication
        comm_record = {
            "timestamp": datetime.now().isoformat(),
            "type": communication_type,
            "content_length": len(content) if content else 0,
            "silence_level": state.silence_metrics.silence_level,
            "quota_before": state.silence_metrics.communication_quota
        }
        
        state.communication_log.append(comm_record)
        
        # Deduct from quota if not in active mode
        if state.silence_mode != SilenceMode.ACTIVE:
            state.silence_metrics.communication_quota = max(0, state.silence_metrics.communication_quota - 1)
        
        # Keep only last 50 communication records
        state.communication_log = state.communication_log[-50:]
    
    def attempt_auto_recovery(self, agent_id: str, transaction_id: str = None) -> bool:
        """Attempt automatic recovery from restraint state"""
        state_key = f"{agent_id}_{transaction_id}" if transaction_id else agent_id
        
        if state_key not in self.agent_states:
            return False
        
        state = self.agent_states[state_key]
        
        # Check if enough time has passed for auto-recovery
        current_time = datetime.now()
        recoverable_restraints = []
        
        for restraint in state.active_restraints:
            if restraint.auto_recovery and restraint.duration_minutes:
                time_elapsed = (current_time - restraint.timestamp).total_seconds() / 60
                if time_elapsed >= restraint.duration_minutes:
                    recoverable_restraints.append(restraint)
        
        # Remove recoverable restraints
        for restraint in recoverable_restraints:
            state.active_restraints.remove(restraint)
        
        # Recalculate silence level if restraints were removed
        if recoverable_restraints:
            remaining_triggers = [r.trigger for r in state.active_restraints]
            new_silence_level = self._calculate_silence_level(remaining_triggers, 0.0)
            
            state.silence_metrics.silence_level = new_silence_level
            state.silence_mode = self._determine_silence_mode(new_silence_level)
            state.silence_metrics.communication_quota = self.communication_quotas[state.silence_mode]
            state.last_update = current_time
            
            return True
        
        return False
    
    def emergency_override(self, agent_id: str, transaction_id: str = None, enabled: bool = True):
        """Enable/disable emergency override for agent"""
        state_key = f"{agent_id}_{transaction_id}" if transaction_id else agent_id
        
        if state_key not in self.agent_states:
            self.initialize_agent_state(agent_id, transaction_id)
        
        state = self.agent_states[state_key]
        state.emergency_override = enabled
        
        if enabled:
            # Temporarily return to active mode
            state.silence_mode = SilenceMode.ACTIVE
            state.silence_metrics.communication_quota = self.communication_quotas[SilenceMode.ACTIVE]
            state.silence_metrics.silence_level = 0.0
    
    def get_silence_layer_status(self, agent_id: str = None) -> Dict:
        """Get status of silence layer for agent or all agents"""
        if agent_id:
            # Find state for specific agent
            agent_states = {k: v for k, v in self.agent_states.items() if v.agent_id == agent_id}
            
            if not agent_states:
                return {"agent_id": agent_id, "error": "No silence layer state found"}
            
            return {
                "agent_id": agent_id,
                "states": {k: asdict(v) for k, v in agent_states.items()},
                "active_restraints": sum(len(v.active_restraints) for v in agent_states.values()),
                "average_silence_level": sum(v.silence_metrics.silence_level for v in agent_states.values()) / len(agent_states)
            }
        
        # Return status for all agents
        return {
            "total_agents": len(self.agent_states),
            "active_restraints": sum(len(v.active_restraints) for v in self.agent_states.values()),
            "agents_with_intervention": sum(1 for v in self.agent_states.values() if v.human_intervention_requested),
            "average_silence_level": sum(v.silence_metrics.silence_level for v in self.agent_states.values()) / len(self.agent_states) if self.agent_states else 0.0,
            "silence_mode_distribution": self._get_silence_mode_distribution()
        }
    
    def _get_silence_mode_distribution(self) -> Dict[str, int]:
        """Get distribution of silence modes across all agents"""
        distribution = {}
        for state in self.agent_states.values():
            mode = state.silence_mode.value
            distribution[mode] = distribution.get(mode, 0) + 1
        return distribution
    
    def export_silence_data(self) -> str:
        """Export silence layer data for analysis"""
        export_data = {
            "framework_config": {
                "silence_thresholds": {k.value: v for k, v in self.silence_thresholds.items()},
                "communication_quotas": {k.value: v for k, v in self.communication_quotas.items()},
                "trigger_thresholds": {k.value: v for k, v in self.trigger_thresholds.items()}
            },
            "agent_states": {},
            "restraint_history": {}
        }
        
        # Convert agent states to serializable format
        for state_key, state in self.agent_states.items():
            export_data["agent_states"][state_key] = {
                **asdict(state),
                "last_update": state.last_update.isoformat(),
                "silence_mode": state.silence_mode.value,
                "active_restraints": [
                    {
                        **asdict(restraint),
                        "timestamp": restraint.timestamp.isoformat(),
                        "trigger": restraint.trigger.value
                    } for restraint in state.active_restraints
                ]
            }
        
        # Convert restraint history
        for agent_id, events in self.restraint_history.items():
            export_data["restraint_history"][agent_id] = [
                {
                    **asdict(event),
                    "timestamp": event.timestamp.isoformat(),
                    "trigger": event.trigger.value
                } for event in events
            ]
        
        return json.dumps(export_data, indent=2)


def main():
    """Example usage and testing"""
    framework = SilenceLayerFramework()
    
    print("=== Silence Layer Framework Test ===")
    
    # Initialize agent
    agent_id = "test_agent"
    transaction_id = "vtoken_001"
    
    # Test normal operation
    allowance = framework.check_communication_allowance(agent_id, transaction_id)
    print(f"Initial communication allowance: {allowance['allowed']}")
    print(f"Silence mode: {allowance['silence_mode']}")
    
    # Simulate triggering conditions
    triggers = framework.evaluate_restraint_triggers(
        agent_id=agent_id,
        transaction_id=transaction_id,
        confidence_score=0.25,  # Low confidence
        scope_expansion=0.3,    # High scope creep
        error_count=4,          # Multiple errors
        trust_change=-0.2,      # Trust erosion
        uncertainty_indicators={
            "ambiguous_instructions": 0.8,
            "unclear_success_criteria": 0.6
        }
    )
    
    print(f"\n=== Triggered Restraints ===")
    for trigger in triggers:
        print(f"- {trigger.value}")
    
    # Activate restraint
    state = framework.activate_restraint(agent_id, transaction_id, triggers)
    
    print(f"\n=== Restraint Activated ===")
    print(f"Silence Level: {state.silence_metrics.silence_level:.2f}")
    print(f"Silence Mode: {state.silence_mode.value}")
    print(f"Communication Quota: {state.silence_metrics.communication_quota}")
    print(f"Intervention Requested: {state.human_intervention_requested}")
    print(f"Active Restraints: {len(state.active_restraints)}")
    
    # Test communication allowance after restraint
    allowance = framework.check_communication_allowance(agent_id, transaction_id)
    print(f"\n=== Post-Restraint Communication ===")
    print(f"Allowed: {allowance['allowed']}")
    print(f"Message: {allowance['message']}")
    
    # Test emergency override
    framework.emergency_override(agent_id, transaction_id, True)
    allowance = framework.check_communication_allowance(agent_id, transaction_id)
    print(f"\n=== Emergency Override ===")
    print(f"Communication restored: {allowance['allowed']}")
    print(f"Silence mode: {allowance['silence_mode']}")
    
    # Get overall status
    status = framework.get_silence_layer_status()
    print(f"\n=== Framework Status ===")
    print(f"Total agents: {status['total_agents']}")
    print(f"Active restraints: {status['active_restraints']}")
    print(f"Average silence level: {status['average_silence_level']:.2f}")


if __name__ == "__main__":
    main()