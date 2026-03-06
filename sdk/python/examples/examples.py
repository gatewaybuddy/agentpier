#!/usr/bin/env python3
"""
AgentPier SDK Basic Usage Examples

This file demonstrates common usage patterns for the AgentPier Python SDK.
These examples show real working code that you can copy and modify for your needs.

Prerequisites:
1. Install the SDK: pip install agentpier
2. Get your API key from https://agentpier.org/signup
3. Set it as environment variable: export AGENTPIER_API_KEY="ap_live_your_key"

Run this file: python examples.py
"""

import os
from agentpier import AgentPier
from agentpier.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    AgentPierError,
)


def example_1_basic_setup():
    """Example 1: Basic SDK initialization and connectivity test"""
    print("=== Example 1: Basic Setup ===")

    # Method 1: Auto-detect API key from environment variable
    ap = AgentPier()

    # Method 2: Explicitly set API key
    # ap = AgentPier(api_key="ap_live_your_key_here")

    # Method 3: Custom configuration
    # ap = AgentPier(
    #     api_key="ap_live_your_key",
    #     timeout=60.0,
    #     max_retries=5
    # )

    # Test connectivity
    print(f"API Key present: {bool(ap.api_key)}")
    print(f"Base URL: {ap.base_url}")

    if ap.ping():
        print("✅ Successfully connected to AgentPier API")
    else:
        print("❌ Could not reach AgentPier API")

    # Show version info
    version_info = ap.version_info()
    print(f"SDK version: {version_info['sdk_version']}")
    print(f"Python version: {version_info['python_version']}")
    print()


def example_2_standards_api():
    """Example 2: Working with the Standards API (no authentication required)"""
    print("=== Example 2: Standards API ===")

    ap = AgentPier()

    try:
        # Get current certification standards
        standards = ap.standards.current()
        print(f"Standards version: {standards.version}")
        print(f"Effective date: {standards.effective_date}")

        # Quick version check
        version = ap.standards.get_version()
        print(f"Current standards version: {version}")

        # Check if agent standards are available
        has_standards = ap.standards.has_agent_standards()
        print(f"Agent standards available: {has_standards}")

        # Get compliance information
        compliance = ap.standards.get_compliance_info()
        print(f"Compliance requirements available: {bool(compliance)}")

        print("✅ Standards API working correctly")

    except AgentPierError as e:
        print(f"❌ Standards API error: {e}")
    print()


def example_3_trust_scores():
    """Example 3: Trust scoring and agent search (requires authentication)"""
    print("=== Example 3: Trust Scores ===")

    ap = AgentPier()

    # Check if we have an API key
    if not ap.api_key:
        print("⚠️  Skipping trust examples - no API key found")
        print("   Set AGENTPIER_API_KEY environment variable to test these")
        print()
        return

    try:
        # Example agent ID for testing
        test_agent_id = "demo-agent-123"

        print(f"Looking up trust score for: {test_agent_id}")

        # Get trust score for a specific agent
        try:
            score = ap.trust.get_score(test_agent_id)
            print(f"✅ Agent: {score.agent_name}")
            print(f"   Trust Score: {score.trust_score}")
            print(f"   Trust Tier: {score.trust_tier}")
            print(f"   Verification Status: {score.verification_status}")
            print(f"   Total Events: {score.total_events}")

        except NotFoundError:
            print(f"   Agent '{test_agent_id}' not found (expected for demo)")

        # Search for trusted agents
        print("\nSearching for trusted agents...")
        search_results = ap.trust.search_agents(min_score=75, limit=5)

        print(f"Found {search_results.total} trusted agents")
        print("Top results:")

        for agent in search_results.results[:3]:  # Show top 3
            print(f"  • {agent.agent_name}: {agent.trust_score:.1f}")

        print("✅ Trust API working correctly")

    except AuthenticationError:
        print("❌ Invalid API key - check your AGENTPIER_API_KEY")
    except RateLimitError as e:
        print(f"❌ Rate limited - retry after {e.retry_after} seconds")
    except AgentPierError as e:
        print(f"❌ Trust API error: {e}")
    print()


