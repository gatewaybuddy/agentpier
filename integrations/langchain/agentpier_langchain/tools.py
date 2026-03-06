"""
LangChain Tools for AgentPier Trust Scoring

Tools that LangChain agents can use to check trust scores during execution.
"""

import requests
from typing import Optional, Dict, Any, List

try:
    from langchain_core.tools import BaseTool
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:
    # Fallback for older LangChain versions
    from langchain.tools import BaseTool
    from pydantic import BaseModel, Field


class TrustScoreInput(BaseModel):
    """Input for trust score checking tool."""

    agent_id: str = Field(description="Agent identifier to check trust score for")


class AgentVerificationInput(BaseModel):
    """Input for agent verification tool."""

    agent_ids: str = Field(description="Comma-separated list of agent IDs to verify")
    min_score: Optional[float] = Field(
        default=60.0, description="Minimum trust score required (0-100)"
    )


class TrustScoreTool(BaseTool):
    """Tool for checking agent trust scores in LangChain workflows."""

    name: str = "check_agent_trust_score"
    description: str = """
    Check the trust score and reputation of an agent from AgentPier.
    Use this tool before delegating tasks to other agents or when making trust-based decisions.
    Input should be an agent identifier (string).
    Returns detailed trust information including score, tier, and recent activity.
    """
    args_schema = TrustScoreInput

    def __init__(self, api_key: str, base_url: str = "https://api.agentpier.org"):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": self.api_key}

    def _run(self, agent_id: str) -> str:
        """Check trust score for a specific agent."""
        try:
            response = requests.get(
                f"{self.base_url}/trust/agents/{agent_id}",
                headers=self.headers,
                timeout=10,
            )

            if response.status_code == 404:
                return f"Agent '{agent_id}' not found in AgentPier trust system."
            elif response.status_code != 200:
                return f"Error checking trust score: {response.status_code} - {response.text}"

            data = response.json()

            # Format trust information
            result = f"""
Agent Trust Report for '{data.get('agent_name', agent_id)}':

🔢 Overall Trust Score: {data.get('trust_score', 0):.1f}/100
🏆 Trust Tier: {data.get('trust_tier', 'unknown').title()}

ACE Breakdown:
• Autonomy: {data.get('axes', {}).get('autonomy', 0):.1f}/100
• Competence: {data.get('axes', {}).get('competence', 0):.1f}/100
• Experience: {data.get('axes', {}).get('experience', 0):.1f}/100

📊 History:
• Total Events: {data.get('history', {}).get('total_events', 0)}
• Success Rate: {data.get('history', {}).get('success_events', 0)}/{data.get('history', {}).get('total_events', 0)}
• Safety Violations: {data.get('history', {}).get('safety_violations', 0)}

📅 Registration: {data.get('registered_at', 'Unknown')}
"""

            # Add Moltbook verification if available
            moltbook_data = data.get("sources", {}).get("moltbook")
            if moltbook_data:
                verification_status = (
                    "✓ Verified" if moltbook_data.get("verified") else "✗ Not verified"
                )
                result += f"\n🐾 Moltbook: {verification_status}"
                if moltbook_data.get("karma"):
                    result += f" (Karma: {moltbook_data.get('karma')})"

            return result.strip()

        except requests.RequestException as e:
            return f"Network error checking trust score: {str(e)}"
        except Exception as e:
            return f"Unexpected error checking trust score: {str(e)}"


class AgentVerificationTool(BaseTool):
    """Tool for verifying multiple agents meet trust requirements."""

    name: str = "verify_agent_trust_levels"
    description: str = """
    Verify that multiple agents meet minimum trust score requirements.
    Use this before starting multi-agent workflows to ensure all participants are trustworthy.
    Input should be comma-separated agent IDs and optional minimum score.
    Returns verification results with pass/fail status and recommendations.
    """
    args_schema = AgentVerificationInput

    def __init__(self, api_key: str, base_url: str = "https://api.agentpier.org"):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": self.api_key}

    def _run(self, agent_ids: str, min_score: float = 60.0) -> str:
        """Verify trust levels for multiple agents."""
        agent_list = [aid.strip() for aid in agent_ids.split(",") if aid.strip()]

        if not agent_list:
            return "Error: No valid agent IDs provided. Please provide comma-separated agent identifiers."

        results = []
        all_passed = True

        for agent_id in agent_list:
            try:
                response = requests.get(
                    f"{self.base_url}/trust/agents/{agent_id}",
                    headers=self.headers,
                    timeout=10,
                )

                if response.status_code == 404:
                    results.append(f"❌ {agent_id}: Not found in trust system")
                    all_passed = False
                    continue
                elif response.status_code != 200:
                    results.append(f"❌ {agent_id}: API error ({response.status_code})")
                    all_passed = False
                    continue

                data = response.json()
                trust_score = data.get("trust_score", 0)
                trust_tier = data.get("trust_tier", "unknown")
                agent_name = data.get("agent_name", agent_id)

                if trust_score >= min_score:
                    results.append(
                        f"✅ {agent_name}: {trust_score:.1f}/100 ({trust_tier}) - PASSED"
                    )
                else:
                    results.append(
                        f"❌ {agent_name}: {trust_score:.1f}/100 ({trust_tier}) - FAILED (required: {min_score})"
                    )
                    all_passed = False

            except Exception as e:
                results.append(f"❌ {agent_id}: Error - {str(e)}")
                all_passed = False

        # Build summary
        summary_icon = "✅" if all_passed else "❌"
        summary_text = "All agents verified" if all_passed else "Verification failed"
        recommendation = (
            "Safe to proceed with workflow"
            if all_passed
            else "Review failed agents before proceeding"
        )

        return f"""
🔍 Agent Trust Verification Results

Minimum Required Score: {min_score}/100
Agents Checked: {len(agent_list)}

{chr(10).join(results)}

{summary_icon} Status: {summary_text}
💡 Recommendation: {recommendation}
"""


class TrustScoreFunction:
    """
    Function-based interface for trust checking (for OpenAI Functions/Tools calling).

    Can be used with LangChain's function calling capabilities or OpenAI's function calling.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.agentpier.org"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": self.api_key}

    @property
    def function_schema(self) -> Dict[str, Any]:
        """OpenAI function schema for trust checking."""
        return {
            "name": "check_agent_trust_score",
            "description": "Check the trust score and reputation of an agent",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "Agent identifier to check trust score for",
                    }
                },
                "required": ["agent_id"],
            },
        }

    def call(self, agent_id: str) -> Dict[str, Any]:
        """Call the function and return structured data."""
        try:
            response = requests.get(
                f"{self.base_url}/trust/agents/{agent_id}",
                headers=self.headers,
                timeout=10,
            )

            if response.status_code == 404:
                return {
                    "success": False,
                    "error": f"Agent '{agent_id}' not found",
                    "agent_id": agent_id,
                }
            elif response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}",
                    "agent_id": agent_id,
                }

            data = response.json()

            return {
                "success": True,
                "agent_id": agent_id,
                "agent_name": data.get("agent_name", agent_id),
                "trust_score": data.get("trust_score", 0),
                "trust_tier": data.get("trust_tier", "unknown"),
                "axes": data.get("axes", {}),
                "history": data.get("history", {}),
                "moltbook_verified": data.get("sources", {})
                .get("moltbook", {})
                .get("verified", False),
                "registered_at": data.get("registered_at"),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "agent_id": agent_id,
            }
