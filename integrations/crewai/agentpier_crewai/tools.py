"""
CrewAI Tools for AgentPier Trust Scoring

Tools that CrewAI agents can use to check trust scores of other agents mid-workflow.
"""

from typing import Type, Optional, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from agentpier import AgentPier
from agentpier.exceptions import AgentPierError, NotFoundError


class TrustScoreInput(BaseModel):
    """Input schema for TrustScoreChecker."""

    agent_id: str = Field(..., description="Agent identifier to check trust score for")


class AgentVerificationInput(BaseModel):
    """Input schema for AgentTrustVerifier."""

    agent_ids: str = Field(
        ..., description="Comma-separated list of agent IDs to verify"
    )
    min_score: float = Field(
        default=60.0, description="Minimum trust score required (0-100)"
    )


class TrustScoreChecker(BaseTool):
    """Tool to check trust scores of agents during CrewAI workflows."""

    name: str = "Check Agent Trust Score"
    description: str = """
    Check the trust score and reputation of an agent from AgentPier.
    Use this tool before delegating tasks to other agents or when making trust-based decisions.
    Returns detailed trust information including score, tier, and recent activity.
    """
    args_schema: Type[BaseModel] = TrustScoreInput

    def __init__(self, api_key: str, base_url: str = "https://api.agentpier.org"):
        super().__init__()
        self.agent_pier = AgentPier(api_key=api_key, base_url=base_url)

    def _run(self, agent_id: str) -> str:
        """Check trust score for a specific agent."""
        try:
            agent_score = self.agent_pier.trust.get_score(agent_id)

            # Format trust information for the agent
            result = f"""
Trust Score Report for Agent '{agent_score.agent_name or agent_id}':

Overall Trust Score: {agent_score.trust_score:.1f}/100
Trust Tier: {(agent_score.trust_tier or 'unknown').title()}

ACE Breakdown:
- Autonomy: {agent_score.axes.get('autonomy', 0):.1f}/100 if agent_score.axes else 0.0
- Competence: {agent_score.axes.get('competence', 0):.1f}/100 if agent_score.axes else 0.0  
- Experience: {agent_score.axes.get('experience', 0):.1f}/100 if agent_score.axes else 0.0

History:
- Total Events: {agent_score.history.get('total_events', 0) if agent_score.history else 0}
- Success Rate: {agent_score.history.get('success_events', 0) if agent_score.history else 0}/{agent_score.history.get('total_events', 0) if agent_score.history else 0}
- Safety Violations: {agent_score.history.get('safety_violations', 0) if agent_score.history else 0}

Registration: {agent_score.registered_at.isoformat() if agent_score.registered_at else 'Unknown'}
"""

            # Add Moltbook verification if available
            if agent_score.sources and agent_score.sources.get("moltbook"):
                moltbook_data = agent_score.sources["moltbook"]
                result += f"\nMoltbook Verification: {'✓ Verified' if moltbook_data.get('verified') else '✗ Not verified'}"
                if moltbook_data.get("karma"):
                    result += f"\nMoltbook Karma: {moltbook_data.get('karma')}"

            return result.strip()

        except NotFoundError:
            return f"Agent '{agent_id}' not found in AgentPier trust system."
        except AgentPierError as e:
            return f"Error checking trust score: {str(e)}"
        except Exception as e:
            return f"Unexpected error checking trust score: {str(e)}"


class AgentTrustVerifier(BaseTool):
    """Tool to verify multiple agents meet minimum trust thresholds."""

    name: str = "Verify Agent Trust Levels"
    description: str = """
    Verify that multiple agents meet minimum trust score requirements.
    Use this before starting multi-agent workflows to ensure all participants are trustworthy.
    Returns pass/fail results and recommendations.
    """
    args_schema: Type[BaseModel] = AgentVerificationInput

    def __init__(self, api_key: str, base_url: str = "https://api.agentpier.org"):
        super().__init__()
        self.agent_pier = AgentPier(api_key=api_key, base_url=base_url)

    def _run(self, agent_ids: str, min_score: float = 60.0) -> str:
        """Verify trust levels for multiple agents."""
        agent_list = [aid.strip() for aid in agent_ids.split(",")]
        results = []
        all_passed = True

        for agent_id in agent_list:
            if not agent_id:
                continue

            try:
                agent_score = self.agent_pier.trust.get_score(agent_id)
                trust_score = agent_score.trust_score
                trust_tier = agent_score.trust_tier or "unknown"
                agent_name = agent_score.agent_name or agent_id

                if trust_score >= min_score:
                    results.append(
                        f"✅ {agent_name}: {trust_score:.1f}/100 ({trust_tier}) - PASSED"
                    )
                else:
                    results.append(
                        f"❌ {agent_name}: {trust_score:.1f}/100 ({trust_tier}) - FAILED (min: {min_score})"
                    )
                    all_passed = False

            except NotFoundError:
                results.append(f"❌ {agent_id}: Not found in trust system")
                all_passed = False
            except AgentPierError as e:
                results.append(f"❌ {agent_id}: Error - {str(e)}")
                all_passed = False
            except Exception as e:
                results.append(f"❌ {agent_id}: Error - {str(e)}")
                all_passed = False

        summary = "✅ All agents verified" if all_passed else "❌ Verification failed"

        return f"""
Agent Trust Verification Results:
Minimum Required Score: {min_score}/100

{chr(10).join(results)}

{summary}

Recommendation: {'Proceed with workflow' if all_passed else 'Review failed agents before proceeding'}
"""
