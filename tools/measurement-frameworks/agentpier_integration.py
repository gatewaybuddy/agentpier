#!/usr/bin/env python3
"""
AgentPier Integration Module for Agent Community Measurement Frameworks

This module integrates confidence decay, scope creep analysis, and silence layer
frameworks with AgentPier's trust scoring and V-Token validation systems.
"""

import json
import time
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from confidence_decay import ConfidenceDecayFramework, TrustScoreValidation
from scope_creep_analysis import ScopeCreepAnalyzer, ScopeCreepAnalysis  
from silence_layer import SilenceLayerFramework, SilenceLayerState


@dataclass
class IntegratedMeasurement:
    """Combined measurement result from all frameworks"""
    agent_id: str
    transaction_id: str
    timestamp: datetime
    
    # Trust and confidence metrics
    trust_validation: TrustScoreValidation
    confidence_recommendation: Dict
    
    # Scope analysis
    scope_analysis: ScopeCreepAnalysis
    
    # Silence layer state
    silence_state: SilenceLayerState
    communication_allowance: Dict
    
    # Integrated recommendations
    integrated_risk_score: float
    overall_trust_adjustment: float
    action_recommendations: List[str]
    intervention_required: bool


@dataclass
class AgentPierMetrics:
    """Comprehensive metrics for AgentPier integration"""
    measurement_timestamp: datetime
    agent_performance_score: float
    trust_score_accuracy: float
    vtoken_validation_confidence: float
    scope_management_score: float
    communication_health_score: float
    overall_system_health: float


