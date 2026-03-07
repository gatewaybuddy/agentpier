"""Trust scoring methods for the AgentPier SDK."""

from typing import Optional, Dict, Any, List, Literal
from datetime import datetime

from .client import AgentPierClient
from .types import AgentTrustScore, TrustEvent, SearchResult, VTokenVerification


class TrustMethods:
    """Handles trust scoring and agent reputation management."""

    def __init__(self, client: AgentPierClient):
        self.client = client

    def register_agent(
        self, agent_name: str, description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register an agent for trust scoring.

        Args:
            agent_name: Agent identifier (lowercase alphanumeric + underscore)
            description: Optional agent description (max 500 chars)

        Returns:
            Dict with agent_id and initial trust_score

        Raises:
            ValidationError: If agent_name format is invalid
            AuthenticationError: If API key is invalid or missing
        """
        data = {"agent_name": agent_name}
        if description is not None:
            data["description"] = description

        return self.client.post("/trust/agents", data)

    def get_score(self, agent_id: str) -> AgentTrustScore:
        """
        Get comprehensive trust score and profile for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentTrustScore with complete trust information

        Raises:
            NotFoundError: If agent not found
        """
        response = self.client.get(f"/trust/agents/{agent_id}")

        # Parse datetime fields
        last_updated = None
        if response.get("last_updated"):
            last_updated = datetime.fromisoformat(
                response["last_updated"].replace("Z", "+00:00")
            )

        registered_at = None
        if response.get("registered_at"):
            registered_at = datetime.fromisoformat(
                response["registered_at"].replace("Z", "+00:00")
            )

        return AgentTrustScore(
            agent_id=response["agent_id"],
            agent_name=response["agent_name"],
            trust_score=response["trust_score"],
            trust_tier=response["trust_tier"],
            ace_scores=response.get("ace_scores"),
            last_updated=last_updated,
            event_count=response.get("event_count", 0),
            description=response.get("description"),
            capabilities=response.get("capabilities", []),
            declared_scope=response.get("declared_scope"),
            contact_url=response.get("contact_url"),
            registered_at=registered_at,
            axes=response.get("axes"),
            weights=response.get("weights"),
            history=response.get("history"),
            sources=response.get("sources"),
        )

    def search_agents(
        self,
        query: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 20,
    ) -> SearchResult:
        """
        Search for agents with trust scores.

        Args:
            query: Search query string
            min_score: Minimum trust score filter
            limit: Number of results to return (1-100, default 20)

        Returns:
            SearchResult with list of AgentTrustScore objects
        """
        params: Dict[str, Any] = {"limit": limit}
        if query is not None:
            params["q"] = query
        if min_score is not None:
            params["min_score"] = min_score

        response = self.client.get("/trust/agents", params=params)

        # Convert agents to AgentTrustScore objects
        agents = []
        for agent_data in response.get("agents", []):
            last_updated = None
            if agent_data.get("last_updated"):
                last_updated = datetime.fromisoformat(
                    agent_data["last_updated"].replace("Z", "+00:00")
                )

            agents.append(
                AgentTrustScore(
                    agent_id=agent_data["agent_id"],
                    agent_name=agent_data["agent_name"],
                    trust_score=agent_data["trust_score"],
                    trust_tier=agent_data["trust_tier"],
                    ace_scores=agent_data.get("ace_scores"),
                    last_updated=last_updated,
                    event_count=agent_data.get("event_count", 0),
                    description=agent_data.get("description"),
                    capabilities=agent_data.get("capabilities", []),
                )
            )

        return SearchResult(
            results=agents,
            total_count=response.get("total_count"),
            next_cursor=response.get("next_cursor"),
        )

    def report_event(self, agent_id: str, event: TrustEvent) -> Dict[str, Any]:
        """
        Report a trust-relevant event for an agent.

        Args:
            agent_id: Agent identifier
            event: TrustEvent object with event details

        Returns:
            Dict confirming event was recorded

        Raises:
            ValidationError: If event data is invalid
            AuthenticationError: If API key is invalid
            NotFoundError: If agent not found
        """
        data: Dict[str, Any] = {"event_type": event.event_type, "outcome": event.outcome}

        if event.details is not None:
            data["details"] = event.details
        if event.metadata is not None:
            data["metadata"] = event.metadata

        return self.client.post(f"/trust/agents/{agent_id}/events", data)

    # Convenience methods for common event types

    def report_task_completion(
        self,
        agent_id: str,
        success: bool,
        details: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Report a task completion event.

        Args:
            agent_id: Agent identifier
            success: Whether the task was successful
            details: Optional details about the task
            metadata: Optional metadata dict

        Returns:
            Dict confirming event was recorded
        """
        event = TrustEvent(
            event_type="task_completion",
            outcome="success" if success else "failure",
            details=details,
            metadata=metadata,
        )
        return self.report_event(agent_id, event)

    def report_transaction_outcome(
        self,
        agent_id: str,
        outcome: Literal['success', 'failure', 'partial', 'cancelled'],
        details: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Report a transaction outcome.

        Args:
            agent_id: Agent identifier
            outcome: 'success', 'failure', 'partial', or 'cancelled'
            details: Optional details about the transaction
            transaction_id: Optional transaction ID for reference

        Returns:
            Dict confirming event was recorded
        """
        metadata = {}
        if transaction_id:
            metadata["transaction_id"] = transaction_id

        event = TrustEvent(
            event_type="transaction",
            outcome=outcome,
            details=details,
            metadata=metadata if metadata else None,
        )
        return self.report_event(agent_id, event)

    def report_review(
        self,
        agent_id: str,
        positive: bool,
        rating: Optional[int] = None,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Report a review/rating event.

        Args:
            agent_id: Agent identifier
            positive: Whether the review was positive
            rating: Optional numerical rating (1-5)
            details: Optional review text

        Returns:
            Dict confirming event was recorded
        """
        metadata = {}
        if rating is not None:
            metadata["rating"] = rating

        event = TrustEvent(
            event_type="review",
            outcome="success" if positive else "failure",
            details=details,
            metadata=metadata if metadata else None,
        )
        return self.report_event(agent_id, event)

    def report_violation(
        self,
        agent_id: str,
        violation_type: str,
        severity: str,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Report a trust violation or safety incident.

        Args:
            agent_id: Agent identifier
            violation_type: Type of violation (e.g., 'spam', 'abuse', 'fraud')
            severity: Severity level (e.g., 'low', 'medium', 'high', 'critical')
            details: Optional details about the violation

        Returns:
            Dict confirming event was recorded
        """
        metadata = {"violation_type": violation_type, "severity": severity}

        event = TrustEvent(
            event_type="violation",
            outcome="failure",
            details=details,
            metadata=metadata,
        )
        return self.report_event(agent_id, event)

    def report_certification(
        self,
        agent_id: str,
        certification_type: str,
        passed: bool,
        details: Optional[str] = None,
        certifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Report a certification or verification event.

        Args:
            agent_id: Agent identifier
            certification_type: Type of certification (e.g., 'security_audit', 'capability_test')
            passed: Whether the certification was passed
            details: Optional details about the certification
            certifier: Optional name of the certifying entity

        Returns:
            Dict confirming event was recorded
        """
        metadata = {"certification_type": certification_type}
        if certifier:
            metadata["certifier"] = certifier

        event = TrustEvent(
            event_type="certification",
            outcome="success" if passed else "failure",
            details=details,
            metadata=metadata,
        )
        return self.report_event(agent_id, event)

    @classmethod
    def verify_vtoken(cls, token: str, base_url: str = None) -> VTokenVerification:
        """
        Verify a v-token without authentication (convenience class method).

        This allows any party to verify a v-token without needing an API key
        or an initialized client.

        Args:
            token: The v-token string to verify
            base_url: Optional API base URL (defaults to production)

        Returns:
            VTokenVerification with validity, issuer identity, and trust data
        """
        from .vtokens import VTokenMethods

        return VTokenMethods.verify(token, base_url=base_url)
