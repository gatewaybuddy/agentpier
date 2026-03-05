"""Standards and certification methods for the AgentPier SDK."""

from typing import Dict, Any
from datetime import datetime

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
            Standards object with version, compliance info, and last update
        """
        response = self.client.get("/standards/current")
        
        # Parse datetime field
        last_updated = None
        if response.get("last_updated"):
            last_updated = datetime.fromisoformat(response["last_updated"].replace('Z', '+00:00'))
        
        return Standards(
            version=response["version"],
            apts_compliance=response["apts_compliance"],
            last_updated=last_updated or datetime.utcnow()
        )
    
    def get_version(self) -> str:
        """
        Get the current standards version (convenience method).
        
        Returns:
            Version string of current standards
        """
        standards = self.current()
        return standards.version
    
    def is_apts_compliant(self) -> bool:
        """
        Check if current standards are APTS compliant (convenience method).
        
        Returns:
            True if current standards are APTS compliant
        """
        standards = self.current()
        return standards.apts_compliance
    
    def get_compliance_info(self) -> Dict[str, Any]:
        """
        Get detailed compliance information.
        
        Returns:
            Dict with compliance details and standards information
        """
        standards = self.current()
        return {
            "version": standards.version,
            "apts_compliant": standards.apts_compliance,
            "last_updated": standards.last_updated.isoformat(),
            "is_current": True,  # Since we're fetching current standards
            "summary": f"Standards v{standards.version} ({'APTS compliant' if standards.apts_compliance else 'Not APTS compliant'})"
        }