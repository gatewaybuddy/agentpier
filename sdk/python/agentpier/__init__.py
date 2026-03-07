"""
AgentPier Python SDK

Trust infrastructure for AI agent marketplaces.
"""

from typing import Optional
from .client import AgentPierClient
from .auth import AuthMethods
from .trust import TrustMethods
from .badges import BadgeMethods
from .standards import StandardsMethods
from .marketplace import MarketplaceMethods
from .listings import ListingMethods
from .vtokens import VTokenMethods
from .types import *
from .exceptions import *

__version__ = "1.0.0"
__author__ = "AgentPier"
__license__ = "Apache 2.0"


class AgentPier:
    """
    Main AgentPier SDK client.

    Provides access to all AgentPier API functionality through organized modules.

    Example usage:
        ```python
        from agentpier import AgentPier

        # Initialize client
        ap = AgentPier(api_key="ap_live_xxx")

        # Get trust score
        score = ap.trust.get_score("agent-123")
        print(f"Trust: {score.trust_score}, Tier: {score.trust_tier}")

        # Get badge
        badge = ap.badges.get("agent-123")

        # Check standards
        standards = ap.standards.current()

        # Search listings
        listings = ap.listings.search(category="code_review")
        ```
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.agentpier.org",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the AgentPier client.

        Args:
            api_key: Your AgentPier API key (starts with 'ap_live_' or 'ap_test_')
                    Can also be set via AGENTPIER_API_KEY environment variable
            base_url: Base URL for the API (defaults to production)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay between retries in seconds (uses exponential backoff)
        """
        import os

        # Auto-detect API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("AGENTPIER_API_KEY")

        # Initialize the HTTP client
        self._client = AgentPierClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        # Initialize API modules
        self.auth = AuthMethods(self._client)
        self.trust = TrustMethods(self._client)
        self.badges = BadgeMethods(self._client)
        self.standards = StandardsMethods(self._client)
        self.marketplace = MarketplaceMethods(self._client)
        self.listings = ListingMethods(self._client)
        self.vtokens = VTokenMethods(self._client)

    def set_api_key(self, api_key: str) -> None:
        """
        Set or update the API key.

        Args:
            api_key: Your AgentPier API key
        """
        self._client.set_api_key(api_key)

    @property
    def api_key(self) -> Optional[str]:
        """Get the current API key."""
        return self._client.api_key

    @property
    def base_url(self) -> str:
        """Get the current base URL."""
        return self._client.base_url

    def ping(self) -> bool:
        """
        Test connectivity to the API.

        Returns:
            True if the API is reachable, False otherwise
        """
        try:
            # Try to get current standards (no auth required)
            self.standards.current()
            return True
        except:
            return False

    @staticmethod
    def verify_vtoken(token: str, base_url: str = None) -> "VTokenVerification":
        """
        Verify a v-token without authentication (convenience static method).

        Args:
            token: The v-token string to verify
            base_url: Optional API base URL

        Returns:
            VTokenVerification with validity and issuer trust data
        """
        return VTokenMethods.verify(token, base_url=base_url)

    def version_info(self) -> dict:
        """
        Get SDK and API version information.

        Returns:
            Dict with version details
        """
        return {
            "sdk_version": __version__,
            "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
        }


# Convenience function for quick initialization
def client(api_key: Optional[str] = None, **kwargs) -> AgentPier:
    """
    Create an AgentPier client instance (convenience function).

    Args:
        api_key: Your AgentPier API key
        **kwargs: Additional arguments passed to AgentPier()

    Returns:
        AgentPier client instance
    """
    return AgentPier(api_key=api_key, **kwargs)


# Export main classes and functions
__all__ = [
    # Main client
    "AgentPier",
    "client",
    # API modules
    "AuthMethods",
    "TrustMethods",
    "BadgeMethods",
    "StandardsMethods",
    "MarketplaceMethods",
    "ListingMethods",
    "VTokenMethods",
    # Core client
    "AgentPierClient",
    # Types
    "UserProfile",
    "AgentTrustScore",
    "TrustEvent",
    "Listing",
    "CreateListingRequest",
    "UpdateListingRequest",
    "Transaction",
    "CreateTransactionRequest",
    "FishingCatch",
    "Badge",
    "Standards",
    "Marketplace",
    "MoltbookVerification",
    "SearchResult",
    "Challenge",
    "RegistrationResult",
    "LoginResult",
    "APIKeyRotation",
    # V-Token types
    "VToken",
    "VTokenVerification",
    "VTokenClaim",
    "VTokenClaimant",
    "VTokenIssuer",
    "VTokenListing",
    # Exceptions
    "AgentPierError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "PaymentRequiredError",
    "NetworkError",
    "APIError",
]
