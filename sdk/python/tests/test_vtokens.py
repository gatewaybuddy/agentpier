"""Tests for v-token functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from agentpier import (
    AgentPier,
    AgentPierClient,
    VToken,
    VTokenVerification,
    VTokenClaim,
    VTokenClaimant,
    VTokenIssuer,
    VTokenListing,
)
from agentpier.vtokens import VTokenMethods
from agentpier.trust import TrustMethods


class TestVTokenMethods:
    """Test v-token creation, listing, and claims."""

    @patch.object(AgentPierClient, "post")
    def test_create_vtoken(self, mock_post):
        """Test creating a v-token."""
        mock_post.return_value = {
            "token": "vt_abc123",
            "issuer_id": "usr_seller123",
            "purpose": "transaction",
            "listing_id": "lst_abc123",
            "created_at": "2026-03-06T20:00:00Z",
            "expires_at": "2026-03-06T21:00:00Z",
            "verify_url": "https://api.agentpier.org/vtokens/vt_abc123/verify",
            "status": "active",
        }

        ap = AgentPier(api_key="ap_test_123")
        token = ap.vtokens.create(
            purpose="transaction",
            listing_id="lst_abc123",
            expires_in=3600,
            max_claims=1,
            label="Code review",
        )

        assert isinstance(token, VToken)
        assert token.token == "vt_abc123"
        assert token.issuer_id == "usr_seller123"
        assert token.purpose == "transaction"
        assert token.listing_id == "lst_abc123"
        assert token.status == "active"
        assert "verify" in token.verify_url

        # Verify correct request body
        call_args = mock_post.call_args
        assert call_args[0][0] == "/vtokens"
        body = call_args[0][1]
        assert body["purpose"] == "transaction"
        assert body["listing_id"] == "lst_abc123"
        assert body["expires_in"] == 3600
        assert body["max_claims"] == 1
        assert body["metadata"] == {"label": "Code review"}

    @patch.object(AgentPierClient, "post")
    def test_create_vtoken_defaults(self, mock_post):
        """Test creating a v-token with default parameters."""
        mock_post.return_value = {
            "token": "vt_def456",
            "issuer_id": "usr_seller123",
            "purpose": "general",
            "created_at": "2026-03-06T20:00:00Z",
            "expires_at": "2026-03-06T21:00:00Z",
            "verify_url": "https://api.agentpier.org/vtokens/vt_def456/verify",
            "status": "active",
        }

        ap = AgentPier(api_key="ap_test_123")
        token = ap.vtokens.create()

        assert token.purpose == "general"
        assert token.listing_id is None

        # No listing_id or metadata in body
        body = mock_post.call_args[0][1]
        assert "listing_id" not in body
        assert "metadata" not in body
        assert body["single_use"] is False
        assert body["max_claims"] == 1

    @patch.object(AgentPierClient, "post")
    def test_claim_vtoken_success(self, mock_post):
        """Test successfully claiming a v-token."""
        mock_post.return_value = {
            "claimed": True,
            "token": "vt_abc123",
            "issuer": {
                "agent_id": "usr_seller123",
                "agent_name": "CodeReviewBot",
                "trust_tier": "established",
                "trust_score": 72,
            },
            "claimant": {
                "agent_id": "usr_buyer456",
                "agent_name": "DataAgent",
                "trust_tier": "emerging",
                "trust_score": 45,
            },
            "mutual_verification": True,
            "claimed_at": "2026-03-06T20:05:00Z",
        }

        ap = AgentPier(api_key="ap_test_123")
        claim = ap.vtokens.claim("vt_abc123", notes="Interested")

        assert isinstance(claim, VTokenClaim)
        assert claim.claimed is True
        assert claim.mutual_verification is True
        assert claim.issuer.agent_id == "usr_seller123"
        assert claim.issuer.trust_score == 72
        assert claim.claimant.agent_id == "usr_buyer456"
        assert claim.claimant.trust_score == 45

        # Verify request
        call_args = mock_post.call_args
        assert call_args[0][0] == "/vtokens/vt_abc123/claim"
        assert call_args[0][1] == {"notes": "Interested"}

    @patch.object(AgentPierClient, "post")
    def test_claim_vtoken_expired(self, mock_post):
        """Test claiming an expired v-token."""
        mock_post.return_value = {
            "claimed": False,
            "reason": "expired",
        }

        ap = AgentPier(api_key="ap_test_123")
        claim = ap.vtokens.claim("vt_expired")

        assert claim.claimed is False
        assert claim.reason == "expired"
        assert claim.issuer is None

    @patch.object(AgentPierClient, "post")
    def test_claim_vtoken_self_claim(self, mock_post):
        """Test that self-claiming is rejected."""
        mock_post.return_value = {
            "claimed": False,
            "reason": "cannot_claim_own_token",
        }

        ap = AgentPier(api_key="ap_test_123")
        claim = ap.vtokens.claim("vt_own_token")

        assert claim.claimed is False
        assert claim.reason == "cannot_claim_own_token"

    @patch.object(AgentPierClient, "post")
    def test_claim_vtoken_max_claims_reached(self, mock_post):
        """Test claiming when max claims reached."""
        mock_post.return_value = {
            "claimed": False,
            "reason": "max_claims_reached",
        }

        ap = AgentPier(api_key="ap_test_123")
        claim = ap.vtokens.claim("vt_exhausted")

        assert claim.claimed is False
        assert claim.reason == "max_claims_reached"

    @patch.object(AgentPierClient, "get")
    def test_list_vtokens(self, mock_get):
        """Test listing issued v-tokens."""
        mock_get.return_value = {
            "tokens": [
                {
                    "token": "vt_abc123",
                    "issuer_id": "usr_seller123",
                    "purpose": "transaction",
                    "created_at": "2026-03-06T20:00:00Z",
                    "expires_at": "2026-03-06T21:00:00Z",
                    "verify_url": "https://api.agentpier.org/vtokens/vt_abc123/verify",
                    "status": "active",
                    "listing_id": "lst_abc123",
                },
                {
                    "token": "vt_def456",
                    "issuer_id": "usr_seller123",
                    "purpose": "general",
                    "created_at": "2026-03-06T19:00:00Z",
                    "expires_at": "2026-03-06T20:00:00Z",
                    "verify_url": "https://api.agentpier.org/vtokens/vt_def456/verify",
                    "status": "expired",
                },
            ]
        }

        ap = AgentPier(api_key="ap_test_123")
        tokens = ap.vtokens.list(status="active", limit=10)

        assert len(tokens) == 2
        assert all(isinstance(t, VToken) for t in tokens)
        assert tokens[0].token == "vt_abc123"
        assert tokens[0].listing_id == "lst_abc123"
        assert tokens[1].token == "vt_def456"
        assert tokens[1].listing_id is None

        # Verify request params
        call_args = mock_get.call_args
        assert call_args[0][0] == "/vtokens"
        assert call_args[1]["params"] == {"status": "active", "limit": 10}

    @patch.object(AgentPierClient, "get")
    def test_list_vtokens_empty(self, mock_get):
        """Test listing with no results."""
        mock_get.return_value = {"tokens": []}

        ap = AgentPier(api_key="ap_test_123")
        tokens = ap.vtokens.list()

        assert tokens == []

    @patch.object(AgentPierClient, "get")
    def test_get_claims(self, mock_get):
        """Test getting claims for a v-token."""
        mock_get.return_value = {
            "token": "vt_abc123",
            "claims": [
                {
                    "claimant_id": "usr_buyer456",
                    "claimant_name": "DataAnalysisAgent",
                    "trust_tier": "established",
                    "trust_score": 68,
                    "claimed_at": "2026-03-06T20:05:00Z",
                },
                {
                    "claimant_id": "usr_buyer789",
                    "claimant_name": "ResearchBot",
                    "trust_tier": "basic",
                    "trust_score": 52,
                    "claimed_at": "2026-03-06T20:10:00Z",
                },
            ],
        }

        ap = AgentPier(api_key="ap_test_123")
        claims = ap.vtokens.get_claims("vt_abc123")

        assert len(claims) == 2
        assert all(isinstance(c, VTokenClaimant) for c in claims)
        assert claims[0].claimant_id == "usr_buyer456"
        assert claims[0].claimant_name == "DataAnalysisAgent"
        assert claims[0].trust_score == 68
        assert claims[1].claimant_id == "usr_buyer789"

        mock_get.assert_called_once_with("/vtokens/vt_abc123/claims")

    @patch.object(AgentPierClient, "get")
    def test_get_claims_empty(self, mock_get):
        """Test getting claims when none exist."""
        mock_get.return_value = {"token": "vt_abc123", "claims": []}

        ap = AgentPier(api_key="ap_test_123")
        claims = ap.vtokens.get_claims("vt_abc123")

        assert claims == []


class TestVTokenVerify:
    """Test v-token verification (class method, no auth)."""

    @patch("agentpier.vtokens._requests.get")
    def test_verify_valid_token(self, mock_get):
        """Test verifying a valid v-token."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "valid": True,
            "issuer": {
                "agent_id": "usr_seller123",
                "agent_name": "CodeReviewBot",
                "trust_tier": "established",
                "trust_score": 72,
                "confidence": 0.65,
                "registered_at": "2025-12-01T00:00:00Z",
            },
            "purpose": "service_inquiry",
            "listing": {
                "listing_id": "lst_abc123",
                "title": "Expert Code Review",
                "category": "development",
            },
            "created_at": "2026-03-06T20:00:00Z",
            "expires_at": "2026-03-06T21:00:00Z",
            "claims_count": 0,
            "signature": "hmac_sha256_hex_here",
            "signature_algorithm": "HMAC-SHA256",
            "signed_fields": "token:issuer_id:purpose:trust_score:created_at:expires_at",
        }
        mock_get.return_value = mock_response

        result = VTokenMethods.verify("vt_abc123")

        assert isinstance(result, VTokenVerification)
        assert result.valid is True
        assert result.issuer.agent_id == "usr_seller123"
        assert result.issuer.agent_name == "CodeReviewBot"
        assert result.issuer.trust_tier == "established"
        assert result.issuer.trust_score == 72
        assert result.issuer.confidence == 0.65
        assert result.purpose == "service_inquiry"
        assert result.listing.listing_id == "lst_abc123"
        assert result.listing.title == "Expert Code Review"
        assert result.claims_count == 0
        assert result.signature == "hmac_sha256_hex_here"

        # Verify the request was made to the correct URL
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "vtokens/vt_abc123/verify" in call_args[0][0]

    @patch("agentpier.vtokens._requests.get")
    def test_verify_invalid_token(self, mock_get):
        """Test verifying an invalid/expired v-token."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "valid": False,
            "reason": "expired",
        }
        mock_get.return_value = mock_response

        result = VTokenMethods.verify("vt_expired_token")

        assert result.valid is False
        assert result.reason == "expired"
        assert result.issuer is None

    @patch("agentpier.vtokens._requests.get")
    def test_verify_no_listing(self, mock_get):
        """Test verifying a token with no listing attached."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "valid": True,
            "issuer": {
                "agent_id": "usr_seller123",
                "agent_name": "GenericAgent",
                "trust_tier": "basic",
                "trust_score": 50,
            },
            "purpose": "identity_proof",
            "created_at": "2026-03-06T20:00:00Z",
            "expires_at": "2026-03-06T21:00:00Z",
            "claims_count": 0,
        }
        mock_get.return_value = mock_response

        result = VTokenMethods.verify("vt_no_listing")

        assert result.valid is True
        assert result.listing is None
        assert result.issuer.trust_tier == "basic"

    @patch("agentpier.vtokens._requests.get")
    def test_verify_custom_base_url(self, mock_get):
        """Test verifying with a custom base URL."""
        mock_response = Mock()
        mock_response.json.return_value = {"valid": False, "reason": "not_found"}
        mock_get.return_value = mock_response

        VTokenMethods.verify("vt_test", base_url="https://staging.agentpier.org")

        call_url = mock_get.call_args[0][0]
        assert call_url.startswith("https://staging.agentpier.org/")

    @patch("agentpier.vtokens._requests.get")
    def test_verify_via_agentpier_class(self, mock_get):
        """Test the convenience static method on AgentPier."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "valid": True,
            "issuer": {
                "agent_id": "usr_test",
                "agent_name": "TestBot",
                "trust_tier": "certified",
                "trust_score": 90,
            },
            "purpose": "general",
            "created_at": "2026-03-06T20:00:00Z",
            "expires_at": "2026-03-06T21:00:00Z",
            "claims_count": 0,
        }
        mock_get.return_value = mock_response

        result = AgentPier.verify_vtoken("vt_test_static")

        assert result.valid is True
        assert result.issuer.trust_score == 90

    @patch("agentpier.vtokens._requests.get")
    def test_verify_via_trust_methods(self, mock_get):
        """Test the convenience class method on TrustMethods."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "valid": True,
            "issuer": {
                "agent_id": "usr_test",
                "agent_name": "TestBot",
                "trust_tier": "established",
                "trust_score": 75,
            },
            "purpose": "transaction",
            "created_at": "2026-03-06T20:00:00Z",
            "expires_at": "2026-03-06T21:00:00Z",
            "claims_count": 0,
        }
        mock_get.return_value = mock_response

        result = TrustMethods.verify_vtoken("vt_trust_method")

        assert result.valid is True
        assert result.issuer.trust_score == 75


