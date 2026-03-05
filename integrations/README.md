# AgentPier Integrations

This directory contains integrations for popular AI agent frameworks, enabling seamless trust scoring and reputation management across different platforms.

## Available Integrations

### CrewAI Integration (`crewai/`)
Trust scoring for CrewAI multi-agent workflows.

**Features:**
- ✅ Automatic task completion/failure reporting
- ✅ Trust verification before crew execution  
- ✅ Mid-workflow trust checking tools
- ✅ Agent auto-registration
- ✅ Configurable thresholds and mappings

**Quick Start:**
```python
from crewai import Agent, Task, Crew
from agentpier_crewai import AgentPierMonitor, TrustVerifier

monitor = AgentPierMonitor(api_key="ap_live_xxx")
verifier = TrustVerifier(api_key="ap_live_xxx", min_score=60)

# Verify trust before execution
if verifier.check_all(crew.agents):
    crew = Crew(
        agents=[agent1, agent2],
        tasks=[task1, task2],
        callbacks=[monitor.on_task_complete, monitor.on_task_fail]
    )
    result = crew.kickoff()
```

### LangChain Integration (`langchain/`)  
Trust scoring for LangChain chains and agents.

**Features:**
- ✅ Chain/tool execution monitoring via callbacks
- ✅ Trust verification tools for agents
- ✅ OpenAI Functions support
- ✅ Flexible event tracking configuration
- ✅ Error handling and graceful degradation

**Quick Start:**
```python
from langchain.chains import LLMChain
from agentpier_langchain import ChainMonitor, TrustScoreTool

monitor = ChainMonitor(api_key="ap_live_xxx")
trust_tool = TrustScoreTool(api_key="ap_live_xxx")

chain = LLMChain(
    llm=llm, 
    prompt=prompt,
    callbacks=[monitor.get_callback()]
)

# Add trust tools to agents
tools = [trust_tool, ...]
agent = initialize_agent(tools, llm, callbacks=[monitor.get_callback()])
```

## Common Concepts

### Trust Events
Both integrations report standardized trust events:
- **Event Types**: `task_completion`, `review`, `certification`, `violation`, `transaction`
- **Outcomes**: `success`, `failure`, `partial`, `cancelled`
- **Metadata**: Duration, error details, performance metrics

### Agent Registration
Automatic agent registration with configurable mapping:
```python
# Map framework-specific names to AgentPier agent IDs
agent_mapping = {
    "Research Specialist": "researcher_v1",
    "Content Writer": "writer_v1"
}
```

### Trust Verification
Pre-execution verification with configurable thresholds:
```python
# Different thresholds for different workflows
verifier = TrustVerifier(min_score=80.0)  # High-security
verifier = TrustVerifier(min_score=40.0)  # Development
```

## Installation

Each integration is packaged separately:

```bash
# CrewAI integration
pip install agentpier-crewai

# LangChain integration  
pip install agentpier-langchain

# Both
pip install agentpier-crewai agentpier-langchain
```

## Architecture

```
AgentPier API
     ↑
     │ Trust Events & Queries
     │
┌────┴─────────────────────┐
│   Integration Layer      │
├─────────────┬────────────┤
│  CrewAI     │ LangChain  │
│  Plugin     │ Plugin     │
├─────────────┼────────────┤
│ • Callbacks │ • Callbacks│
│ • Tools     │ • Tools    │
│ • Monitor   │ • Monitor  │
└─────────────┴────────────┘
     ↑              ↑
     │              │
┌────┴─────┐  ┌────┴─────┐
│ CrewAI   │  │LangChain │
│Framework │  │Framework │
└──────────┘  └──────────┘
```

### Integration Components

1. **Callbacks**: Monitor framework execution and report outcomes
2. **Tools**: Allow agents to check trust scores during execution  
3. **Monitors**: High-level utilities for setup and verification
4. **Auto-registration**: Seamlessly onboard new agents

### Trust Score Flow

1. **Pre-execution**: Verify agents meet minimum trust requirements
2. **During execution**: Agents can check trust scores of collaborators
3. **Post-execution**: Task outcomes automatically update trust scores
4. **Continuous**: Trust scores evolve based on performance history