class AgentPierMeasurementIntegrator:
    """
    Integrates all measurement frameworks with AgentPier systems
    
    Provides unified interface for trust validation, scope management,
    and agent restraint mechanisms within AgentPier ecosystem.
    """
    
    def __init__(self, agentpier_config: Dict = None):
        # Initialize component frameworks
        self.confidence_framework = ConfidenceDecayFramework()
        self.scope_analyzer = ScopeCreepAnalyzer()
        self.silence_layer = SilenceLayerFramework()
        
        # AgentPier integration configuration
        self.config = agentpier_config or self._get_default_config()
        
        # Measurement history
        self.measurement_history: Dict[str, List[IntegratedMeasurement]] = {}
        
        # Performance tracking
        self.performance_metrics: Dict[str, AgentPierMetrics] = {}
        
        # Integration state
        self.vtoken_validations = 0
        self.trust_adjustments = 0
        self.intervention_requests = 0
        
    def _get_default_config(self) -> Dict:
        """Get default AgentPier integration configuration"""
        return {
            "trust_score_weight": 0.4,          # Weight for trust score in final calculation
            "confidence_decay_weight": 0.3,     # Weight for confidence decay
            "scope_creep_weight": 0.2,          # Weight for scope management
            "silence_layer_weight": 0.1,        # Weight for communication health
            
            "intervention_threshold": 0.7,      # Threshold for human intervention
            "trust_adjustment_threshold": 0.15, # Threshold for trust score adjustment
            "auto_restraint_enabled": True,     # Enable automatic restraint activation
            
            "vtoken_validation_mode": "enhanced", # Standard, enhanced, or strict
            "scope_monitoring_enabled": True,   # Enable scope creep monitoring
            "confidence_tracking_enabled": True, # Enable confidence decay tracking
            
            "integration_mode": "production",   # Development, staging, or production
            "metrics_retention_days": 30,       # How long to retain measurement history
        }
    
    def perform_integrated_measurement(
        self,
        agent_id: str,
        transaction_id: str,
        current_trust_score: float,
        interaction_context: Dict,
        vtoken_data: Dict = None
    ) -> IntegratedMeasurement:
        """
        Perform comprehensive measurement using all frameworks
        
        Args:
            agent_id: Agent identifier
            transaction_id: V-Token transaction ID
            current_trust_score: Current AgentPier trust score
            interaction_context: Context about recent interactions
            vtoken_data: V-Token transaction data
        
        Returns:
            IntegratedMeasurement with complete analysis and recommendations
        """
        measurement_start = datetime.now()
        
        # Extract context data
        turns_since_validation = interaction_context.get("turns_since_validation", 0)
        interaction_history = interaction_context.get("interaction_history", [])
        scope_data = interaction_context.get("scope_data", {})
        
        # 1. Trust Score Validation with Confidence Decay
        trust_validation = self.confidence_framework.validate_trust_score(
            agent_id=agent_id,
            trust_score=current_trust_score,
            turns_since_last_validation=turns_since_validation,
            interaction_history=interaction_history
        )
        
        confidence_recommendation = self.confidence_framework.generate_trust_adjustment_recommendation(trust_validation)
        
        # 2. Scope Creep Analysis (if V-Token data available)
        scope_analysis = None
        if vtoken_data and scope_data:
            original_scope = scope_data.get("original_scope", {})
            current_scope = scope_data.get("current_scope", {})
            
            if original_scope and current_scope:
                scope_analysis = self.scope_analyzer.analyze_scope_change(
                    transaction_id=transaction_id,
                    agent_id=agent_id,
                    original_scope=original_scope,
                    current_scope=current_scope,
                    interaction_history=interaction_history
                )
        
        # 3. Silence Layer Evaluation
        # Evaluate restraint triggers
        restraint_triggers = self.silence_layer.evaluate_restraint_triggers(
            agent_id=agent_id,
            transaction_id=transaction_id,
            confidence_score=trust_validation.confidence_metrics.current_confidence,
            scope_expansion=scope_analysis.scope_metrics.expansion_percentage if scope_analysis else 0.0,
            error_count=interaction_context.get("error_count", 0),
            trust_change=current_trust_score - interaction_context.get("previous_trust_score", current_trust_score),
            complexity_factor=scope_analysis.scope_metrics.complexity_factor if scope_analysis else 1.0,
            uncertainty_indicators=interaction_context.get("uncertainty_indicators", {})
        )
        
        # Activate restraint if triggers detected
        if restraint_triggers:
            silence_state = self.silence_layer.activate_restraint(
                agent_id=agent_id,
                transaction_id=transaction_id,
                triggers=restraint_triggers
            )
        else:
            # Check existing state or initialize
            state_key = f"{agent_id}_{transaction_id}"
            if state_key in self.silence_layer.agent_states:
                silence_state = self.silence_layer.agent_states[state_key]
            else:
                silence_state = self.silence_layer.initialize_agent_state(agent_id, transaction_id)
        
        communication_allowance = self.silence_layer.check_communication_allowance(agent_id, transaction_id)
        
        # 4. Integrated Analysis
        integrated_risk_score = self._calculate_integrated_risk_score(
            trust_validation, scope_analysis, silence_state
        )
        
        overall_trust_adjustment = self._calculate_overall_trust_adjustment(
            confidence_recommendation, scope_analysis, silence_state
        )
        
        action_recommendations = self._generate_integrated_recommendations(
            trust_validation, scope_analysis, silence_state, integrated_risk_score
        )
        
        intervention_required = (
            integrated_risk_score > self.config["intervention_threshold"] or
            silence_state.human_intervention_requested or
            (scope_analysis and scope_analysis.severity.value in ["major", "critical"])
        )
        
        # Create integrated measurement
        measurement = IntegratedMeasurement(
            agent_id=agent_id,
            transaction_id=transaction_id,
            timestamp=measurement_start,
            trust_validation=trust_validation,
            confidence_recommendation=confidence_recommendation,
            scope_analysis=scope_analysis,
            silence_state=silence_state,
            communication_allowance=communication_allowance,
            integrated_risk_score=integrated_risk_score,
            overall_trust_adjustment=overall_trust_adjustment,
            action_recommendations=action_recommendations,
            intervention_required=intervention_required
        )
        
        # Store measurement history
        if agent_id not in self.measurement_history:
            self.measurement_history[agent_id] = []
        self.measurement_history[agent_id].append(measurement)
        
        # Keep only recent measurements
        retention_limit = self.config["metrics_retention_days"] * 24 * 60 // 15  # Assuming 15min intervals
        self.measurement_history[agent_id] = self.measurement_history[agent_id][-retention_limit:]
        
        # Update counters
        self.vtoken_validations += 1
        if abs(overall_trust_adjustment) > self.config["trust_adjustment_threshold"]:
            self.trust_adjustments += 1
        if intervention_required:
            self.intervention_requests += 1
        
        return measurement
    
    def _calculate_integrated_risk_score(
        self, 
        trust_validation: TrustScoreValidation,
        scope_analysis: Optional[ScopeCreepAnalysis],
        silence_state: SilenceLayerState
    ) -> float:
        """Calculate integrated risk score from all measurements"""
        
        # Risk from confidence decay
        confidence_risk = 1.0 - trust_validation.confidence_metrics.current_confidence
        
        # Risk from scope creep
        scope_risk = scope_analysis.risk_score if scope_analysis else 0.0
        
        # Risk from silence layer
        silence_risk = silence_state.silence_metrics.restraint_score
        
        # Trust assessment risk
        trust_risk_map = {"HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.2}
        trust_risk = trust_risk_map.get(trust_validation.risk_assessment, 0.3)
        
        # Weighted combination
        integrated_risk = (
            confidence_risk * self.config["confidence_decay_weight"] +
            scope_risk * self.config["scope_creep_weight"] +
            silence_risk * self.config["silence_layer_weight"] +
            trust_risk * self.config["trust_score_weight"]
        )
        
        return max(0.0, min(1.0, integrated_risk))
    
    def _calculate_overall_trust_adjustment(
        self,
        confidence_recommendation: Dict,
        scope_analysis: Optional[ScopeCreepAnalysis],
        silence_state: SilenceLayerState
    ) -> float:
        """Calculate overall recommended trust score adjustment"""
        
        # Start with confidence-based recommendation
        base_adjustment = (
            confidence_recommendation["recommended_trust_score"] - 
            confidence_recommendation["current_trust_score"]
        )
        
        # Adjust for scope creep impact
        if scope_analysis:
            scope_impact = scope_analysis.trust_impact
            base_adjustment += scope_impact * 0.5  # 50% weight for scope impact
        
        # Adjust for silence layer concerns
        if silence_state.silence_metrics.restraint_score > 0.3:
            restraint_impact = -silence_state.silence_metrics.restraint_score * 0.2
            base_adjustment += restraint_impact
        
        # Cap adjustment magnitude
        return max(-0.5, min(0.3, base_adjustment))
    
    def _generate_integrated_recommendations(
        self,
        trust_validation: TrustScoreValidation,
        scope_analysis: Optional[ScopeCreepAnalysis],
        silence_state: SilenceLayerState,
        integrated_risk_score: float
    ) -> List[str]:
        """Generate actionable recommendations from integrated analysis"""
        recommendations = []
        
        # High-level risk assessment
        if integrated_risk_score > 0.7:
            recommendations.append("🚨 HIGH RISK: Multiple concerning indicators detected. Immediate review recommended.")
        elif integrated_risk_score > 0.4:
            recommendations.append("⚠️ MODERATE RISK: Several issues detected. Monitor closely and consider interventions.")
        elif integrated_risk_score > 0.2:
            recommendations.append("ℹ️ LOW RISK: Minor issues detected. Continue monitoring.")
        else:
            recommendations.append("✅ NORMAL: Agent performance within acceptable parameters.")
        
        # Trust and confidence recommendations
        confidence_level = trust_validation.confidence_metrics.current_confidence
        if confidence_level < 0.5:
            recommendations.append(f"Confidence level ({confidence_level:.2f}) concerning. Increase validation frequency.")
        
        if trust_validation.risk_assessment == "HIGH":
            recommendations.append("Trust score validation indicates high risk. Consider trust score reduction.")
        
        # Scope management recommendations
        if scope_analysis:
            if scope_analysis.severity.value in ["major", "critical"]:
                recommendations.append(f"Scope creep severity: {scope_analysis.severity.value}. Immediate scope control needed.")
            
            for scope_rec in scope_analysis.recommendations[:2]:  # Take top 2
                recommendations.append(f"Scope: {scope_rec}")
        
        # Communication and restraint recommendations
        if silence_state.silence_mode.value != "active":
            recommendations.append(f"Agent in {silence_state.silence_mode.value} mode. Communication restricted.")
        
        if silence_state.human_intervention_requested:
            recommendations.append("🔴 Human intervention requested by silence layer.")
        
        # V-Token specific recommendations
        if scope_analysis and scope_analysis.scope_metrics.expansion_percentage > 0.3:
            recommendations.append("V-Token scope expanded significantly. Consider re-validation or splitting.")
        
        # Performance optimization recommendations
        if len(recommendations) > 5:  # Many issues detected
            recommendations.append("Multiple issues detected. Consider agent retraining or configuration review.")
        
        return recommendations
    
    def get_agentpier_metrics(self, agent_id: str = None) -> Dict:
        """Get comprehensive AgentPier integration metrics"""
        if agent_id:
            return self._get_agent_metrics(agent_id)
        else:
            return self._get_system_metrics()
    
    def _get_agent_metrics(self, agent_id: str) -> Dict:
        """Get metrics for specific agent"""
        if agent_id not in self.measurement_history:
            return {"agent_id": agent_id, "error": "No measurement history found"}
        
        measurements = self.measurement_history[agent_id]
        recent_measurements = measurements[-10:]  # Last 10 measurements
        
        # Calculate agent performance score
        avg_confidence = sum(m.trust_validation.confidence_metrics.current_confidence for m in recent_measurements) / len(recent_measurements)
        avg_risk_score = sum(m.integrated_risk_score for m in recent_measurements) / len(recent_measurements)
        
        agent_performance_score = (avg_confidence * 0.6) + ((1.0 - avg_risk_score) * 0.4)
        
        # Trust score accuracy
        trust_adjustments = [abs(m.overall_trust_adjustment) for m in recent_measurements]
        trust_score_accuracy = 1.0 - (sum(trust_adjustments) / len(trust_adjustments))
        
        # Scope management score
        scope_scores = []
        for m in recent_measurements:
            if m.scope_analysis:
                scope_health = 1.0 - min(1.0, m.scope_analysis.scope_metrics.expansion_percentage)
                scope_scores.append(scope_health)
        scope_management_score = sum(scope_scores) / len(scope_scores) if scope_scores else 1.0
        
        # Communication health
        comm_restrictions = sum(1 for m in recent_measurements if m.silence_state.silence_mode.value != "active")
        communication_health_score = 1.0 - (comm_restrictions / len(recent_measurements))
        
        return {
            "agent_id": agent_id,
            "measurement_count": len(measurements),
            "agent_performance_score": agent_performance_score,
            "trust_score_accuracy": trust_score_accuracy,
            "scope_management_score": scope_management_score,
            "communication_health_score": communication_health_score,
            "recent_risk_trend": [m.integrated_risk_score for m in recent_measurements[-5:]],
            "intervention_requests": sum(1 for m in measurements if m.intervention_required),
            "last_measurement": recent_measurements[-1].__dict__ if recent_measurements else None
        }
    
    def _get_system_metrics(self) -> Dict:
        """Get system-wide integration metrics"""
        all_agents = list(self.measurement_history.keys())
        total_measurements = sum(len(measurements) for measurements in self.measurement_history.values())
        
        if not all_agents:
            return {"error": "No measurement data available"}
        
        # Calculate system-wide scores
        agent_scores = []
        for agent_id in all_agents:
            agent_metrics = self._get_agent_metrics(agent_id)
            if "error" not in agent_metrics:
                agent_scores.append({
                    "performance": agent_metrics["agent_performance_score"],
                    "trust_accuracy": agent_metrics["trust_score_accuracy"],
                    "scope_management": agent_metrics["scope_management_score"],
                    "communication_health": agent_metrics["communication_health_score"]
                })
        
        if not agent_scores:
            return {"error": "No valid agent metrics available"}
        
        system_metrics = {
            "total_agents": len(all_agents),
            "total_measurements": total_measurements,
            "vtoken_validations": self.vtoken_validations,
            "trust_adjustments": self.trust_adjustments,
            "intervention_requests": self.intervention_requests,
            
            "average_performance_score": sum(s["performance"] for s in agent_scores) / len(agent_scores),
            "average_trust_accuracy": sum(s["trust_accuracy"] for s in agent_scores) / len(agent_scores),
            "average_scope_management": sum(s["scope_management"] for s in agent_scores) / len(agent_scores),
            "average_communication_health": sum(s["communication_health"] for s in agent_scores) / len(agent_scores),
            
            "framework_utilization": {
                "confidence_decay": len(self.confidence_framework.validation_history),
                "scope_creep": len(self.scope_analyzer.analysis_history),
                "silence_layer": len(self.silence_layer.agent_states)
            }
        }
        
        # Overall system health score
        system_metrics["overall_system_health"] = (
            system_metrics["average_performance_score"] * 0.4 +
            system_metrics["average_trust_accuracy"] * 0.25 +
            system_metrics["average_scope_management"] * 0.2 +
            system_metrics["average_communication_health"] * 0.15
        )
        
        return system_metrics
    
    def validate_vtoken_with_measurement(
        self,
        vtoken_id: str,
        agent_id: str,
        vtoken_data: Dict,
        context: Dict
    ) -> Dict:
        """Validate V-Token using integrated measurement frameworks"""
        
        # Extract trust score from V-Token or context
        current_trust_score = vtoken_data.get("trust_score", 0.5)
        
        # Perform integrated measurement
        measurement = self.perform_integrated_measurement(
            agent_id=agent_id,
            transaction_id=vtoken_id,
            current_trust_score=current_trust_score,
            interaction_context=context,
            vtoken_data=vtoken_data
        )
        
        # V-Token validation decision
        validation_result = {
            "vtoken_id": vtoken_id,
            "agent_id": agent_id,
            "validation_timestamp": datetime.now().isoformat(),
            "current_trust_score": current_trust_score,
            "recommended_trust_score": current_trust_score + measurement.overall_trust_adjustment,
            "validation_status": "pending",
            "confidence_level": measurement.trust_validation.confidence_metrics.current_confidence,
            "risk_assessment": measurement.integrated_risk_score,
            "scope_health": "healthy" if not measurement.scope_analysis or measurement.scope_analysis.severity.value in ["none", "minor"] else "concerning",
            "communication_status": measurement.silence_state.silence_mode.value,
            "intervention_required": measurement.intervention_required,
            "recommendations": measurement.action_recommendations
        }
        
        # Make validation decision
        if measurement.intervention_required:
            validation_result["validation_status"] = "blocked_intervention_required"
        elif measurement.integrated_risk_score > 0.7:
            validation_result["validation_status"] = "rejected_high_risk"
        elif measurement.integrated_risk_score > 0.4:
            validation_result["validation_status"] = "conditional_monitor_required"
        elif measurement.silence_state.silence_mode.value in ["minimal", "silent"]:
            validation_result["validation_status"] = "blocked_communication_restricted"
        else:
            validation_result["validation_status"] = "approved"
        
        return validation_result
    
    def export_integration_data(self) -> str:
        """Export all integration data for analysis"""
        export_data = {
            "integration_config": self.config,
            "system_metrics": self._get_system_metrics(),
            "measurement_history": {},
            "framework_states": {
                "confidence_decay": self.confidence_framework.export_metrics(),
                "scope_creep": json.loads(self.scope_analyzer.export_analysis_data()),
                "silence_layer": json.loads(self.silence_layer.export_silence_data())
            }
        }
        
        # Export measurement history (last 100 per agent)
        for agent_id, measurements in self.measurement_history.items():
            export_data["measurement_history"][agent_id] = [
                {
                    **asdict(m),
                    "timestamp": m.timestamp.isoformat(),
                    # Handle nested objects
                    "trust_validation": asdict(m.trust_validation),
                    "scope_analysis": asdict(m.scope_analysis) if m.scope_analysis else None,
                    "silence_state": asdict(m.silence_state)
                } for m in measurements[-100:]  # Last 100 measurements
            ]
        
        return json.dumps(export_data, indent=2, default=str)


def main():
    """Example usage and testing"""
    integrator = AgentPierMeasurementIntegrator()
    
    print("=== AgentPier Measurement Integration Test ===")
    
    # Mock interaction context
    interaction_context = {
        "turns_since_validation": 5,
        "interaction_history": [
            {"success_rate": 0.9, "response_time_ms": 800, "error_count": 1},
            {"success_rate": 0.85, "response_time_ms": 1200, "error_count": 0}
        ],
        "scope_data": {
            "original_scope": {
                "description": "Simple authentication",
                "requirements": ["login", "logout"],
                "features": ["basic_auth"],
                "estimated_hours": 10
            },
            "current_scope": {
                "description": "Advanced authentication with 2FA",
                "requirements": ["login", "logout", "2fa", "session_management"],
                "features": ["basic_auth", "2fa", "session_tracking"],
                "estimated_hours": 20
            }
        },
        "error_count": 2,
        "previous_trust_score": 0.8,
        "uncertainty_indicators": {
            "ambiguous_instructions": 0.3,
            "unclear_success_criteria": 0.2
        }
    }
    
    # Mock V-Token data
    vtoken_data = {
        "trust_score": 0.75,
        "transaction_type": "skill_execution",
        "complexity_level": "moderate"
    }
    
    # Perform integrated measurement
    measurement = integrator.perform_integrated_measurement(
        agent_id="test_agent_001",
        transaction_id="vtoken_12345",
        current_trust_score=0.75,
        interaction_context=interaction_context,
        vtoken_data=vtoken_data
    )
    
    print(f"Agent ID: {measurement.agent_id}")
    print(f"Integrated Risk Score: {measurement.integrated_risk_score:.2f}")
    print(f"Trust Adjustment: {measurement.overall_trust_adjustment:+.3f}")
    print(f"Intervention Required: {measurement.intervention_required}")
    print(f"Communication Mode: {measurement.silence_state.silence_mode.value}")
    
    print(f"\n=== Recommendations ===")
    for rec in measurement.action_recommendations:
        print(f"- {rec}")
    
    # Test V-Token validation
    validation_result = integrator.validate_vtoken_with_measurement(
        vtoken_id="vtoken_12345",
        agent_id="test_agent_001", 
        vtoken_data=vtoken_data,
        context=interaction_context
    )
    
    print(f"\n=== V-Token Validation ===")
    print(f"Status: {validation_result['validation_status']}")
    print(f"Trust Score: {validation_result['current_trust_score']:.2f} → {validation_result['recommended_trust_score']:.2f}")
    print(f"Risk Assessment: {validation_result['risk_assessment']:.2f}")
    
    # Get system metrics
    metrics = integrator.get_agentpier_metrics()
    print(f"\n=== System Metrics ===")
    print(f"Total Agents: {metrics['total_agents']}")
    print(f"V-Token Validations: {metrics['vtoken_validations']}")
    print(f"Overall System Health: {metrics['overall_system_health']:.2f}")


if __name__ == "__main__":
    main()