def example_4_error_handling():
    """Example 4: Proper error handling patterns"""
    print("=== Example 4: Error Handling ===")

    ap = AgentPier()

    # Example 1: Handle missing API key gracefully
    print("Testing API key validation...")
    try:
        # This will fail if no API key is set
        bad_ap = AgentPier(api_key="invalid_key")
        bad_ap.trust.get_score("some-agent")

    except AuthenticationError:
        print("✅ Correctly caught AuthenticationError for invalid key")

    # Example 2: Handle not found errors
    print("Testing not found handling...")
    try:
        if ap.api_key:  # Only test if we have a key
            ap.trust.get_score("definitely-does-not-exist-12345")
    except NotFoundError:
        print("✅ Correctly caught NotFoundError for missing agent")
    except AuthenticationError:
        print("⚠️  Need valid API key to test NotFoundError")

    # Example 3: Handle validation errors
    print("Testing validation error handling...")
    try:
        if ap.api_key:  # Only test if we have a key
            # Invalid agent name format (contains spaces)
            ap.trust.register_agent("invalid agent name with spaces!")
    except ValidationError as e:
        print(f"✅ Correctly caught ValidationError: {e.message}")
    except AuthenticationError:
        print("⚠️  Need valid API key to test ValidationError")

    # Example 4: Generic error handling pattern
    print("Example of comprehensive error handling:")
    print("""
try:
    score = ap.trust.get_score("agent-123")
    print(f"Trust score: {score.trust_score}")
    
except AuthenticationError:
    print("Invalid API key - check your credentials")
    
except NotFoundError:
    print("Agent not found - check the agent ID")
    
except RateLimitError as e:
    print(f"Rate limited - wait {e.retry_after} seconds")
    
except ValidationError as e:
    print(f"Request validation failed: {e.message}")
    
except AgentPierError as e:
    print(f"General API error: {e}")
    
except Exception as e:
    print(f"Unexpected error: {e}")
""")
    print()


def example_5_agent_registration():
    """Example 5: Agent registration workflow (requires authentication)"""
    print("=== Example 5: Agent Registration ===")

    ap = AgentPier()

    if not ap.api_key:
        print("⚠️  Skipping registration example - no API key found")
        print("   Set AGENTPIER_API_KEY environment variable to test")
        print()
        return

    try:
        # Generate a unique agent name for testing
        import time

        test_agent = f"demo_agent_{int(time.time())}"

        print(f"Registering new agent: {test_agent}")

        # Register a new agent
        result = ap.trust.register_agent(
            agent_name=test_agent, description="Demo agent created by SDK examples"
        )

        print(f"✅ Agent registered successfully!")
        print(f"   Agent ID: {result['agent_id']}")
        print(f"   Initial trust score: {result['trust_score']}")

        # Now get the full trust profile
        score = ap.trust.get_score(result["agent_id"])
        print(f"   Full profile retrieved: {score.agent_name}")
        print(f"   Trust tier: {score.trust_tier}")

    except AuthenticationError:
        print("❌ Invalid API key - check your AGENTPIER_API_KEY")
    except ValidationError as e:
        print(f"❌ Registration failed: {e.message}")
    except AgentPierError as e:
        print(f"❌ Registration error: {e}")
    print()


def example_6_search_and_discovery():
    """Example 6: Agent search and discovery features"""
    print("=== Example 6: Search & Discovery ===")

    ap = AgentPier()

    if not ap.api_key:
        print("⚠️  Skipping search examples - no API key found")
        print()
        return

    try:
        print("Searching agents by criteria...")

        # Search by minimum trust score
        high_trust = ap.trust.search_agents(min_score=85, limit=10)
        print(f"Agents with 85+ trust score: {high_trust.total}")

        # Search by trust tier
        verified = ap.trust.search_agents(tier="verified", limit=10)
        print(f"Verified agents: {verified.total}")

        # Search by agent name pattern (if supported)
        # code_agents = ap.trust.search_agents(name_pattern="code", limit=5)
        # print(f"Code-related agents: {code_agents.total}")

        # Show some results
        if high_trust.results:
            print("\nTop high-trust agents:")
            for agent in high_trust.results[:3]:
                print(f"  • {agent.agent_name}")
                print(f"    Score: {agent.trust_score:.1f}")
                print(f"    Tier: {agent.trust_tier}")
                print(f"    Events: {agent.total_events}")
                print()

    except AuthenticationError:
        print("❌ Invalid API key for search operations")
    except AgentPierError as e:
        print(f"❌ Search error: {e}")
    print()


def main():
    """Run all examples"""
    print("🚀 AgentPier SDK Examples")
    print("=" * 50)

    # Check for API key
    api_key = os.getenv("AGENTPIER_API_KEY")
    if not api_key:
        print("⚠️  No AGENTPIER_API_KEY environment variable found")
        print("   Some examples will be skipped")
        print("   Get your key from: https://agentpier.org/signup")
        print()
    else:
        print(f"✅ API key found: {api_key[:12]}...")
        print()

    try:
        # Run examples
        example_1_basic_setup()
        example_2_standards_api()
        example_3_trust_scores()
        example_4_error_handling()
        example_5_agent_registration()
        example_6_search_and_discovery()

        print("🎉 Examples complete!")
        print("=" * 50)
        print("Next steps:")
        print("1. Read the full documentation at https://docs.agentpier.org")
        print("2. Check out demo.py for more comprehensive examples")
        print("3. Build something awesome!")

    except KeyboardInterrupt:
        print("\n\n👋 Examples interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error in examples: {e}")
        print("Please report this issue to the AgentPier team")


if __name__ == "__main__":
    main()
