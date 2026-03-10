#!/usr/bin/env python3
"""
Scope Creep Analysis Framework for V-Token Transaction Validation
Based on agent community research showing 38% task expansion patterns

This module detects and analyzes scope creep in V-Token transactions,
helping validate transaction accuracy and prevent trust erosion.
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import re


class ScopeCreepSeverity(Enum):
    """Scope creep severity levels"""
    NONE = "none"           # 0-5% expansion
    MINOR = "minor"         # 5-15% expansion  
    MODERATE = "moderate"   # 15-30% expansion
    MAJOR = "major"         # 30-50% expansion
    CRITICAL = "critical"   # >50% expansion


class ExpansionType(Enum):
    """Types of scope expansion detected"""
    FEATURE_ADDITION = "feature_addition"
    COMPLEXITY_GROWTH = "complexity_growth"
    REQUIREMENT_CHANGE = "requirement_change"
    DEPENDENCY_EXPANSION = "dependency_expansion"
    TIMELINE_EXTENSION = "timeline_extension"
    RESOURCE_ESCALATION = "resource_escalation"


@dataclass
class ScopeMetrics:
    """Scope analysis metrics"""
    original_scope_size: float
    current_scope_size: float
    expansion_percentage: float
    expansion_rate: float
    complexity_factor: float
    requirement_drift: float
    feature_count_delta: int
    timeline_drift_factor: float


@dataclass
class ExpansionEvent:
    """Individual scope expansion event"""
    event_id: str
    timestamp: datetime
    expansion_type: ExpansionType
    magnitude: float
    description: str
    trigger_source: str
    impact_assessment: str


@dataclass 
class ScopeCreepAnalysis:
    """Complete scope creep analysis for a V-Token transaction"""
    transaction_id: str
    agent_id: str
    original_scope_hash: str
    current_scope_hash: str
    scope_metrics: ScopeMetrics
    expansion_events: List[ExpansionEvent]
    severity: ScopeCreepSeverity
    risk_score: float
    trust_impact: float
    analysis_timestamp: datetime
    recommendations: List[str]


class ScopeCreepAnalyzer:
    """
    Analyzes scope creep patterns in V-Token transactions
    
    Implements detection algorithms based on agent community research
    showing 38% average task expansion and scope creep indicators.
    """
    
    def __init__(self, baseline_expansion_threshold: float = 0.38):
        self.baseline_expansion_threshold = baseline_expansion_threshold
        self.analysis_history: Dict[str, List[ScopeCreepAnalysis]] = {}
        self.scope_tracking: Dict[str, Dict] = {}
        
        # Scope creep detection patterns
        self.expansion_indicators = {
            "additional": {"weight": 0.3, "pattern": r"\b(also|additional|furthermore|moreover|plus)\b"},
            "scope_words": {"weight": 0.4, "pattern": r"\b(expand|extend|add|include|enhance|improve)\b"},
            "complexity": {"weight": 0.5, "pattern": r"\b(complex|sophisticated|advanced|comprehensive)\b"},
            "requirements": {"weight": 0.3, "pattern": r"\b(requirement|specification|criteria|constraint)\b"},
            "timeline": {"weight": 0.2, "pattern": r"\b(deadline|timeline|schedule|duration|time)\b"},
            "features": {"weight": 0.4, "pattern": r"\b(feature|functionality|capability|option|setting)\b"}
        }
        
        # Severity thresholds
        self.severity_thresholds = {
            ScopeCreepSeverity.NONE: 0.05,
            ScopeCreepSeverity.MINOR: 0.15,
            ScopeCreepSeverity.MODERATE: 0.30,
            ScopeCreepSeverity.MAJOR: 0.50,
            ScopeCreepSeverity.CRITICAL: float('inf')
        }
    
    def analyze_scope_change(
        self,
        transaction_id: str,
        agent_id: str,
        original_scope: Dict,
        current_scope: Dict,
        interaction_history: List[Dict] = None
    ) -> ScopeCreepAnalysis:
        """
        Analyze scope creep between original and current transaction scope
        
        Args:
            transaction_id: Unique transaction identifier
            agent_id: Agent performing the transaction
            original_scope: Original scope definition
            current_scope: Current scope state
            interaction_history: History of scope modifications
        
        Returns:
            ScopeCreepAnalysis with complete scope creep assessment
        """
        # Generate scope hashes for comparison
        original_hash = self._generate_scope_hash(original_scope)
        current_hash = self._generate_scope_hash(current_scope)
        
        # Calculate scope metrics
        scope_metrics = self._calculate_scope_metrics(original_scope, current_scope)
        
        # Detect expansion events
        expansion_events = self._detect_expansion_events(
            original_scope, current_scope, interaction_history or []
        )
        
        # Determine severity
        severity = self._determine_severity(scope_metrics.expansion_percentage)
        
        # Calculate risk score and trust impact
        risk_score = self._calculate_risk_score(scope_metrics, expansion_events)
        trust_impact = self._calculate_trust_impact(severity, risk_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(scope_metrics, expansion_events, severity)
        
        # Create analysis
        analysis = ScopeCreepAnalysis(
            transaction_id=transaction_id,
            agent_id=agent_id,
            original_scope_hash=original_hash,
            current_scope_hash=current_hash,
            scope_metrics=scope_metrics,
            expansion_events=expansion_events,
            severity=severity,
            risk_score=risk_score,
            trust_impact=trust_impact,
            analysis_timestamp=datetime.now(),
            recommendations=recommendations
        )
        
        # Store analysis history
        if transaction_id not in self.analysis_history:
            self.analysis_history[transaction_id] = []
        self.analysis_history[transaction_id].append(analysis)
        
        return analysis
    
    def _generate_scope_hash(self, scope: Dict) -> str:
        """Generate consistent hash for scope comparison"""
        # Normalize and sort scope data
        normalized = json.dumps(scope, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _calculate_scope_metrics(self, original: Dict, current: Dict) -> ScopeMetrics:
        """Calculate comprehensive scope change metrics"""
        # Calculate scope sizes using multiple dimensions
        orig_size = self._calculate_scope_size(original)
        curr_size = self._calculate_scope_size(current)
        
        # Calculate expansion percentage
        expansion_pct = (curr_size - orig_size) / orig_size if orig_size > 0 else 0
        
        # Calculate expansion rate (scope growth velocity)
        time_factor = self._get_time_factor(original, current)
        expansion_rate = expansion_pct / max(time_factor, 1.0)
        
        # Calculate complexity factor
        complexity_factor = self._calculate_complexity_factor(original, current)
        
        # Calculate requirement drift
        requirement_drift = self._calculate_requirement_drift(original, current)
        
        # Count feature changes
        feature_delta = self._count_feature_changes(original, current)
        
        # Calculate timeline drift
        timeline_drift = self._calculate_timeline_drift(original, current)
        
        return ScopeMetrics(
            original_scope_size=orig_size,
            current_scope_size=curr_size,
            expansion_percentage=expansion_pct,
            expansion_rate=expansion_rate,
            complexity_factor=complexity_factor,
            requirement_drift=requirement_drift,
            feature_count_delta=feature_delta,
            timeline_drift_factor=timeline_drift
        )
    
    def _calculate_scope_size(self, scope: Dict) -> float:
        """Calculate normalized scope size using multiple indicators"""
        size_indicators = {
            "requirements": len(scope.get("requirements", [])),
            "features": len(scope.get("features", [])),
            "constraints": len(scope.get("constraints", [])),
            "deliverables": len(scope.get("deliverables", [])),
            "acceptance_criteria": len(scope.get("acceptance_criteria", [])),
            "dependencies": len(scope.get("dependencies", [])),
        }
        
        # Text-based indicators
        text_fields = ["description", "specifications", "details"]
        for field in text_fields:
            if field in scope and isinstance(scope[field], str):
                # Count words as size indicator
                size_indicators[f"{field}_words"] = len(scope[field].split())
        
        # Weighted sum of indicators
        weights = {
            "requirements": 0.3,
            "features": 0.25,
            "constraints": 0.15,
            "deliverables": 0.15,
            "acceptance_criteria": 0.1,
            "dependencies": 0.05
        }
        
        total_size = 0.0
        for indicator, count in size_indicators.items():
            base_indicator = indicator.split('_')[0]  # Remove '_words' suffix
            weight = weights.get(base_indicator, 0.01)
            total_size += count * weight
        
        return max(1.0, total_size)  # Minimum size of 1.0
    
    def _get_time_factor(self, original: Dict, current: Dict) -> float:
        """Calculate time factor for scope changes"""
        orig_time = original.get("created_timestamp") or original.get("timestamp")
        curr_time = current.get("updated_timestamp") or current.get("timestamp")
        
        if not orig_time or not curr_time:
            return 1.0
        
        # Handle both string and datetime formats
        if isinstance(orig_time, str):
            orig_time = datetime.fromisoformat(orig_time.replace('Z', '+00:00'))
        if isinstance(curr_time, str):
            curr_time = datetime.fromisoformat(curr_time.replace('Z', '+00:00'))
        
        time_diff = (curr_time - orig_time).total_seconds() / 3600  # Hours
        return max(1.0, time_diff)  # Minimum 1 hour
    
    def _calculate_complexity_factor(self, original: Dict, current: Dict) -> float:
        """Calculate complexity increase factor"""
        orig_complexity = self._assess_complexity(original)
        curr_complexity = self._assess_complexity(current)
        
        if orig_complexity == 0:
            return 1.0 if curr_complexity == 0 else 2.0
        
        return curr_complexity / orig_complexity
    
    def _assess_complexity(self, scope: Dict) -> float:
        """Assess scope complexity using various indicators"""
        complexity_score = 0.0
        
        # Count complex indicators
        text_content = json.dumps(scope).lower()
        
        for indicator, config in self.expansion_indicators.items():
            matches = len(re.findall(config["pattern"], text_content))
            complexity_score += matches * config["weight"]
        
        # Additional complexity factors
        nested_depth = self._calculate_nesting_depth(scope)
        complexity_score += nested_depth * 0.1
        
        # Dependencies complexity
        deps = scope.get("dependencies", [])
        complexity_score += len(deps) * 0.2
        
        return max(1.0, complexity_score)
    
    def _calculate_nesting_depth(self, obj, current_depth=0) -> int:
        """Calculate maximum nesting depth of scope object"""
        if not isinstance(obj, (dict, list)):
            return current_depth
        
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_nesting_depth(v, current_depth + 1) for v in obj.values())
        
        if isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_nesting_depth(item, current_depth + 1) for item in obj)
        
        return current_depth
    
    def _calculate_requirement_drift(self, original: Dict, current: Dict) -> float:
        """Calculate how much requirements have drifted"""
        orig_reqs = set(original.get("requirements", []))
        curr_reqs = set(current.get("requirements", []))
        
        if not orig_reqs:
            return 1.0 if curr_reqs else 0.0
        
        # Calculate Jaccard distance as drift measure
        intersection = len(orig_reqs.intersection(curr_reqs))
        union = len(orig_reqs.union(curr_reqs))
        
        if union == 0:
            return 0.0
        
        jaccard_similarity = intersection / union
        return 1.0 - jaccard_similarity  # Convert to drift (1 = complete drift)
    
    def _count_feature_changes(self, original: Dict, current: Dict) -> int:
        """Count net feature additions"""
        orig_features = set(original.get("features", []))
        curr_features = set(current.get("features", []))
        
        added = curr_features - orig_features
        removed = orig_features - curr_features
        
        return len(added) - len(removed)  # Net feature change
    
    def _calculate_timeline_drift(self, original: Dict, current: Dict) -> float:
        """Calculate timeline expansion factor"""
        orig_timeline = original.get("estimated_hours") or original.get("timeline_hours", 1.0)
        curr_timeline = current.get("estimated_hours") or current.get("timeline_hours", 1.0)
        
        if orig_timeline <= 0:
            return 1.0
        
        return curr_timeline / orig_timeline
    
    def _detect_expansion_events(
        self, 
        original: Dict, 
        current: Dict, 
        history: List[Dict]
    ) -> List[ExpansionEvent]:
        """Detect individual expansion events from interaction history"""
        events = []
        
        # Analyze direct scope changes
        if self._has_feature_additions(original, current):
            events.append(ExpansionEvent(
                event_id=f"feature_add_{int(time.time())}",
                timestamp=datetime.now(),
                expansion_type=ExpansionType.FEATURE_ADDITION,
                magnitude=self._calculate_feature_expansion_magnitude(original, current),
                description="New features added to scope",
                trigger_source="scope_comparison",
                impact_assessment="Medium"
            ))
        
        if self._has_complexity_growth(original, current):
            events.append(ExpansionEvent(
                event_id=f"complexity_growth_{int(time.time())}",
                timestamp=datetime.now(),
                expansion_type=ExpansionType.COMPLEXITY_GROWTH,
                magnitude=self._calculate_complexity_factor(original, current) - 1.0,
                description="Increased scope complexity detected",
                trigger_source="complexity_analysis",
                impact_assessment="High"
            ))
        
        if self._has_requirement_changes(original, current):
            events.append(ExpansionEvent(
                event_id=f"req_change_{int(time.time())}",
                timestamp=datetime.now(),
                expansion_type=ExpansionType.REQUIREMENT_CHANGE,
                magnitude=self._calculate_requirement_drift(original, current),
                description="Requirements have been modified",
                trigger_source="requirement_analysis",
                impact_assessment="Medium"
            ))
        
        # Analyze interaction history for additional events
        for i, interaction in enumerate(history):
            event = self._analyze_interaction_for_expansion(interaction, i)
            if event:
                events.append(event)
        
        return events
    
    def _has_feature_additions(self, original: Dict, current: Dict) -> bool:
        """Check if features have been added"""
        orig_features = set(original.get("features", []))
        curr_features = set(current.get("features", []))
        return len(curr_features - orig_features) > 0
    
    def _has_complexity_growth(self, original: Dict, current: Dict) -> bool:
        """Check if complexity has grown significantly"""
        complexity_factor = self._calculate_complexity_factor(original, current)
        return complexity_factor > 1.2  # 20% complexity increase threshold
    
    def _has_requirement_changes(self, original: Dict, current: Dict) -> bool:
        """Check if requirements have changed"""
        drift = self._calculate_requirement_drift(original, current)
        return drift > 0.1  # 10% drift threshold
    
    def _calculate_feature_expansion_magnitude(self, original: Dict, current: Dict) -> float:
        """Calculate magnitude of feature expansion"""
        orig_count = len(original.get("features", []))
        curr_count = len(current.get("features", []))
        
        if orig_count == 0:
            return 1.0 if curr_count > 0 else 0.0
        
        return (curr_count - orig_count) / orig_count
    
    def _analyze_interaction_for_expansion(self, interaction: Dict, index: int) -> Optional[ExpansionEvent]:
        """Analyze single interaction for expansion indicators"""
        text_content = str(interaction).lower()
        
        # Check for expansion trigger words
        expansion_score = 0.0
        detected_type = ExpansionType.COMPLEXITY_GROWTH
        
        for indicator, config in self.expansion_indicators.items():
            matches = len(re.findall(config["pattern"], text_content))
            if matches > 0:
                expansion_score += matches * config["weight"]
                
                # Determine most likely expansion type
                if indicator in ["additional", "features"]:
                    detected_type = ExpansionType.FEATURE_ADDITION
                elif indicator == "requirements":
                    detected_type = ExpansionType.REQUIREMENT_CHANGE
                elif indicator == "timeline":
                    detected_type = ExpansionType.TIMELINE_EXTENSION
        
        # Threshold for expansion detection
        if expansion_score > 0.5:
            return ExpansionEvent(
                event_id=f"interaction_{index}_{int(time.time())}",
                timestamp=datetime.now(),
                expansion_type=detected_type,
                magnitude=min(1.0, expansion_score),
                description=f"Expansion indicators found in interaction {index}",
                trigger_source="interaction_analysis",
                impact_assessment="Low" if expansion_score < 1.0 else "Medium"
            )
        
        return None
    
    def _determine_severity(self, expansion_percentage: float) -> ScopeCreepSeverity:
        """Determine scope creep severity from expansion percentage"""
        for severity, threshold in self.severity_thresholds.items():
            if expansion_percentage <= threshold:
                return severity
        return ScopeCreepSeverity.CRITICAL
    
    def _calculate_risk_score(self, metrics: ScopeMetrics, events: List[ExpansionEvent]) -> float:
        """Calculate overall risk score (0.0-1.0)"""
        # Base risk from expansion percentage
        expansion_risk = min(1.0, metrics.expansion_percentage / self.baseline_expansion_threshold)
        
        # Risk from expansion rate (velocity)
        rate_risk = min(1.0, metrics.expansion_rate * 2.0)
        
        # Risk from complexity growth
        complexity_risk = min(1.0, (metrics.complexity_factor - 1.0) * 2.0)
        
        # Risk from number of expansion events
        event_risk = min(1.0, len(events) / 5.0)  # Risk increases with more events
        
        # Combined risk score with weights
        total_risk = (
            expansion_risk * 0.4 +
            rate_risk * 0.2 + 
            complexity_risk * 0.2 +
            event_risk * 0.2
        )
        
        return max(0.0, min(1.0, total_risk))
    
    def _calculate_trust_impact(self, severity: ScopeCreepSeverity, risk_score: float) -> float:
        """Calculate impact on trust score (-1.0 to 0.0)"""
        # Base trust impact by severity
        severity_impact = {
            ScopeCreepSeverity.NONE: 0.0,
            ScopeCreepSeverity.MINOR: -0.05,
            ScopeCreepSeverity.MODERATE: -0.15,
            ScopeCreepSeverity.MAJOR: -0.30,
            ScopeCreepSeverity.CRITICAL: -0.50
        }
        
        base_impact = severity_impact.get(severity, -0.1)
        
        # Adjust by risk score
        adjusted_impact = base_impact * (0.5 + risk_score * 0.5)
        
        return max(-1.0, adjusted_impact)
    
    def _generate_recommendations(
        self, 
        metrics: ScopeMetrics, 
        events: List[ExpansionEvent], 
        severity: ScopeCreepSeverity
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if severity == ScopeCreepSeverity.NONE:
            recommendations.append("Scope is well-controlled. Continue current practices.")
            return recommendations
        
        # General recommendations based on severity
        if severity in [ScopeCreepSeverity.MODERATE, ScopeCreepSeverity.MAJOR, ScopeCreepSeverity.CRITICAL]:
            recommendations.append("Implement scope freeze to prevent further expansion")
            recommendations.append("Conduct formal scope review with stakeholders")
        
        # Specific recommendations based on metrics
        if metrics.expansion_percentage > 0.3:
            recommendations.append(f"Scope has expanded {metrics.expansion_percentage:.1%}. Consider breaking into multiple transactions.")
        
        if metrics.complexity_factor > 1.5:
            recommendations.append("High complexity growth detected. Simplify requirements where possible.")
        
        if metrics.requirement_drift > 0.3:
            recommendations.append("Significant requirement drift detected. Clarify and document requirements.")
        
        if metrics.timeline_drift_factor > 1.3:
            recommendations.append("Timeline has extended significantly. Re-evaluate resource allocation.")
        
        # Event-based recommendations
        feature_events = [e for e in events if e.expansion_type == ExpansionType.FEATURE_ADDITION]
        if len(feature_events) > 2:
            recommendations.append("Multiple feature additions detected. Consider feature prioritization.")
        
        dependency_events = [e for e in events if e.expansion_type == ExpansionType.DEPENDENCY_EXPANSION]
        if dependency_events:
            recommendations.append("Dependency expansion detected. Review external dependencies for necessity.")
        
        # Risk mitigation
        if severity == ScopeCreepSeverity.CRITICAL:
            recommendations.append("CRITICAL: Consider cancelling and re-scoping transaction to prevent trust erosion.")
            recommendations.append("Implement immediate controls and escalate to management.")
        
        return recommendations
    
    def get_agent_scope_profile(self, agent_id: str) -> Dict:
        """Get scope creep profile for specific agent"""
        agent_analyses = []
        
        for transaction_analyses in self.analysis_history.values():
            agent_analyses.extend([a for a in transaction_analyses if a.agent_id == agent_id])
        
        if not agent_analyses:
            return {"agent_id": agent_id, "error": "No scope analyses found"}
        
        # Calculate agent scope creep statistics
        avg_expansion = sum(a.scope_metrics.expansion_percentage for a in agent_analyses) / len(agent_analyses)
        avg_risk = sum(a.risk_score for a in agent_analyses) / len(agent_analyses)
        
        severity_counts = {}
        for analysis in agent_analyses:
            severity = analysis.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "agent_id": agent_id,
            "total_transactions": len(agent_analyses),
            "average_expansion_pct": avg_expansion,
            "average_risk_score": avg_risk,
            "severity_distribution": severity_counts,
            "latest_analysis": agent_analyses[-1].__dict__ if agent_analyses else None
        }
    
    def export_analysis_data(self, format: str = "json") -> str:
        """Export analysis data for external processing"""
        export_data = {
            "framework_config": {
                "baseline_expansion_threshold": self.baseline_expansion_threshold,
                "analysis_timestamp": datetime.now().isoformat(),
                "total_transactions": len(self.analysis_history)
            },
            "analyses": {}
        }
        
        # Convert analyses to serializable format
        for transaction_id, analyses in self.analysis_history.items():
            export_data["analyses"][transaction_id] = [
                {
                    **asdict(analysis),
                    "analysis_timestamp": analysis.analysis_timestamp.isoformat(),
                    "expansion_events": [
                        {
                            **asdict(event),
                            "timestamp": event.timestamp.isoformat(),
                            "expansion_type": event.expansion_type.value
                        } for event in analysis.expansion_events
                    ],
                    "severity": analysis.severity.value
                } for analysis in analyses
            ]
        
        if format.lower() == "json":
            return json.dumps(export_data, indent=2)
        else:
            return str(export_data)


def main():
    """Example usage and testing"""
    analyzer = ScopeCreepAnalyzer()
    
    print("=== Scope Creep Analysis Framework Test ===")
    
    # Mock original scope
    original_scope = {
        "transaction_id": "vtoken_001",
        "description": "Build simple user authentication system",
        "requirements": [
            "User registration",
            "Login/logout functionality", 
            "Password reset"
        ],
        "features": ["basic auth", "email verification"],
        "constraints": ["Use existing database", "Complete in 2 weeks"],
        "estimated_hours": 40,
        "created_timestamp": "2024-01-01T10:00:00Z"
    }
    
    # Mock current scope (expanded)
    current_scope = {
        "transaction_id": "vtoken_001", 
        "description": "Build comprehensive user authentication and authorization system with advanced security features",
        "requirements": [
            "User registration",
            "Login/logout functionality",
            "Password reset", 
            "Two-factor authentication",
            "Role-based access control",
            "Session management",
            "Audit logging"
        ],
        "features": [
            "basic auth", "email verification", 
            "2FA", "RBAC", "session tracking",
            "security monitoring", "compliance reporting"
        ],
        "constraints": ["Use existing database", "Complete in 4 weeks", "GDPR compliance"],
        "estimated_hours": 80,
        "updated_timestamp": "2024-01-01T14:00:00Z"
    }
    
    # Mock interaction history
    interaction_history = [
        {"type": "clarification", "content": "Also need to add two-factor authentication"},
        {"type": "requirement", "content": "Additionally, we need role-based access control"},
        {"type": "feature", "content": "Can we also include audit logging functionality?"}
    ]
    
    # Perform scope creep analysis
    analysis = analyzer.analyze_scope_change(
        transaction_id="vtoken_001",
        agent_id="test_agent",
        original_scope=original_scope,
        current_scope=current_scope,
        interaction_history=interaction_history
    )
    
    print(f"Transaction ID: {analysis.transaction_id}")
    print(f"Expansion Percentage: {analysis.scope_metrics.expansion_percentage:.1%}")
    print(f"Severity: {analysis.severity.value}")
    print(f"Risk Score: {analysis.risk_score:.2f}")
    print(f"Trust Impact: {analysis.trust_impact:.2f}")
    print(f"Expansion Events: {len(analysis.expansion_events)}")
    
    print(f"\n=== Recommendations ===")
    for rec in analysis.recommendations:
        print(f"- {rec}")
    
    # Test agent profile
    profile = analyzer.get_agent_scope_profile("test_agent")
    print(f"\n=== Agent Profile ===")
    print(f"Average Expansion: {profile.get('average_expansion_pct', 0):.1%}")
    print(f"Average Risk: {profile.get('average_risk_score', 0):.2f}")


if __name__ == "__main__":
    main()