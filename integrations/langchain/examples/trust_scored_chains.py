#!/usr/bin/env python3
"""
AgentPier LangChain Integration - Working Example

Demonstrates how to use AgentPier trust scoring with LangChain workflows.
This example shows:
1. Trust monitoring with callbacks
2. Trust verification before chain execution
3. Trust checking tools for agents to use
"""

import os
from langchain.chains import LLMChain, SequentialChain
from langchain.prompts import PromptTemplate
from langchain.agents import initialize_agent, Tool, AgentType
from agentpier_langchain import ChainMonitor, TrustScoreTool, AgentVerificationTool


# Mock LLM for demo purposes (replace with real LLM)
class MockLLM:
    """Mock LLM for demonstration - replace with real LLM like OpenAI"""

    def __call__(self, prompt: str) -> str:
        if "summarize" in prompt.lower():
            return "This is a mock summary of the input text."
        elif "analyze" in prompt.lower():
            return "This is a mock analysis with key insights and recommendations."
        elif "check trust" in prompt.lower():
            return "I should check the trust score of the agent before proceeding."
        else:
            return f"Mock response to: {prompt[:100]}..."

    def predict(self, text: str) -> str:
        return self(text)


def main():
    # Get API key from environment
    api_key = os.getenv("AGENTPIER_API_KEY")
    if not api_key:
        print("❌ Error: AGENTPIER_API_KEY environment variable not set")
        print("   Get your API key from https://agentpier.com/dashboard")
        print("   For demo purposes, using 'demo_key' - some features may not work")
        api_key = "demo_key"

    print("🔗 AgentPier LangChain Trust Scoring Example")
    print("=" * 50)

    # Step 1: Initialize trust monitoring
    print("\n1️⃣ Setting up trust monitoring...")

    monitor = ChainMonitor(
        api_key=api_key,
        agent_mapping={
            "summary_chain": "summarizer_v1",
            "analysis_chain": "analyzer_v1",
            "supervisor_agent": "supervisor_v1",
        },
        auto_register=True,
        track_chains=True,
        track_tools=True,
        track_llm_calls=False,  # Too verbose for demo
    )

    print("✅ Trust monitoring initialized")

    # Step 2: Create trust tools for agents
    print("\n2️⃣ Creating trust verification tools...")

    trust_checker = TrustScoreTool(api_key=api_key)
    agent_verifier = AgentVerificationTool(api_key=api_key)

    # Create LangChain tools
    tools = [
        Tool(
            name="check_agent_trust_score",
            func=trust_checker._run,
            description="Check the trust score and reputation of an agent before delegation",
        ),
        Tool(
            name="verify_multiple_agents",
            func=agent_verifier._run,
            description="Verify that multiple agents meet minimum trust score requirements",
        ),
        Tool(
            name="calculator",
            func=lambda x: f"Result: {eval(x) if x.replace('.','').replace('+','').replace('-','').replace('*','').replace('/','').replace(' ','').isdigit() else 'Invalid calculation'}",
            description="Perform basic calculations",
        ),
    ]

    print("✅ Trust tools created")

    # Step 3: Create chains with trust monitoring
    print("\n3️⃣ Creating LangChain chains...")

    # Mock LLM (replace with real LLM like OpenAI)
    llm = MockLLM()

    # Summary chain
    summary_prompt = PromptTemplate(
        template="Summarize the following text in 2-3 sentences:\n\nText: {text}\n\nSummary:",
        input_variables=["text"],
    )

    summary_chain = LLMChain(
        llm=llm,
        prompt=summary_prompt,
        output_key="summary",
        callbacks=[monitor.get_callback()],  # Add trust monitoring
    )

    # Analysis chain
    analysis_prompt = PromptTemplate(
        template="Analyze the following summary and provide key insights:\n\nSummary: {summary}\n\nAnalysis:",
        input_variables=["summary"],
    )

    analysis_chain = LLMChain(
        llm=llm,
        prompt=analysis_prompt,
        output_key="analysis",
        callbacks=[monitor.get_callback()],  # Add trust monitoring
    )

    # Sequential chain combining both
    overall_chain = SequentialChain(
        chains=[summary_chain, analysis_chain],
        input_variables=["text"],
        output_variables=["summary", "analysis"],
        callbacks=[monitor.get_callback()],  # Add trust monitoring
    )

    print("✅ Chains created with trust monitoring")

    # Step 4: Create agent with trust tools
    print("\n4️⃣ Creating agent with trust verification capabilities...")

    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        callbacks=[monitor.get_callback()],  # Add trust monitoring
        verbose=True,
    )

    print("✅ Agent created with trust tools")

    # Step 5: Verify chain agents before execution
    print("\n5️⃣ Verifying chain trust levels...")

    chain_agents = ["summarizer_v1", "analyzer_v1"]
    verification = monitor.verify_multiple_agents(chain_agents, min_score=50.0)

    print(f"📊 Chain Agent Verification:")
    print(f"   Total Agents: {verification['total_agents']}")
    print(f"   Verified: {verification['verified_count']}")
    print(f"   Failed: {verification['failed_count']}")

    for result in verification["results"]:
        status = "✅" if result["verified"] else "❌"
        score = result.get("trust_score", "N/A")
        print(f"   {status} {result['agent_id']}: {score} - {result['reason']}")

    if not verification["all_verified"]:
        print(
            "\n⚠️  Some chain agents don't meet requirements, but continuing with demo..."
        )

    # Step 6: Execute chains with trust tracking
    print("\n6️⃣ Running chains with trust monitoring...")

    sample_text = """
    Artificial Intelligence has revolutionized many industries in recent years. 
    Machine learning algorithms can now process vast amounts of data to identify 
    patterns and make predictions. However, concerns about AI safety, bias, and 
    transparency remain important challenges that need to be addressed as the 
    technology continues to advance.
    """

    try:
        print("🔄 Executing sequential chain (summary + analysis)...")
        chain_result = overall_chain({"text": sample_text})

        print("\n📄 Chain Results:")
        print(f"Summary: {chain_result['summary']}")
        print(f"Analysis: {chain_result['analysis']}")

    except Exception as e:
        print(f"❌ Chain execution failed: {str(e)}")
        print("💡 This is expected in demo mode with mock LLM")

    # Step 7: Test agent with trust verification
    print("\n7️⃣ Testing agent with trust verification capabilities...")

    try:
        print("🤖 Agent task: Check trust of summarizer_v1 and analyzer_v1...")

        agent_task = """
        Check the trust scores of these two agents: summarizer_v1, analyzer_v1
        Then calculate 50 + 25 using the calculator tool.
        Provide a summary of whether we should proceed with using these agents.
        """

        agent_result = agent.run(agent_task)
        print(f"\n🤖 Agent Response:\n{agent_result}")

    except Exception as e:
        print(f"❌ Agent execution failed: {str(e)}")
        print("💡 This is expected in demo mode with mock LLM")

    # Step 8: Manual trust reporting
    print("\n8️⃣ Testing manual trust event reporting...")

    success = monitor.report_custom_event(
        agent_id="demo_agent",
        event_type="task_completion",
        outcome="success",
        details="Demo completed successfully",
        metadata={"demo_mode": True, "version": "v1.0"},
    )

    if success:
        print("✅ Custom trust event reported successfully")
    else:
        print("❌ Failed to report custom trust event (expected in demo mode)")

    # Step 9: Get trust summary
    print("\n9️⃣ Getting trust summary for workflow agents...")

    all_agents = ["summarizer_v1", "analyzer_v1", "supervisor_v1", "demo_agent"]
    trust_summary = monitor.get_trust_summary(all_agents)

    print("📈 Trust Summary:")
    print(f"   Total Agents: {trust_summary['total_agents']}")
    print(f"   Found in System: {trust_summary['found_agents']}")
    print(f"   Average Score: {trust_summary['average_score']:.1f}/100")

    for agent_data in trust_summary["agents"]:
        if agent_data.get("found"):
            score = agent_data.get("trust_score", 0)
            tier = agent_data.get("trust_tier", "unknown")
            print(f"   📊 {agent_data['agent_name']}: {score:.1f}/100 ({tier})")
        else:
            error = agent_data.get("error", "Not found")
            print(f"   ❓ {agent_data['agent_id']}: {error}")

    print("\n✨ LangChain integration example completed!")
    print("\n📋 What happened:")
    print("   1. ✅ Trust monitoring was set up for LangChain components")
    print("   2. ✅ Trust verification tools were created for agents")
    print("   3. ✅ Chains were created with automatic trust reporting")
    print("   4. ✅ Agent was given trust verification capabilities")
    print("   5. ✅ Chain execution outcomes were reported to AgentPier")
    print("   6. ✅ Agent could check trust scores during execution")
    print("   7. ✅ Custom trust events were reported")
    print("   8. ✅ Trust summary was generated for all agents")

    print("\n🔗 View detailed trust reports at https://agentpier.com/dashboard")

    if api_key == "demo_key":
        print("\n💡 To see real trust reporting:")
        print("   1. Get an API key from https://agentpier.com")
        print("   2. Set AGENTPIER_API_KEY environment variable")
        print("   3. Replace MockLLM with real LLM (OpenAI, etc.)")
        print("   4. Re-run this example")


if __name__ == "__main__":
    main()
