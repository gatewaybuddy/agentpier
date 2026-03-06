"""
CrewAI Callbacks for AgentPier Trust Reporting

Callbacks that automatically report task completion/failure as trust signals to AgentPier.
"""

from typing import Any, Dict, Optional
from datetime import datetime
from agentpier import AgentPier
from agentpier.types import TrustEvent
from agentpier.exceptions import AgentPierError, NotFoundError


class AgentPierTaskCallback:
    """
    CrewAI callback that automatically reports task outcomes to AgentPier trust system.

    This callback monitors task execution and reports success/failure events
    which contribute to agents' trust scores over time.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.agentpier.org",
        agent_mapping: Optional[Dict[str, str]] = None,
        auto_register: bool = True,
    ):
        """
        Initialize the callback.

        Args:
            api_key: AgentPier API key
            base_url: AgentPier API base URL (defaults to production)
            agent_mapping: Optional mapping of CrewAI agent names to AgentPier agent IDs
            auto_register: Whether to auto-register agents that aren't found
        """
        self.agent_pier = AgentPier(api_key=api_key, base_url=base_url)
        self.agent_mapping = agent_mapping or {}
        self.auto_register = auto_register
        self._registered_agents = set()

    def _get_agent_id(self, agent_name: str) -> str:
        """Get AgentPier agent ID for a CrewAI agent name."""
        # Check explicit mapping first
        if agent_name in self.agent_mapping:
            return self.agent_mapping[agent_name]

        # Use agent name as ID by default (common pattern)
        return agent_name.lower().replace(" ", "_")

    def _register_agent_if_needed(self, agent_id: str, agent_name: str) -> bool:
        """Register agent in AgentPier if not already registered."""
        if not self.auto_register or agent_id in self._registered_agents:
            return True

        try:
            # Check if agent already exists
            try:
                self.agent_pier.trust.get_score(agent_id)
                # Agent exists
                self._registered_agents.add(agent_id)
                return True
            except NotFoundError:
                # Agent doesn't exist, register it
                description = f"CrewAI agent '{agent_name}' auto-registered via AgentPier integration"
                self.agent_pier.trust.register_agent(agent_id, description)
                self._registered_agents.add(agent_id)
                return True

        except AgentPierError as e:
            print(f"Error registering agent {agent_id}: {str(e)}")
            return False

    def _report_trust_event(
        self,
        agent_id: str,
        event_type: str,
        outcome: str,
        details: str = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """Report a trust event to AgentPier."""
        try:
            event = TrustEvent(
                event_type=event_type,
                outcome=outcome,
                details=details or f"CrewAI task {outcome}",
                metadata=metadata or {},
            )

            self.agent_pier.trust.report_event(agent_id, event)
            return True

        except AgentPierError as e:
            print(f"Error reporting trust event for {agent_id}: {str(e)}")
            return False

    def on_task_start(self, task: Any, agent: Any, **kwargs) -> None:
        """Called when a task starts."""
        agent_name = getattr(agent, "role", str(agent))
        agent_id = self._get_agent_id(agent_name)

        # Ensure agent is registered
        self._register_agent_if_needed(agent_id, agent_name)

        # Optional: Report task start (commented out to avoid noise)
        # self._report_trust_event(
        #     agent_id,
        #     "task_completion",
        #     "partial",
        #     f"Started task: {getattr(task, 'description', 'Unknown task')}",
        #     {"task_type": "crewai_task", "status": "started"}
        # )

    def on_task_complete(
        self, task: Any, agent: Any, result: Any = None, **kwargs
    ) -> None:
        """Called when a task completes successfully."""
        agent_name = getattr(agent, "role", str(agent))
        agent_id = self._get_agent_id(agent_name)

        # Determine if task was successful based on result
        outcome = "success"
        details = f"Completed CrewAI task successfully"

        if hasattr(task, "description"):
            details += f": {task.description[:100]}"

        metadata = {
            "task_type": "crewai_task",
            "completion_time": datetime.utcnow().isoformat(),
            "has_result": result is not None,
        }

        if result and hasattr(result, "__len__"):
            metadata["result_length"] = len(str(result))

        self._report_trust_event(
            agent_id, "task_completion", outcome, details, metadata
        )

    def on_task_fail(
        self, task: Any, agent: Any, error: Exception = None, **kwargs
    ) -> None:
        """Called when a task fails."""
        agent_name = getattr(agent, "role", str(agent))
        agent_id = self._get_agent_id(agent_name)

        outcome = "failure"
        details = f"CrewAI task failed"

        if error:
            details += f": {str(error)[:200]}"
        elif hasattr(task, "description"):
            details += f": {task.description[:100]}"

        metadata = {
            "task_type": "crewai_task",
            "failure_time": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__ if error else "unknown",
        }

        if error:
            metadata["error_message"] = str(error)[:500]

        self._report_trust_event(
            agent_id, "task_completion", outcome, details, metadata
        )

    def on_agent_action(
        self, agent: Any, action: str, result: Any = None, **kwargs
    ) -> None:
        """Called when an agent takes an action (optional monitoring)."""
        # This could be used for more granular trust reporting
        # Currently not implemented to avoid noise
        pass

    def on_crew_complete(self, crew: Any, result: Any = None, **kwargs) -> None:
        """Called when entire crew workflow completes."""
        # Could be used for collaborative trust scoring
        # Currently not implemented
        pass