class TestAgentPierVTokensProperty:
    """Test that vtokens is accessible on the main SDK class."""

    def test_vtokens_property_exists(self):
        """Test that AgentPier has a vtokens attribute."""
        ap = AgentPier(api_key="ap_test_123")
        assert hasattr(ap, "vtokens")
        assert isinstance(ap.vtokens, VTokenMethods)

    def test_vtokens_shares_client(self):
        """Test that vtokens uses the same HTTP client."""
        ap = AgentPier(api_key="ap_test_123")
        assert ap.vtokens.client is ap._client


class TestVTokenTypes:
    """Test v-token type definitions."""

    def test_vtoken_dataclass(self):
        """Test VToken dataclass construction."""
        token = VToken(
            token="vt_test",
            issuer_id="usr_123",
            purpose="general",
            created_at="2026-03-06T20:00:00Z",
            expires_at="2026-03-06T21:00:00Z",
            verify_url="https://api.agentpier.org/vtokens/vt_test/verify",
            status="active",
        )

        assert token.token == "vt_test"
        assert token.listing_id is None

    def test_vtoken_with_listing(self):
        """Test VToken with listing_id."""
        token = VToken(
            token="vt_test",
            issuer_id="usr_123",
            purpose="transaction",
            created_at="2026-03-06T20:00:00Z",
            expires_at="2026-03-06T21:00:00Z",
            verify_url="https://api.agentpier.org/vtokens/vt_test/verify",
            status="active",
            listing_id="lst_456",
        )

        assert token.listing_id == "lst_456"

    def test_vtoken_verification_valid(self):
        """Test VTokenVerification for a valid token."""
        issuer = VTokenIssuer(
            agent_id="usr_123",
            agent_name="TestBot",
            trust_tier="established",
            trust_score=72,
        )

        result = VTokenVerification(
            valid=True,
            issuer=issuer,
            purpose="transaction",
        )

        assert result.valid is True
        assert result.issuer.trust_score == 72
        assert result.reason is None

    def test_vtoken_verification_invalid(self):
        """Test VTokenVerification for an invalid token."""
        result = VTokenVerification(valid=False, reason="expired")

        assert result.valid is False
        assert result.reason == "expired"
        assert result.issuer is None

    def test_vtoken_claim_success(self):
        """Test VTokenClaim for a successful claim."""
        issuer = VTokenIssuer(
            agent_id="usr_seller",
            agent_name="Seller",
            trust_tier="established",
            trust_score=72,
        )
        claimant = VTokenIssuer(
            agent_id="usr_buyer",
            agent_name="Buyer",
            trust_tier="emerging",
            trust_score=45,
        )

        claim = VTokenClaim(
            claimed=True,
            token="vt_test",
            issuer=issuer,
            claimant=claimant,
            mutual_verification=True,
            claimed_at="2026-03-06T20:05:00Z",
        )

        assert claim.claimed is True
        assert claim.mutual_verification is True
        assert claim.issuer.trust_score == 72
        assert claim.claimant.trust_score == 45

    def test_vtoken_claimant(self):
        """Test VTokenClaimant dataclass."""
        claimant = VTokenClaimant(
            claimant_id="usr_buyer456",
            claimant_name="DataAgent",
            trust_tier="established",
            trust_score=68,
            claimed_at="2026-03-06T20:05:00Z",
        )

        assert claimant.claimant_id == "usr_buyer456"
        assert claimant.trust_score == 68

    def test_vtoken_listing(self):
        """Test VTokenListing dataclass."""
        listing = VTokenListing(
            listing_id="lst_abc123",
            title="Expert Code Review",
            category="development",
        )

        assert listing.listing_id == "lst_abc123"
        assert listing.title == "Expert Code Review"


if __name__ == "__main__":
    pytest.main([__file__])
