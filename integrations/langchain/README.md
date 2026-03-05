# AgentPier LangChain Integration

Trust scoring integration for LangChain chains and agents. Automatically report chain/tool execution as trust signals and verify agent trust levels during workflows.

## Features

- **Automatic Trust Reporting**: Callbacks that monitor chain/tool execution and report outcomes
- **Trust Verification Tools**: LangChain tools for checking agent trust scores during execution
- **Chain Monitoring**: High-level utilities for trust-enabled LangChain workflows
- **Auto-Registration**: Automatically register new agents in AgentPier trust system
- **Flexible Configuration**: Control what events are tracked and how agents are mapped

## Installation

```bash
pip install agentpier-langchain
```

## Quick Start

### 1. Basic Chain Monitoring

```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from agentpier_langchain import ChainMonitor

# Initialize monitor
monitor = ChainMonitor(api_key="ap_live_your_key_here")

# Create chain with automatic trust monitoring
llm = OpenAI()
prompt = PromptTemplate(template="Summarize: {text}", input_variables=["text"])

chain = LLMChain(
    llm=llm,
    prompt=prompt,
    callbacks=[monitor.get_callback()]  # Add trust monitoring
)

# Run chain - outcomes automatically reported to AgentPier
result = chain.run(text="Long article to summarize...")
```

### 2. Trust Verification Tools

```python
from agentpier_langchain import TrustScoreTool, AgentVerificationTool

# Create tools for agents to use
trust_checker = TrustScoreTool(api_key="ap_live_your_key_here")
verifier = AgentVerificationTool(api_key="ap_live_your_key_here")

# Add to agent toolkit
from langchain.agents import initialize_agent, Tool

tools = [
    Tool(
        name="Check Trust Score",
        func=trust_checker._run,
        description="Check trust score of an agent before delegation"
    ),
    Tool(
        name="Verify Agents",
        func=verifier._run,
        description="Verify multiple agents meet trust requirements"
    )
]

agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
```

### 3. Advanced Monitoring with Custom Mapping

```python
monitor = ChainMonitor(
    api_key="ap_live_your_key_here",
    agent_mapping={
        "summary_chain": "summarizer_v2",
        "analysis_tool": "data_analyst",
        "research_chain": "researcher_pro"
    },
    auto_register=True,
    track_chains=True,
    track_tools=True,
    track_llm_calls=False  # Usually too verbose
)

# Verify agents before starting workflow
verification = monitor.verify_multiple_agents(
    ["summarizer_v2", "data_analyst"], 
    min_score=70.0
)

if verification["all_verified"]:
    print("✅ All agents verified - starting workflow")
    # Proceed with chains...
else:
    print("❌ Some agents don't meet requirements")
    for result in verification["results"]:
        if not result["verified"]:
            print(f"- {result['agent_id']}: {result['reason']}")
```

## Configuration

### Callback Configuration

Control what events are tracked:

```python
from agentpier_langchain import AgentPierCallback

callback = AgentPierCallback(
    api_key="ap_live_your_key_here",
    track_chains=True,      # Monitor chain execution
    track_tools=True,       # Monitor tool usage
    track_llm_calls=False,  # Usually too verbose
    auto_register=True      # Auto-register new agents
)
```

### Agent ID Mapping

Map LangChain component names to AgentPier agent IDs:

```python
agent_mapping = {
    "research_chain": "researcher_v1",
    "summarization_chain": "summarizer_v1", 
    "calculator": "math_tool_v2"
}

monitor = ChainMonitor(
    api_key="ap_live_your_key_here",
    agent_mapping=agent_mapping
)
```

### Trust Thresholds

Set different trust requirements for different workflows:

```python
# High-security workflow
high_security_monitor = ChainMonitor(api_key="ap_live_your_key_here")
result = high_security_monitor.verify_multiple_agents(
    ["critical_agent_1", "critical_agent_2"], 
    min_score=80.0
)

# Development/testing workflow  
dev_monitor = ChainMonitor(api_key="ap_live_your_key_here")
result = dev_monitor.verify_multiple_agents(
    ["test_agent_1", "test_agent_2"],
    min_score=30.0
)
```

## API Reference

### ChainMonitor

Main class for LangChain workflow monitoring.

```python
monitor = ChainMonitor(
    api_key: str,                           # Required: AgentPier API key
    base_url: str = "...",                  # Optional: API base URL
    agent_mapping: Dict[str, str] = None,   # Optional: Component to agent ID mapping
    auto_register: bool = True,             # Optional: Auto-register new agents
    track_chains: bool = True,              # Optional: Track chain execution
    track_tools: bool = True,               # Optional: Track tool usage
    track_llm_calls: bool = False           # Optional: Track LLM calls (verbose)
)

# Methods
monitor.get_callback() -> AgentPierCallback           # Get callback for chains
monitor.verify_agent_trust(agent_id, min_score) -> Dict  # Verify single agent
monitor.verify_multiple_agents(agent_ids, min_score) -> Dict  # Verify multiple agents
monitor.create_monitored_chain(chain_class, *args, **kwargs)  # Create chain with monitoring
monitor.report_custom_event(agent_id, event_type, outcome, details, metadata) -> bool
```

