"""
LangChain Callbacks for AgentPier Trust Reporting

Callbacks that report chain/agent runs as trust signals to AgentPier.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from uuid import UUID
from agentpier import AgentPier
from agentpier.types import TrustEvent
from agentpier.exceptions import AgentPierError, NotFoundError

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
    from langchain_core.messages import BaseMessage
    from langchain_core.documents import Document
except ImportError:
    # Fallback for older LangChain versions
    from langchain.callbacks.base import BaseCallbackHandler
    from langchain.schema import LLMResult, BaseMessage, Document


class AgentPierCallback(BaseCallbackHandler):
    """
    LangChain callback that reports chain/agent execution to AgentPier trust system.

    This callback monitors various LangChain events and converts them into trust signals
    that contribute to agent reputation scores.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.agentpier.org",
        agent_mapping: Optional[Dict[str, str]] = None,
        auto_register: bool = True,
        track_chains: bool = True,
        track_tools: bool = True,
        track_llm_calls: bool = False,  # Usually too verbose
    ):
        """
        Initialize the callback.

        Args:
            api_key: AgentPier API key
            base_url: AgentPier API base URL (defaults to production)
            agent_mapping: Optional mapping of LangChain agent names to AgentPier agent IDs
            auto_register: Whether to auto-register agents that aren't found
            track_chains: Whether to track chain execution
            track_tools: Whether to track tool usage
            track_llm_calls: Whether to track individual LLM calls (verbose)
        """
        super().__init__()
        self.agent_pier = AgentPier(api_key=api_key, base_url=base_url)
        self.agent_mapping = agent_mapping or {}
        self.auto_register = auto_register
        self.track_chains = track_chains
        self.track_tools = track_tools
        self.track_llm_calls = track_llm_calls

        self._registered_agents = set()
        self._active_runs = {}  # Track active chains/tools for completion reporting

    def _get_agent_id(self, name: str) -> str:
        """Get AgentPier agent ID from LangChain component name."""
        # Check explicit mapping first
        if name in self.agent_mapping:
            return self.agent_mapping[name]

        # Clean up name to create agent ID
        agent_id = name.lower().replace(" ", "_").replace("-", "_")

        # Remove common LangChain prefixes/suffixes
        agent_id = (
            agent_id.replace("chain", "").replace("agent", "").replace("tool", "")
        )
        agent_id = agent_id.strip("_")

        return agent_id or "langchain_agent"

    def _register_agent_if_needed(self, agent_id: str, description: str = None) -> bool:
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
                register_description = (
                    description
                    or f"LangChain agent '{agent_id}' auto-registered via AgentPier integration"
                )
                self.agent_pier.trust.register_agent(agent_id, register_description)
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
                details=details or f"LangChain {event_type} {outcome}",
                metadata=metadata or {},
            )

            self.agent_pier.trust.report_event(agent_id, event)
            return True

        except AgentPierError as e:
            print(f"Error reporting trust event for {agent_id}: {str(e)}")
            return False

    # Chain callbacks
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain starts running."""
        if not self.track_chains:
            return

        chain_name = serialized.get("name", "unknown_chain")
        agent_id = self._get_agent_id(chain_name)

        # Register agent if needed
        self._register_agent_if_needed(agent_id, f"LangChain chain: {chain_name}")

        # Track the run
        self._active_runs[str(run_id)] = {
            "agent_id": agent_id,
            "type": "chain",
            "name": chain_name,
            "start_time": datetime.utcnow(),
            "inputs": inputs,
        }

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain ends successfully."""
        if not self.track_chains:
            return

        run_info = self._active_runs.get(str(run_id))
        if not run_info:
            return

        agent_id = run_info["agent_id"]
        duration = (datetime.utcnow() - run_info["start_time"]).total_seconds()

        details = f"LangChain chain '{run_info['name']}' completed successfully"
        metadata = {
            "chain_type": "langchain_chain",
            "duration_seconds": duration,
            "has_outputs": bool(outputs),
            "input_keys": list(run_info["inputs"].keys()) if run_info["inputs"] else [],
        }

        if outputs:
            metadata["output_keys"] = list(outputs.keys())
            metadata["output_length"] = len(str(outputs))

        self._report_trust_event(
            agent_id, "task_completion", "success", details, metadata
        )

        # Clean up
        del self._active_runs[str(run_id)]

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain encounters an error."""
        if not self.track_chains:
            return

        run_info = self._active_runs.get(str(run_id))
        if not run_info:
            return

        agent_id = run_info["agent_id"]
        duration = (datetime.utcnow() - run_info["start_time"]).total_seconds()

        details = f"LangChain chain '{run_info['name']}' failed: {str(error)[:200]}"
        metadata = {
            "chain_type": "langchain_chain",
            "duration_seconds": duration,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
        }

        self._report_trust_event(
            agent_id, "task_completion", "failure", details, metadata
        )

        # Clean up
        del self._active_runs[str(run_id)]

    # Tool callbacks
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts running."""
        if not self.track_tools:
            return

        tool_name = serialized.get("name", "unknown_tool")
        agent_id = self._get_agent_id(tool_name)

        # Register agent if needed
        self._register_agent_if_needed(agent_id, f"LangChain tool: {tool_name}")

        # Track the run
        self._active_runs[str(run_id)] = {
            "agent_id": agent_id,
            "type": "tool",
            "name": tool_name,
            "start_time": datetime.utcnow(),
            "input": input_str,
        }

    def on_tool_end(
        self,
        output: str,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool ends successfully."""
        if not self.track_tools:
            return

        run_info = self._active_runs.get(str(run_id))
        if not run_info:
            return

        agent_id = run_info["agent_id"]
        duration = (datetime.utcnow() - run_info["start_time"]).total_seconds()

        details = f"LangChain tool '{run_info['name']}' executed successfully"
        metadata = {
            "tool_type": "langchain_tool",
            "duration_seconds": duration,
            "input_length": len(run_info["input"]) if run_info["input"] else 0,
            "output_length": len(output) if output else 0,
        }

        self._report_trust_event(
            agent_id, "task_completion", "success", details, metadata
        )

        # Clean up
        del self._active_runs[str(run_id)]

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool encounters an error."""
        if not self.track_tools:
            return

        run_info = self._active_runs.get(str(run_id))
        if not run_info:
            return

        agent_id = run_info["agent_id"]
        duration = (datetime.utcnow() - run_info["start_time"]).total_seconds()

        details = f"LangChain tool '{run_info['name']}' failed: {str(error)[:200]}"
        metadata = {
            "tool_type": "langchain_tool",
            "duration_seconds": duration,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "input_length": len(run_info["input"]) if run_info["input"] else 0,
        }

        self._report_trust_event(
            agent_id, "task_completion", "failure", details, metadata
        )

        # Clean up
        del self._active_runs[str(run_id)]

    # LLM callbacks (optional, usually verbose)
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts running."""
        if not self.track_llm_calls:
            return

        # LLM tracking implementation would go here
        # Usually disabled to avoid noise
        pass

    def on_llm_end(
        self,
        response: LLMResult,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM ends successfully."""
        if not self.track_llm_calls:
            return

        # LLM tracking implementation would go here
        # Usually disabled to avoid noise
        pass

    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM encounters an error."""
        if not self.track_llm_calls:
            return

        # LLM error tracking implementation would go here
        # Usually disabled to avoid noise
        pass
