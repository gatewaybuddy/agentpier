"""Marketplace methods for the AgentPier SDK."""

from typing import Optional, Dict, Any
from datetime import datetime

from .client import AgentPierClient
from .types import Marketplace


class MarketplaceMethods:
    """Handles marketplace platform management."""

    def __init__(self, client: AgentPierClient):
        self.client = client

    def register(
        self, name: str, description: str, website: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new marketplace platform.

        Args:
            name: Marketplace name (max 100 chars)
            description: Marketplace description (max 500 chars)
            website: Optional website URL

        Returns:
            Dict with marketplace_id and api_key for the new marketplace

        Raises:
            ValidationError: If name/description validation fails
            AuthenticationError: If API key is invalid
        """
        data = {"name": name, "description": description}

        if website is not None:
            data["website"] = website

        return self.client.post("/marketplace/register", data)

    def get(self, marketplace_id: str) -> Marketplace:
        """
        Get marketplace details.

        Args:
            marketplace_id: Marketplace identifier

        Returns:
            Marketplace object with platform details

        Raises:
            NotFoundError: If marketplace not found
        """
        response = self.client.get(f"/marketplace/{marketplace_id}")

        # Parse datetime field
        created_at = None
        if response.get("created_at"):
            created_at = datetime.fromisoformat(
                response["created_at"].replace("Z", "+00:00")
            )

        return Marketplace(
            marketplace_id=response["marketplace_id"],
            name=response["name"],
            description=response["description"],
            website=response.get("website"),
            trust_score=response.get("trust_score"),
            agent_count=response.get("agent_count"),
            created_at=created_at,
        )

    def get_stats(self, marketplace_id: str) -> Dict[str, Any]:
        """
        Get marketplace statistics.

        Args:
            marketplace_id: Marketplace identifier

        Returns:
            Dict with marketplace statistics

        Raises:
            NotFoundError: If marketplace not found
        """
        marketplace = self.get(marketplace_id)
        return {
            "marketplace_id": marketplace.marketplace_id,
            "name": marketplace.name,
            "trust_score": marketplace.trust_score,
            "agent_count": marketplace.agent_count,
            "created_at": (
                marketplace.created_at.isoformat() if marketplace.created_at else None
            ),
        }
