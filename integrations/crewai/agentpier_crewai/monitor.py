"""
AgentPier Monitoring for CrewAI

High-level classes for monitoring CrewAI workflows and verifying trust levels.
"""

import requests
from typing import List, Any, Dict, Optional
from .callbacks import AgentPierTaskCallback


class AgentPierMonitor:
    """
    High-level monitor for CrewAI workflows with AgentPier trust integration.
    
    Provides simple callback methods for common CrewAI events and automatic
    trust score reporting.
    """
    
    def __init__(
        self, 
        api_key: str, 
        base_url: str = "https://api.agentpier.org",
        agent_mapping: Optional[Dict[str, str]] = None,
        auto_register: bool = True
    ):
        """
        Initialize the monitor.
        
        Args:
            api_key: AgentPier API key
            base_url: AgentPier API base URL  
            agent_mapping: Optional mapping of CrewAI agent names to AgentPier agent IDs
            auto_register: Whether to auto-register agents that aren't found
        """
        self.callback = AgentPierTaskCallback(
            api_key=api_key,
            base_url=base_url,
            agent_mapping=agent_mapping,
            auto_register=auto_register
        )
    
    def on_task_complete(self, task: Any, agent: Any, result: Any = None, **kwargs) -> None:
        """Callback for successful task completion."""
        self.callback.on_task_complete(task, agent, result, **kwargs)
    
    def on_task_fail(self, task: Any, agent: Any, error: Exception = None, **kwargs) -> None:
        """Callback for task failure."""
        self.callback.on_task_fail(task, agent, error, **kwargs)
    
    def on_task_start(self, task: Any, agent: Any, **kwargs) -> None:
        """Callback for task start."""
        self.callback.on_task_start(task, agent, **kwargs)


class TrustVerifier:
    """
    Verifies agent trust levels before CrewAI workflow execution.
    
    Use this to check that all agents in a crew meet minimum trust requirements
    before starting work.
    """
    
    def __init__(
        self, 
        api_key: str, 
        min_score: float = 60.0,
        base_url: str = "https://api.agentpier.org"
    ):
        """
        Initialize the verifier.
        
        Args:
            api_key: AgentPier API key
            min_score: Minimum trust score required (0-100)
            base_url: AgentPier API base URL
        """
        self.api_key = api_key
        self.min_score = min_score
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": self.api_key}
    
    def check_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Check trust score for a single agent.
        
        Args:
            agent_id: Agent identifier to check
            
        Returns:
            Dict with trust information and verification status
        """
        try:
            response = requests.get(
                f"{self.base_url}/trust/agents/{agent_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 404:
                return {
                    "agent_id": agent_id,
                    "found": False,
                    "verified": False,
                    "reason": "Agent not found in trust system"
                }
            elif response.status_code != 200:
                return {
                    "agent_id": agent_id,
                    "found": False,
                    "verified": False,
                    "reason": f"API error: {response.status_code}"
                }
            
            data = response.json()
            trust_score = data.get('trust_score', 0)
            
            return {
                "agent_id": agent_id,
                "agent_name": data.get('agent_name', agent_id),
                "found": True,
                "verified": trust_score >= self.min_score,
                "trust_score": trust_score,
                "trust_tier": data.get('trust_tier', 'unknown'),
                "min_required": self.min_score,
                "reason": "Meets minimum trust score" if trust_score >= self.min_score else f"Score {trust_score:.1f} below minimum {self.min_score}"
            }
            
        except Exception as e:
            return {
                "agent_id": agent_id,
                "found": False,
                "verified": False,
                "reason": f"Error checking agent: {str(e)}"
            }
    
    def check_agents(self, agent_ids: List[str]) -> Dict[str, Any]:
        """
        Check trust scores for multiple agents.
        
        Args:
            agent_ids: List of agent identifiers to check
            
        Returns:
            Dict with overall verification status and individual results
        """
        results = []
        all_verified = True
        
        for agent_id in agent_ids:
            if not agent_id.strip():
                continue
                
            result = self.check_agent(agent_id.strip())
            results.append(result)
            
            if not result["verified"]:
                all_verified = False
        
        return {
            "all_verified": all_verified,
            "total_agents": len(results),
            "verified_count": sum(1 for r in results if r["verified"]),
            "failed_count": sum(1 for r in results if not r["verified"]),
            "min_score": self.min_score,
            "results": results
        }
    
    def check_crew(self, crew: Any) -> Dict[str, Any]:
        """
        Check trust levels for all agents in a CrewAI crew.
        
        Args:
            crew: CrewAI Crew object
            
        Returns:
            Dict with verification status for the entire crew
        """
        # Extract agent identifiers from crew
        agent_ids = []
        
        if hasattr(crew, 'agents'):
            for agent in crew.agents:
                # Try to get agent ID/name from various attributes
                agent_id = None
                
                if hasattr(agent, 'role'):
                    agent_id = agent.role
                elif hasattr(agent, 'name'):
                    agent_id = agent.name
                elif hasattr(agent, 'id'):
                    agent_id = agent.id
                else:
                    agent_id = str(agent)
                
                # Clean up agent ID
                if agent_id:
                    agent_id = agent_id.lower().replace(" ", "_")
                    agent_ids.append(agent_id)
        
        if not agent_ids:
            return {
                "all_verified": False,
                "total_agents": 0,
                "verified_count": 0,
                "failed_count": 0,
                "min_score": self.min_score,
                "results": [],
                "error": "No agents found in crew"
            }
        
        return self.check_agents(agent_ids)
    
    def check_all(self, crew_or_agents) -> bool:
        """
        Simple boolean check - returns True if all agents are verified.
        
        Args:
            crew_or_agents: Either a CrewAI Crew object or list of agent IDs
            
        Returns:
            True if all agents meet minimum trust requirements
        """
        if hasattr(crew_or_agents, 'agents'):
            # It's a crew
            result = self.check_crew(crew_or_agents)
        elif isinstance(crew_or_agents, list):
            # It's a list of agent IDs
            result = self.check_agents(crew_or_agents)
        else:
            return False
        
        return result.get("all_verified", False)