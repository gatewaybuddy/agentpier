#!/usr/bin/env python3
"""
Confidence Decay Framework for AgentPier Trust Scoring
Based on Hazel_OC's confidence decay framework with 4.7-turn half-life

This module implements confidence decay patterns for trust score validation
and V-Token accuracy metrics, adapting agent community measurement trends.
"""

import math
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class ConfidenceLevel(Enum):
    """Trust confidence levels matching AgentPier trust tiers"""
    VERY_HIGH = "very_high"      # 90-100%
    HIGH = "high"                # 75-89%
    MODERATE = "moderate"        # 50-74%
    LOW = "low"                  # 25-49%
    VERY_LOW = "very_low"        # 0-24%


@dataclass
class ConfidenceDecayMetrics:
    """Metrics for confidence decay analysis"""
    initial_confidence: float
    current_confidence: float
    decay_rate: float
    turns_elapsed: int
    half_life_turns: float
    time_since_last_update: float
    decay_acceleration: float
    stability_score: float


@dataclass
class TrustScoreValidation:
    """Trust score validation using confidence decay"""
    agent_id: str
    trust_score: float
    confidence_metrics: ConfidenceDecayMetrics
    validation_timestamp: datetime
    last_interaction_turns: int
    reputation_stability: float
    risk_assessment: str


