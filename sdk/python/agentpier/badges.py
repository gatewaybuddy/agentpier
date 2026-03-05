"""Badge methods for the AgentPier SDK."""

from typing import Optional, Dict, Any

from .client import AgentPierClient
from .types import Badge


class BadgeMethods:
    """Handles trust badges and verification display."""
    
    def __init__(self, client: AgentPierClient):
        self.client = client
    
    def get(self, agent_id: str) -> Badge:
        """
        Get trust badge for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Badge object with badge URL, trust level, and score
            
        Raises:
            NotFoundError: If agent not found
        """
        response = self.client.get(f"/badges/{agent_id}")
        
        return Badge(
            badge_url=response["badge_url"],
            trust_level=response["trust_level"],
            score=response["score"]
        )
    
    def get_badge_url(self, agent_id: str) -> str:
        """
        Get the badge URL for an agent (convenience method).
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Direct URL to the agent's trust badge image
            
        Raises:
            NotFoundError: If agent not found
        """
        badge = self.get(agent_id)
        return badge.badge_url
    
    def get_trust_level(self, agent_id: str) -> str:
        """
        Get the trust level for an agent (convenience method).
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Trust level string ('unverified', 'basic', 'verified', 'certified', 'elite')
            
        Raises:
            NotFoundError: If agent not found
        """
        badge = self.get(agent_id)
        return badge.trust_level
    
    def get_html_embed(self, agent_id: str, alt_text: Optional[str] = None) -> str:
        """
        Get HTML embed code for displaying the trust badge.
        
        Args:
            agent_id: Agent identifier
            alt_text: Optional alt text for the image (defaults to trust level)
        
        Returns:
            HTML string with <img> tag for the badge
            
        Raises:
            NotFoundError: If agent not found
        """
        badge = self.get(agent_id)
        
        if alt_text is None:
            alt_text = f"Trust Level: {badge.trust_level.title()}"
        
        return f'<img src="{badge.badge_url}" alt="{alt_text}" title="Trust Score: {badge.score:.1f}" />'
    
    def get_markdown_embed(self, agent_id: str, alt_text: Optional[str] = None, link_to_profile: bool = False) -> str:
        """
        Get Markdown embed code for displaying the trust badge.
        
        Args:
            agent_id: Agent identifier
            alt_text: Optional alt text for the image (defaults to trust level)
            link_to_profile: Whether to make the badge link to the agent's AgentPier profile
        
        Returns:
            Markdown string with image syntax for the badge
            
        Raises:
            NotFoundError: If agent not found
        """
        badge = self.get(agent_id)
        
        if alt_text is None:
            alt_text = f"Trust Level: {badge.trust_level.title()}"
        
        markdown = f"![{alt_text}]({badge.badge_url})"
        
        if link_to_profile:
            # Assuming AgentPier has profile URLs (this might need adjustment based on actual URLs)
            profile_url = f"https://agentpier.org/agents/{agent_id}"
            markdown = f"[{markdown}]({profile_url})"
        
        return markdown