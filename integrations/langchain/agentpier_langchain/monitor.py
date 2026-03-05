"""
AgentPier Chain Monitoring for LangChain

High-level monitoring utilities for LangChain workflows.
"""

import requests
from typing import Any, Dict, List, Optional, Union
from .callbacks import AgentPierCallback


class ChainMonitor:
    """
    High-level monitor for LangChain workflows with AgentPier trust integration.
    
    Provides simple setup and management of trust monitoring for LangChain chains.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev",
        agent_mapping: Optional[Dict[str, str]] = None,
        auto_register: bool = True,
        track_chains: bool = True,
        track_tools: bool = True,
        track_llm_calls: bool = False
    ):
        """
        Initialize the monitor.
        
        Args:
            api_key: AgentPier API key
            base_url: AgentPier API base URL
            agent_mapping: Optional mapping of LangChain component names to AgentPier agent IDs
            auto_register: Whether to auto-register agents that aren't found
            track_chains: Whether to track chain execution
            track_tools: Whether to track tool usage  
            track_llm_calls: Whether to track individual LLM calls (verbose)
        """
        self.callback = AgentPierCallback(
            api_key=api_key,
            base_url=base_url,
            agent_mapping=agent_mapping,
            auto_register=auto_register,
            track_chains=track_chains,
            track_tools=track_tools,
            track_llm_calls=track_llm_calls
        )
        
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": self.api_key}
    
    def get_callback(self) -> AgentPierCallback:
        """Get the callback instance to add to LangChain chains."""
        return self.callback
    
    def verify_agent_trust(self, agent_id: str, min_score: float = 60.0) -> Dict[str, Any]:
        """
        Verify an agent meets minimum trust requirements.
        
        Args:
            agent_id: Agent identifier to check
            min_score: Minimum required trust score
            
        Returns:
            Dict with verification result
        """
        try:
            response = requests.get(
                f"{self.base_url}/trust/agents/{agent_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 404:
                return {
                    "verified": False,
                    "agent_id": agent_id,
                    "reason": "Agent not found in trust system",
                    "trust_score": None
                }
            elif response.status_code != 200:
                return {
                    "verified": False,
                    "agent_id": agent_id,
                    "reason": f"API error: {response.status_code}",
                    "trust_score": None
                }
            
            data = response.json()
            trust_score = data.get('trust_score', 0)
            
            return {
                "verified": trust_score >= min_score,
                "agent_id": agent_id,
                "agent_name": data.get('agent_name', agent_id),
                "trust_score": trust_score,
                "min_score": min_score,
                "trust_tier": data.get('trust_tier', 'unknown'),
                "reason": "Meets requirements" if trust_score >= min_score else f"Score {trust_score:.1f} below minimum {min_score}"
            }
            
        except Exception as e:
            return {
                "verified": False,
                "agent_id": agent_id,
                "reason": f"Error checking agent: {str(e)}",
                "trust_score": None
            }
    
    def verify_multiple_agents(self, agent_ids: List[str], min_score: float = 60.0) -> Dict[str, Any]:
        """
        Verify multiple agents meet trust requirements.
        
        Args:
            agent_ids: List of agent identifiers
            min_score: Minimum required trust score
            
        Returns:
            Dict with overall verification status
        """
        results = []
        all_verified = True
        
        for agent_id in agent_ids:
            if not agent_id.strip():
                continue
                
            result = self.verify_agent_trust(agent_id.strip(), min_score)
            results.append(result)
            
            if not result["verified"]:
                all_verified = False
        
        return {
            "all_verified": all_verified,
            "total_agents": len(results),
            "verified_count": sum(1 for r in results if r["verified"]),
            "failed_count": sum(1 for r in results if not r["verified"]),
            "min_score": min_score,
            "results": results
        }
    
    def create_monitored_chain(self, chain_class, *args, **kwargs):
        """
        Create a LangChain chain with automatic trust monitoring.
        
        Args:
            chain_class: LangChain chain class to instantiate
            *args, **kwargs: Arguments passed to chain constructor
            
        Returns:
            Chain instance with callback attached
        """
        # Add callback to kwargs if not already present
        if 'callbacks' not in kwargs:
            kwargs['callbacks'] = []
        elif kwargs['callbacks'] is None:
            kwargs['callbacks'] = []
        
        # Add our callback if not already present
        if self.callback not in kwargs['callbacks']:
            kwargs['callbacks'].append(self.callback)
        
        # Create and return the chain
        return chain_class(*args, **kwargs)
    
    def report_custom_event(
        self, 
        agent_id: str, 
        event_type: str = "task_completion",
        outcome: str = "success", 
        details: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Report a custom trust event.
        
        Args:
            agent_id: Agent identifier
            event_type: Type of event (task_completion, review, etc.)
            outcome: Event outcome (success, failure, partial)
            details: Optional event description
            metadata: Optional additional data
            
        Returns:
            True if event was reported successfully
        """
        return self.callback._report_trust_event(
            agent_id, event_type, outcome, details, metadata
        )
    
    def get_trust_summary(self, agent_ids: List[str]) -> Dict[str, Any]:
        """
        Get a trust summary for multiple agents.
        
        Args:
            agent_ids: List of agent identifiers
            
        Returns:
            Dict with trust summary
        """
        agent_data = []
        total_score = 0
        found_count = 0
        
        for agent_id in agent_ids:
            if not agent_id.strip():
                continue
                
            try:
                response = requests.get(
                    f"{self.base_url}/trust/agents/{agent_id}",
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    trust_score = data.get('trust_score', 0)
                    
                    agent_data.append({
                        "agent_id": agent_id,
                        "agent_name": data.get('agent_name', agent_id),
                        "trust_score": trust_score,
                        "trust_tier": data.get('trust_tier', 'unknown'),
                        "found": True
                    })
                    
                    total_score += trust_score
                    found_count += 1
                else:
                    agent_data.append({
                        "agent_id": agent_id,
                        "found": False,
                        "trust_score": None
                    })
                    
            except Exception as e:
                agent_data.append({
                    "agent_id": agent_id,
                    "found": False,
                    "error": str(e),
                    "trust_score": None
                })
        
        return {
            "total_agents": len(agent_data),
            "found_agents": found_count,
            "average_score": total_score / found_count if found_count > 0 else 0,
            "agents": agent_data
        }