class ConfidenceDecayFramework:
    """
    Implements confidence decay patterns for AgentPier trust validation
    
    Based on agent community research showing 4.7-turn half-life for
    confidence decay in agent interactions and self-measurement patterns.
    """
    
    def __init__(self, base_half_life: float = 4.7):
        self.base_half_life = base_half_life
        self.decay_constant = math.log(2) / base_half_life
        self.validation_history: Dict[str, List[TrustScoreValidation]] = {}
        self.confidence_thresholds = {
            ConfidenceLevel.VERY_HIGH: 0.90,
            ConfidenceLevel.HIGH: 0.75,
            ConfidenceLevel.MODERATE: 0.50,
            ConfidenceLevel.LOW: 0.25,
            ConfidenceLevel.VERY_LOW: 0.0
        }
    
    def calculate_confidence_decay(
        self, 
        initial_confidence: float, 
        turns_elapsed: int,
        interaction_quality: float = 1.0,
        reputation_modifier: float = 1.0
    ) -> ConfidenceDecayMetrics:
        """
        Calculate confidence decay using exponential decay model
        
        Args:
            initial_confidence: Starting confidence level (0.0-1.0)
            turns_elapsed: Number of turns/interactions since last validation
            interaction_quality: Quality multiplier for interactions (0.5-1.5)
            reputation_modifier: Reputation-based modifier (0.8-1.2)
        
        Returns:
            ConfidenceDecayMetrics with current state and analysis
        """
        # Adjust decay rate based on interaction quality and reputation
        adjusted_decay_constant = self.decay_constant * (2.0 - interaction_quality) * (2.0 - reputation_modifier)
        
        # Calculate current confidence using exponential decay
        current_confidence = initial_confidence * math.exp(-adjusted_decay_constant * turns_elapsed)
        
        # Calculate effective half-life with adjustments
        effective_half_life = math.log(2) / adjusted_decay_constant if adjusted_decay_constant > 0 else float('inf')
        
        # Calculate decay acceleration (second derivative indicator)
        decay_acceleration = adjusted_decay_constant ** 2 * current_confidence
        
        # Calculate stability score (resistance to decay)
        stability_score = min(1.0, interaction_quality * reputation_modifier)
        
        return ConfidenceDecayMetrics(
            initial_confidence=initial_confidence,
            current_confidence=current_confidence,
            decay_rate=adjusted_decay_constant,
            turns_elapsed=turns_elapsed,
            half_life_turns=effective_half_life,
            time_since_last_update=turns_elapsed,
            decay_acceleration=decay_acceleration,
            stability_score=stability_score
        )
    
    def validate_trust_score(
        self,
        agent_id: str,
        trust_score: float,
        turns_since_last_validation: int,
        interaction_history: List[Dict] = None
    ) -> TrustScoreValidation:
        """
        Validate trust score using confidence decay analysis
        
        Args:
            agent_id: Unique identifier for agent
            trust_score: Current trust score from AgentPier
            turns_since_last_validation: Interactions since last validation
            interaction_history: Recent interaction data
        
        Returns:
            TrustScoreValidation with decay analysis and recommendations
        """
        # Get historical confidence or start with trust score
        if agent_id in self.validation_history and self.validation_history[agent_id]:
            last_validation = self.validation_history[agent_id][-1]
            initial_confidence = last_validation.confidence_metrics.current_confidence
        else:
            initial_confidence = trust_score
        
        # Analyze interaction quality if history provided
        interaction_quality = 1.0
        if interaction_history:
            interaction_quality = self._analyze_interaction_quality(interaction_history)
        
        # Calculate reputation stability from trust score
        reputation_modifier = min(1.2, 0.8 + (trust_score * 0.4))
        
        # Generate confidence decay metrics
        confidence_metrics = self.calculate_confidence_decay(
            initial_confidence,
            turns_since_last_validation,
            interaction_quality,
            reputation_modifier
        )
        
        # Calculate reputation stability
        reputation_stability = self._calculate_reputation_stability(agent_id)
        
        # Assess risk level
        risk_assessment = self._assess_risk_level(confidence_metrics, trust_score)
        
        # Create validation record
        validation = TrustScoreValidation(
            agent_id=agent_id,
            trust_score=trust_score,
            confidence_metrics=confidence_metrics,
            validation_timestamp=datetime.now(),
            last_interaction_turns=turns_since_last_validation,
            reputation_stability=reputation_stability,
            risk_assessment=risk_assessment
        )
        
        # Store validation history
        if agent_id not in self.validation_history:
            self.validation_history[agent_id] = []
        self.validation_history[agent_id].append(validation)
        
        # Keep only last 50 validations per agent
        self.validation_history[agent_id] = self.validation_history[agent_id][-50:]
        
        return validation
    
    def _analyze_interaction_quality(self, interaction_history: List[Dict]) -> float:
        """Analyze interaction quality from history"""
        if not interaction_history:
            return 1.0
        
        quality_scores = []
        for interaction in interaction_history[-10:]:  # Last 10 interactions
            # Extract quality indicators
            success_rate = interaction.get('success_rate', 1.0)
            response_time = interaction.get('response_time_ms', 1000)
            error_count = interaction.get('error_count', 0)
            
            # Calculate interaction quality (0.5-1.5 range)
            quality = success_rate * min(1.5, 2000 / max(response_time, 500)) * max(0.5, 1.0 - (error_count * 0.1))
            quality_scores.append(max(0.5, min(1.5, quality)))
        
        return sum(quality_scores) / len(quality_scores) if quality_scores else 1.0
    
    def _calculate_reputation_stability(self, agent_id: str) -> float:
        """Calculate reputation stability from validation history"""
        if agent_id not in self.validation_history or len(self.validation_history[agent_id]) < 2:
            return 0.5  # Neutral stability for new agents
        
        recent_validations = self.validation_history[agent_id][-10:]
        trust_scores = [v.trust_score for v in recent_validations]
        
        # Calculate variance in trust scores
        mean_trust = sum(trust_scores) / len(trust_scores)
        variance = sum((score - mean_trust) ** 2 for score in trust_scores) / len(trust_scores)
        
        # Convert variance to stability (lower variance = higher stability)
        stability = max(0.0, min(1.0, 1.0 - (variance * 10)))
        return stability
    
    def _assess_risk_level(self, confidence_metrics: ConfidenceDecayMetrics, trust_score: float) -> str:
        """Assess risk level based on confidence decay and trust score"""
        confidence = confidence_metrics.current_confidence
        decay_rate = confidence_metrics.decay_rate
        
        # High risk conditions
        if confidence < 0.3 or decay_rate > 0.5 or trust_score < 0.4:
            return "HIGH"
        
        # Medium risk conditions
        if confidence < 0.6 or decay_rate > 0.2 or trust_score < 0.6:
            return "MEDIUM"
        
        # Low risk (stable confidence and trust)
        return "LOW"
    
    def get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Get confidence level enum from numeric confidence"""
        for level, threshold in sorted(self.confidence_thresholds.items(), 
                                     key=lambda x: x[1], reverse=True):
            if confidence >= threshold:
                return level
        return ConfidenceLevel.VERY_LOW
    
    def generate_trust_adjustment_recommendation(self, validation: TrustScoreValidation) -> Dict:
        """Generate recommendation for trust score adjustment"""
        confidence = validation.confidence_metrics.current_confidence
        current_trust = validation.trust_score
        risk = validation.risk_assessment
        
        # Calculate recommended adjustment
        confidence_gap = abs(confidence - current_trust)
        
        if risk == "HIGH":
            # Significant adjustment needed
            adjustment_factor = -0.2 if confidence < current_trust else 0.1
        elif risk == "MEDIUM":
            # Moderate adjustment
            adjustment_factor = -0.1 if confidence < current_trust else 0.05
        else:
            # Minor adjustment or maintenance
            adjustment_factor = confidence_gap * 0.1
        
        recommended_trust = max(0.0, min(1.0, current_trust + adjustment_factor))
        
        return {
            "current_trust_score": current_trust,
            "recommended_trust_score": recommended_trust,
            "adjustment_magnitude": abs(adjustment_factor),
            "adjustment_direction": "increase" if adjustment_factor > 0 else "decrease",
            "confidence_level": self.get_confidence_level(confidence).value,
            "risk_assessment": risk,
            "reasoning": self._generate_adjustment_reasoning(validation, adjustment_factor)
        }
    
    def _generate_adjustment_reasoning(self, validation: TrustScoreValidation, adjustment: float) -> str:
        """Generate human-readable reasoning for trust adjustment"""
        confidence = validation.confidence_metrics.current_confidence
        trust = validation.trust_score
        turns = validation.last_interaction_turns
        
        if abs(adjustment) < 0.01:
            return f"Trust score stable. Confidence ({confidence:.2f}) closely matches trust ({trust:.2f}) after {turns} interactions."
        
        if adjustment < 0:
            return f"Confidence decay detected. After {turns} interactions, confidence ({confidence:.2f}) has fallen below trust score ({trust:.2f}). Recommend lowering trust to match validated confidence."
        else:
            return f"Agent performance exceeding expectations. Confidence ({confidence:.2f}) supports higher trust than current score ({trust:.2f}). Consider trust score increase."
    
    def export_metrics(self, agent_id: str = None) -> Dict:
        """Export confidence decay metrics for analysis"""
        if agent_id:
            if agent_id in self.validation_history:
                return {
                    "agent_id": agent_id,
                    "validation_count": len(self.validation_history[agent_id]),
                    "latest_validation": self.validation_history[agent_id][-1].__dict__ if self.validation_history[agent_id] else None,
                    "average_confidence": sum(v.confidence_metrics.current_confidence for v in self.validation_history[agent_id]) / len(self.validation_history[agent_id]) if self.validation_history[agent_id] else 0
                }
            return {"agent_id": agent_id, "error": "No validation history found"}
        
        # Export all agents
        return {
            "total_agents": len(self.validation_history),
            "total_validations": sum(len(history) for history in self.validation_history.values()),
            "framework_config": {
                "base_half_life": self.base_half_life,
                "decay_constant": self.decay_constant
            },
            "agents": list(self.validation_history.keys())
        }


def main():
    """Example usage and testing"""
    framework = ConfidenceDecayFramework()
    
    # Test confidence decay calculation
    print("=== Confidence Decay Framework Test ===")
    
    # Simulate agent validation
    agent_id = "test-agent-001"
    trust_score = 0.85
    turns_since_validation = 5
    
    # Mock interaction history
    interaction_history = [
        {"success_rate": 0.95, "response_time_ms": 800, "error_count": 0},
        {"success_rate": 0.90, "response_time_ms": 1200, "error_count": 1},
        {"success_rate": 1.00, "response_time_ms": 600, "error_count": 0},
    ]
    
    # Validate trust score
    validation = framework.validate_trust_score(
        agent_id, trust_score, turns_since_validation, interaction_history
    )
    
    print(f"Agent ID: {validation.agent_id}")
    print(f"Trust Score: {validation.trust_score:.3f}")
    print(f"Current Confidence: {validation.confidence_metrics.current_confidence:.3f}")
    print(f"Decay Rate: {validation.confidence_metrics.decay_rate:.3f}")
    print(f"Half-life: {validation.confidence_metrics.half_life_turns:.1f} turns")
    print(f"Risk Assessment: {validation.risk_assessment}")
    
    # Generate recommendation
    recommendation = framework.generate_trust_adjustment_recommendation(validation)
    print(f"\n=== Trust Adjustment Recommendation ===")
    print(f"Current: {recommendation['current_trust_score']:.3f}")
    print(f"Recommended: {recommendation['recommended_trust_score']:.3f}")
    print(f"Direction: {recommendation['adjustment_direction']}")
    print(f"Reasoning: {recommendation['reasoning']}")
    
    # Export metrics
    metrics = framework.export_metrics()
    print(f"\n=== Framework Metrics ===")
    print(f"Total agents tracked: {metrics['total_agents']}")
    print(f"Total validations: {metrics['total_validations']}")


if __name__ == "__main__":
    main()