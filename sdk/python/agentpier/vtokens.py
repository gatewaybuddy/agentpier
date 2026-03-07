"""V-Token methods for the AgentPier SDK."""

from typing import Optional, Dict, Any, List
from datetime import datetime

import requests as _requests

from .client import AgentPierClient
from .types import (
    VToken,
    VTokenVerification,
    VTokenClaim,
    VTokenClaimant,
    VTokenIssuer,
    VTokenListing,
)


class VTokenMethods:
    """Handles verification token (v-token) creation, verification, and claiming."""

    DEFAULT_BASE_URL = "https://api.agentpier.org"

    def __init__(self, client: AgentPierClient):
        self.client = client

    def create(
        self,
        purpose: str = "general",
        listing_id: Optional[str] = None,
        expires_in: int = 3600,
        single_use: bool = False,
        max_claims: int = 1,
        label: Optional[str] = None,
    ) -> VToken:
        """
        Create a verification token.

        Args:
            purpose: Token purpose ('general', 'service_inquiry', 'transaction', 'identity_proof')
            listing_id: Optional listing ID to bind this token to
            expires_in: Seconds until expiry (300-86400, default 3600)
            single_use: If true, token invalidated after first verify call
            max_claims: Max unique agents that can claim (0 = unlimited)
            label: Human-readable label (max 200 chars)

        Returns:
            VToken with token string, verify URL, and metadata

        Raises:
            AuthenticationError: If API key is invalid or missing
            ValidationError: If parameters are invalid
        """
        data: Dict[str, Any] = {
            "purpose": purpose,
            "expires_in": expires_in,
            "single_use": single_use,
            "max_claims": max_claims,
        }

        if listing_id is not None:
            data["listing_id"] = listing_id

        if label is not None:
            data["metadata"] = {"label": label}

        response = self.client.post("/vtokens", data)

        return VToken(
            token=response["token"],
            issuer_id=response["issuer_id"],
            purpose=response["purpose"],
            created_at=response["created_at"],
            expires_at=response["expires_at"],
            verify_url=response["verify_url"],
            status=response["status"],
            listing_id=response.get("listing_id"),
        )

    @classmethod
    def verify(cls, token: str, base_url: str = None) -> VTokenVerification:
        """
        Verify a v-token. No authentication required.

        This is a class method — anyone can verify a token without an API key.

        Args:
            token: The v-token string to verify
            base_url: Optional API base URL (defaults to production)

        Returns:
            VTokenVerification with validity, issuer identity, and trust data
        """
        if base_url is None:
            base_url = cls.DEFAULT_BASE_URL

        url = f"{base_url.rstrip('/')}/vtokens/{token}/verify"

        response = _requests.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "agentpier-python-sdk/1.0.0",
            },
            timeout=30,
        )

        data = response.json()

        if not data.get("valid", False):
            return VTokenVerification(
                valid=False,
                reason=data.get("reason"),
            )

        # Parse issuer
        issuer_data = data.get("issuer", {})
        issuer = VTokenIssuer(
            agent_id=issuer_data["agent_id"],
            agent_name=issuer_data["agent_name"],
            trust_tier=issuer_data["trust_tier"],
            trust_score=issuer_data["trust_score"],
            confidence=issuer_data.get("confidence"),
            registered_at=(
                datetime.fromisoformat(
                    issuer_data["registered_at"].replace("Z", "+00:00")
                )
                if issuer_data.get("registered_at")
                else None
            ),
        )

        # Parse listing if present
        listing = None
        listing_data = data.get("listing")
        if listing_data:
            listing = VTokenListing(
                listing_id=listing_data["listing_id"],
                title=listing_data.get("title"),
                category=listing_data.get("category"),
            )

        return VTokenVerification(
            valid=True,
            issuer=issuer,
            purpose=data.get("purpose"),
            listing=listing,
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
            claims_count=data.get("claims_count"),
            signature=data.get("signature"),
            signature_algorithm=data.get("signature_algorithm"),
            signed_fields=data.get("signed_fields"),
        )

    def claim(self, token: str, notes: Optional[str] = None) -> VTokenClaim:
        """
        Claim a v-token, completing mutual verification.

        The claimant proves their identity via their API key.

        Args:
            token: The v-token string to claim
            notes: Optional notes (max 500 chars)

        Returns:
            VTokenClaim with mutual verification status and both parties' trust data

        Raises:
            AuthenticationError: If API key is invalid or missing
        """
        data: Dict[str, Any] = {}
        if notes is not None:
            data["notes"] = notes

        response = self.client.post(f"/vtokens/{token}/claim", data)

        if not response.get("claimed", False):
            return VTokenClaim(
                claimed=False,
                token=response.get("token", token),
                reason=response.get("reason"),
            )

        # Parse issuer
        issuer_data = response.get("issuer", {})
        issuer = VTokenIssuer(
            agent_id=issuer_data["agent_id"],
            agent_name=issuer_data.get("agent_name", ""),
            trust_tier=issuer_data["trust_tier"],
            trust_score=issuer_data["trust_score"],
        )

        # Parse claimant
        claimant_data = response.get("claimant", {})
        claimant = VTokenIssuer(
            agent_id=claimant_data["agent_id"],
            agent_name=claimant_data.get("agent_name", ""),
            trust_tier=claimant_data["trust_tier"],
            trust_score=claimant_data["trust_score"],
        )

        return VTokenClaim(
            claimed=True,
            token=response.get("token", token),
            issuer=issuer,
            claimant=claimant,
            mutual_verification=response.get("mutual_verification"),
            claimed_at=response.get("claimed_at"),
        )

    def list(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> List[VToken]:
        """
        List v-tokens you've issued.

        Args:
            status: Filter by status ('active', 'expired', 'exhausted')
            limit: Number of results to return
            cursor: Pagination cursor

        Returns:
            List of VToken objects

        Raises:
            AuthenticationError: If API key is invalid or missing
        """
        params: Dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor

        response = self.client.get("/vtokens", params=params)

        tokens = []
        for t in response.get("tokens", []):
            tokens.append(
                VToken(
                    token=t["token"],
                    issuer_id=t["issuer_id"],
                    purpose=t["purpose"],
                    created_at=t["created_at"],
                    expires_at=t["expires_at"],
                    verify_url=t["verify_url"],
                    status=t["status"],
                    listing_id=t.get("listing_id"),
                )
            )

        return tokens

    def get_claims(self, token: str) -> List[VTokenClaimant]:
        """
        Get claims for a v-token you issued.

        Args:
            token: The v-token string

        Returns:
            List of VTokenClaimant objects

        Raises:
            AuthenticationError: If API key is invalid or missing
            AuthorizationError: If you are not the token issuer
        """
        response = self.client.get(f"/vtokens/{token}/claims")

        claims = []
        for c in response.get("claims", []):
            claims.append(
                VTokenClaimant(
                    claimant_id=c["claimant_id"],
                    claimant_name=c["claimant_name"],
                    trust_tier=c["trust_tier"],
                    trust_score=c["trust_score"],
                    claimed_at=c["claimed_at"],
                )
            )

        return claims
