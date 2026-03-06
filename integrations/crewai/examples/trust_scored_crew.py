#!/usr/bin/env python3
"""
AgentPier CrewAI Integration - Working Example

Demonstrates how to use AgentPier trust scoring with CrewAI workflows.
This example shows:
1. Trust verification before workflow execution
2. Automatic trust reporting during task execution
3. Mid-workflow trust checking by agents
"""

import os
from crewai import Agent, Task, Crew, Process
from agentpier_crewai import AgentPierMonitor, TrustVerifier, TrustScoreChecker


def main():
    # Get API key from environment
    api_key = os.getenv("AGENTPIER_API_KEY")
    if not api_key:
        print("❌ Error: AGENTPIER_API_KEY environment variable not set")
        print("   Get your API key from https://agentpier.com/dashboard")
        return

    print("🔍 AgentPier CrewAI Trust Scoring Example")
    print("=" * 50)

    # Step 1: Initialize trust monitoring
    print("\n1️⃣ Setting up trust monitoring...")

    monitor = AgentPierMonitor(
        api_key=api_key,
        auto_register=True,  # Auto-register agents if not found
        agent_mapping={
            "Research Specialist": "research_agent_v1",
            "Content Writer": "writer_agent_v1",
            "Quality Reviewer": "reviewer_agent_v1",
        },
    )

    trust_verifier = TrustVerifier(
        api_key=api_key, min_score=50.0  # Require minimum 50/100 trust score
    )

    # Create trust checking tool for agents to use
    trust_checker = TrustScoreChecker(api_key=api_key)

    print("✅ Trust monitoring initialized")

    # Step 2: Define agents with different roles
    print("\n2️⃣ Creating CrewAI agents...")

    researcher = Agent(
        role="Research Specialist",
        goal="Research and gather information on given topics",
        backstory="Expert researcher with strong analytical skills and attention to detail",
        verbose=True,
    )

    writer = Agent(
        role="Content Writer",
        goal="Create engaging and informative content",
        backstory="Creative writer skilled at transforming research into compelling narratives",
        verbose=True,
    )

    reviewer = Agent(
        role="Quality Reviewer",
        goal="Review content for quality and delegate additional work if needed",
        backstory="Senior reviewer with authority to assign work to other agents",
        tools=[trust_checker],  # Give reviewer ability to check trust scores
        verbose=True,
    )

    agents = [researcher, writer, reviewer]
    print(f"✅ Created {len(agents)} agents")

    # Step 3: Verify agent trust levels before starting
    print("\n3️⃣ Verifying agent trust levels...")

    verification = trust_verifier.check_crew(Crew(agents=agents, tasks=[]))

    print(f"📊 Trust Verification Results:")
    print(f"   Total Agents: {verification['total_agents']}")
    print(f"   Verified: {verification['verified_count']}")
    print(f"   Failed: {verification['failed_count']}")
    print(f"   Minimum Required: {verification['min_score']}/100")

    for result in verification["results"]:
        status = "✅" if result["verified"] else "❌"
        score = result.get("trust_score", 0)
        print(
            f"   {status} {result['agent_name']}: {score:.1f}/100 - {result['reason']}"
        )

    if not verification["all_verified"]:
        print(
            "\n⚠️  Some agents don't meet trust requirements, but continuing with example..."
        )

    # Step 4: Define tasks with dependencies
    print("\n4️⃣ Creating tasks with trust monitoring...")

    research_task = Task(
        description="""
        Research the current state of AI agent trust and reputation systems.
        Focus on:
        - Existing solutions and their limitations
        - Key challenges in agent verification
        - Emerging standards and best practices
        
        Provide a comprehensive summary with key findings.
        """,
        agent=researcher,
        expected_output="A detailed research report with findings and insights",
    )

    writing_task = Task(
        description="""
        Write a blog post based on the research findings about AI agent trust systems.
        The post should be:
        - Informative yet accessible to a technical audience
        - Well-structured with clear sections
        - Include practical implications for developers
        
        Target length: 800-1000 words.
        """,
        agent=writer,
        expected_output="A complete blog post ready for publication",
    )

    review_task = Task(
        description="""
        Review the blog post for quality, accuracy, and completeness.
        
        Before accepting the work, use the trust checking tool to verify 
        the writer's current trust score. If the score is concerning,
        recommend improvements or request revisions.
        
        Provide feedback and final approval or rejection.
        """,
        agent=reviewer,
        expected_output="Quality review with approval status and any feedback",
    )

    tasks = [research_task, writing_task, review_task]
    print(f"✅ Created {len(tasks)} tasks")

    # Step 5: Create crew with trust monitoring callbacks
    print("\n5️⃣ Creating crew with trust monitoring...")

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        callbacks=[
            monitor.on_task_start,  # Optional: Track task starts
            monitor.on_task_complete,  # Report successful completions
            monitor.on_task_fail,  # Report failures
        ],
    )

    print("✅ Crew created with trust monitoring callbacks")

    # Step 6: Execute workflow with trust tracking
    print("\n6️⃣ Starting workflow execution...")
    print("📝 Task outcomes will be automatically reported to AgentPier")
    print("🔄 This may take a few minutes...")

    try:
        result = crew.kickoff()

        print("\n🎉 Workflow completed successfully!")
        print("\n📄 Final Result:")
        print("-" * 40)
        print(result)

    except Exception as e:
        print(f"\n❌ Workflow failed: {str(e)}")
        print("💡 Check agent configurations and API connectivity")

    # Step 7: Show final trust status
    print("\n7️⃣ Checking final trust scores...")

    final_verification = trust_verifier.check_crew(crew)

    print("📈 Updated Trust Scores:")
    for result in final_verification["results"]:
        score = result.get("trust_score", 0)
        tier = result.get("trust_tier", "unknown")
        print(f"   {result['agent_name']}: {score:.1f}/100 ({tier})")

    print("\n✨ Example completed!")
    print("🔗 View detailed trust reports at https://agentpier.com/dashboard")


if __name__ == "__main__":
    main()
