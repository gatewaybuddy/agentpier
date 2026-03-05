"""Standards and certification methods for the AgentPier SDK."""

from typing import Dict, Any

from .client import AgentPierClient
from .types import Standards


class StandardsMethods:
    """Handles certification standards and compliance."""
    
    def __init__(self, client: AgentPierClient):
        self.client = client
    
    def current(self) -> Standards:
        """
        Get current certification standards.
        
        Returns:
            Standards object with version, effective date, and standards structure
        """
        response = self.client.get("/standards/current")
        
        return Standards(
            version=response["version"],
            effective_date=response["effective_date"],
            standards=response["standards"]
        )
    
    def get_version(self) -> str:
        """
        Get the current standards version (convenience method).
        
        Returns:
            Version string of current standards
        """
        standards = self.current()
        return standards.version
    
    def has_agent_standards(self) -> bool:
        """
        Check if agent standards are available (convenience method).
        
        Returns:
            True if agent standards are defined
        """
        standards = self.current()
        return "agent" in standards.standards
    
    def get_compliance_info(self) -> Dict[str, Any]:
        """
        Get detailed compliance information.
        
        Returns:
            Dict with standards details and structure information
        """
        standards = self.current()
        agent_available = "agent" in standards.standards
        marketplace_available = "marketplace" in standards.standards
        
        return {
            "version": standards.version,
            "effective_date": standards.effective_date,
            "agent_standards_available": agent_available,
            "marketplace_standards_available": marketplace_available,
            "is_current": True,  # Since we're fetching current standards
            "standards": standards.standards,
            "summary": f"Standards v{standards.version} (Agent: {'✓' if agent_available else '✗'}, Marketplace: {'✓' if marketplace_available else '✗'})"
        }