### AgentPierCallback

LangChain callback for automatic trust reporting.

```python
callback = AgentPierCallback(
    api_key: str,                           # Required: AgentPier API key
    base_url: str = "...",                  # Optional: API base URL
    agent_mapping: Dict[str, str] = None,   # Optional: Component to agent ID mapping  
    auto_register: bool = True,             # Optional: Auto-register new agents
    track_chains: bool = True,              # Optional: Track chain execution
    track_tools: bool = True,               # Optional: Track tool usage
    track_llm_calls: bool = False           # Optional: Track LLM calls
)

# Add to any LangChain component
chain = SomeChain(..., callbacks=[callback])
agent = SomeAgent(..., callbacks=[callback])
```

### TrustScoreTool

LangChain tool for checking agent trust scores.

```python
tool = TrustScoreTool(api_key="ap_live_your_key_here")

# Use with LangChain agents
from langchain.agents import Tool
trust_tool = Tool(
    name="check_trust_score",
    func=tool._run,
    description="Check agent trust score before delegation"
)
```

### AgentVerificationTool

LangChain tool for verifying multiple agents.

```python
tool = AgentVerificationTool(api_key="ap_live_your_key_here")

# Use with LangChain agents
verification_tool = Tool(
    name="verify_agents", 
    func=tool._run,
    description="Verify multiple agents meet trust requirements"
)
```

### TrustScoreFunction

Function-based interface for OpenAI Functions calling.

```python
from agentpier_langchain.tools import TrustScoreFunction

trust_func = TrustScoreFunction(api_key="ap_live_your_key_here")

# Get OpenAI function schema
schema = trust_func.function_schema

# Call function
result = trust_func.call("agent_id_here")
```

## Event Types and Outcomes

### Event Types
- `task_completion`: Chain or tool execution
- `review`: Manual review or validation
- `certification`: Formal certification events  
- `violation`: Safety or policy violations
- `transaction`: Commercial transactions

### Outcomes
- `success`: Successful completion
- `failure`: Failed execution
- `partial`: Partial completion
- `cancelled`: Cancelled execution

## Integration Patterns

### With LangChain Agents

```python
from langchain.agents import initialize_agent
from langchain.tools import Tool

# Create agent with trust tools
trust_tool = TrustScoreTool(api_key="ap_live_your_key_here")
monitor = ChainMonitor(api_key="ap_live_your_key_here")

tools = [
    Tool(name="check_trust", func=trust_tool._run, description="Check agent trust"),
    # ... other tools
]

agent = initialize_agent(
    tools, 
    llm,
    agent="zero-shot-react-description",
    callbacks=[monitor.get_callback()]
)
```

### With Custom Chains

```python
from langchain.chains.base import Chain

class CustomChain(Chain):
    def _call(self, inputs):
        # Your chain logic here
        result = self.process(inputs)
        
        # Manual trust reporting if needed
        monitor.report_custom_event(
            "custom_chain_v1",
            "task_completion", 
            "success",
            "Custom chain completed successfully"
        )
        
        return result

# Use with monitoring
chain = CustomChain(callbacks=[monitor.get_callback()])
```

### With Sequential Chains

```python
from langchain.chains import SequentialChain

# Create individual chains
chain1 = LLMChain(llm=llm, prompt=prompt1, output_key="summary")
chain2 = LLMChain(llm=llm, prompt=prompt2, output_key="analysis")

# Combine with monitoring
overall_chain = SequentialChain(
    chains=[chain1, chain2],
    input_variables=["text"],
    output_variables=["summary", "analysis"],
    callbacks=[monitor.get_callback()]
)
```

## Error Handling

The integration handles errors gracefully:

- **Network errors**: Logged but don't interrupt workflow execution
- **API errors**: Clear error messages with status codes
- **Agent not found**: Option to auto-register or continue without reporting
- **Rate limiting**: Respects API rate limits and provides clear feedback

## Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# The callback will log detailed information about trust reporting
callback = AgentPierCallback(api_key="ap_live_your_key_here")
```

## Trust Score Interpretation

- **0-20**: Unverified - New or unreliable agents
- **21-40**: Basic - Some positive history
- **41-60**: Verified - Consistent performance  
- **61-80**: Certified - High reliability
- **81-100**: Elite - Exceptional track record

## Best Practices

1. **Start with high-level monitoring**: Use `ChainMonitor` for simple setups
2. **Use agent mapping**: Map meaningful names to consistent agent IDs
3. **Set appropriate thresholds**: Different workflows need different trust levels
4. **Monitor selectively**: Track chains and tools, skip LLM calls unless needed
5. **Handle failures gracefully**: Don't let trust reporting break your workflow
6. **Verify before delegation**: Check trust scores before assigning critical tasks

## Contributing

Contributions welcome! See the [main AgentPier repository](https://github.com/gatewaybuddy/agentpier) for guidelines.

## License

Apache 2.0 - see [LICENSE](../../LICENSE) for details.