## Configuration

### API Authentication
```bash
export AGENTPIER_API_KEY="ap_live_your_key_here"
```

### Framework-Specific Settings

**CrewAI:**
```python
monitor = AgentPierMonitor(
    api_key=api_key,
    agent_mapping={"Agent Name": "agent_id"},
    auto_register=True
)
```

**LangChain:**
```python
monitor = ChainMonitor(
    api_key=api_key,
    track_chains=True,
    track_tools=True,
    track_llm_calls=False  # Usually too verbose
)
```

## Examples

- **CrewAI**: `crewai/examples/trust_scored_crew.py`
- **LangChain**: `langchain/examples/trust_scored_chains.py`

Both examples demonstrate:
- Trust verification before execution
- Automatic trust reporting during execution
- Trust checking tools for agents
- Error handling and graceful degradation

## Best Practices

### 1. Start Simple
Begin with basic monitoring and add features as needed:
```python
# Start here
monitor = AgentPierMonitor(api_key=api_key)
crew = Crew(..., callbacks=[monitor.on_task_complete])

# Add later
verifier = TrustVerifier(api_key=api_key, min_score=70)
trust_tools = [TrustScoreChecker(api_key=api_key)]
```

### 2. Use Meaningful Agent IDs
Map framework names to consistent, meaningful agent IDs:
```python
agent_mapping = {
    "Senior Research Agent": "researcher_v2",
    "Content Writer Pro": "writer_pro_v1"
}
```

### 3. Set Appropriate Thresholds
Different workflows need different trust levels:
- **Development/Testing**: 20-40 minimum score
- **Production**: 50-70 minimum score  
- **Critical/Financial**: 70+ minimum score

### 4. Handle Errors Gracefully
Trust scoring should enhance, not break, your workflows:
```python
try:
    if verifier.check_all(agents):
        result = crew.kickoff()
    else:
        print("Trust verification failed, but continuing...")
        result = crew.kickoff()  # Continue anyway
except Exception as e:
    print(f"Trust error (continuing): {e}")
    result = crew.kickoff()
```

### 5. Monitor Selectively  
Track meaningful events without overwhelming the system:
- ✅ Track task/chain completion
- ✅ Track tool usage
- ❌ Avoid tracking every LLM call (too verbose)

## Troubleshooting

### Common Issues

1. **"Agent not found"**
   - Enable auto-registration: `auto_register=True`
   - Check agent ID mapping
   - Manually register agents via AgentPier dashboard

2. **"API key invalid"**
   - Verify API key is correct
   - Check environment variable: `echo $AGENTPIER_API_KEY`
   - Generate new key at https://agentpier.com/dashboard

3. **"Rate limit exceeded"**
   - Reduce frequency of trust checks
   - Upgrade API plan if needed
   - Cache trust scores locally for repeated checks

4. **"Network timeout"**
   - Check internet connectivity
   - Verify firewall settings
   - Increase timeout in requests

### Debugging

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

We welcome contributions! Areas for expansion:

### Framework Support
- **AutoGen**: Multi-agent conversation framework
- **LlamaIndex**: RAG and data framework integration
- **Haystack**: NLP pipeline framework
- **Microsoft Semantic Kernel**: Cross-platform agent framework

### Features
- **Batch reporting**: Reduce API calls for high-volume workflows
- **Local caching**: Cache trust scores to reduce latency
- **Advanced metrics**: Track more granular performance data
- **Trust analytics**: Rich dashboards and reporting

### Testing
- **Integration tests**: Test against real frameworks
- **Performance tests**: Ensure minimal overhead
- **Error simulation**: Test failure scenarios

## License

Apache 2.0 - see [LICENSE](../LICENSE) for details.

## Support

- **Documentation**: https://docs.agentpier.com
- **Issues**: https://github.com/gatewaybuddy/agentpier/issues
- **Discussions**: https://github.com/gatewaybuddy/agentpier/discussions
- **Email**: support@agentpier.com