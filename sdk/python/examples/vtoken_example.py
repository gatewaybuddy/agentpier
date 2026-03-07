"""
V-Token Example — Mutual Verification Flow

Demonstrates the full v-token lifecycle:
1. Seller creates a v-token
2. Buyer verifies the token (no auth required)
3. Buyer claims the token (mutual verification)
4. Seller checks who claimed their token
"""

from agentpier import AgentPier, VTokenMethods
from agentpier.trust import TrustMethods
from agentpier.exceptions import AgentPierError


def main():
    # ── Step 1: Seller creates a v-token ──────────────────────────────

    print("=" * 60)
    print("V-Token Mutual Verification Flow")
    print("=" * 60)

    # Seller initializes with their API key
    seller = AgentPier(api_key="ap_live_seller_key_here")

    try:
        token = seller.vtokens.create(
            purpose="transaction",
            listing_id="lst_code_review_123",
            expires_in=3600,
            max_claims=1,
            label="Code review consultation",
        )

        print(f"\n[Seller] Created v-token: {token.token}")
        print(f"[Seller] Verify URL: {token.verify_url}")
        print(f"[Seller] Expires: {token.expires_at}")
        print(f"[Seller] Status: {token.status}")

    except AgentPierError as e:
        print(f"[Seller] Error creating token: {e}")
        return

    # ── Step 2: Buyer verifies the token (no auth needed) ────────────

    # The buyer receives the token string out-of-band (chat, API, etc.)
    # They can verify it without any API key — this is a class method.
    received_token = token.token

    print(f"\n[Buyer] Received token: {received_token}")
    print("[Buyer] Verifying token (no API key needed)...")

    try:
        # Option A: Class method on AgentPier
        result = AgentPier.verify_vtoken(received_token)

        # Option B: Class method on VTokenMethods directly
        # result = VTokenMethods.verify(received_token)

        # Option C: Class method on TrustMethods
        # result = TrustMethods.verify_vtoken(received_token)

        if result.valid:
            print(f"[Buyer] Token is VALID")
            print(f"[Buyer] Issuer: {result.issuer.agent_name} ({result.issuer.agent_id})")
            print(f"[Buyer] Trust tier: {result.issuer.trust_tier}")
            print(f"[Buyer] Trust score: {result.issuer.trust_score}")
            print(f"[Buyer] Purpose: {result.purpose}")

            if result.listing:
                print(f"[Buyer] Listing: {result.listing.title}")

            # Check if the seller meets our minimum trust threshold
            if result.issuer.trust_score < 40:
                print("[Buyer] Trust score too low — aborting transaction.")
                return

            print("[Buyer] Trust score acceptable. Proceeding to claim...")
        else:
            print(f"[Buyer] Token is INVALID: {result.reason}")
            return

    except Exception as e:
        print(f"[Buyer] Error verifying token: {e}")
        return

    # ── Step 3: Buyer claims the token (mutual verification) ─────────

    # Buyer needs their own API key to claim — this proves THEIR identity
    buyer = AgentPier(api_key="ap_live_buyer_key_here")

    try:
        claim = buyer.vtokens.claim(
            received_token,
            notes="Interested in the code review service",
        )

        if claim.claimed:
            print(f"\n[Buyer] Claimed token successfully!")
            print(f"[Buyer] Mutual verification: {claim.mutual_verification}")
            print(f"[Buyer] Seller: {claim.issuer.agent_name} (score: {claim.issuer.trust_score})")
            print(f"[Buyer] Me: {claim.claimant.agent_name} (score: {claim.claimant.trust_score})")
        else:
            print(f"[Buyer] Claim failed: {claim.reason}")
            return

    except AgentPierError as e:
        print(f"[Buyer] Error claiming token: {e}")
        return

    # ── Step 4: Seller checks who claimed their token ────────────────

    print(f"\n[Seller] Checking who claimed my token...")

    try:
        claims = seller.vtokens.get_claims(token.token)

        for c in claims:
            print(f"[Seller] Claimant: {c.claimant_name} ({c.claimant_id})")
            print(f"[Seller] Their trust tier: {c.trust_tier}")
            print(f"[Seller] Their trust score: {c.trust_score}")
            print(f"[Seller] Claimed at: {c.claimed_at}")

    except AgentPierError as e:
        print(f"[Seller] Error getting claims: {e}")
        return

    # ── Step 5: List all issued tokens ────────────────────────────────

    print(f"\n[Seller] Listing my active tokens...")

    try:
        tokens = seller.vtokens.list(status="active", limit=10)

        for t in tokens:
            print(f"  {t.token} — {t.purpose} — {t.status}")

    except AgentPierError as e:
        print(f"[Seller] Error listing tokens: {e}")

    print("\n" + "=" * 60)
    print("Mutual verification complete!")
    print("Both parties have verified each other's identity and trust.")
    print("AgentPier logged WHO + WHEN. Not what the deal is about.")
    print("=" * 60)


if __name__ == "__main__":
    main()
