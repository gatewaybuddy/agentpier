# AgentPier CrewAI Integration

Trust scoring integration for CrewAI agents and workflows. Automatically report task outcomes to build agent reputation over time, and verify agent trust levels before delegation.

## Features

- **Trust Tools**: CrewAI agents can check trust scores of other agents mid-workflow
- **Automatic Reporting**: Callbacks that report task completion/failure as trust signals
- **Agent Verification**: Verify trust scores meet thresholds before workflow execution  
- **Auto-Registration**: Automatically register new agents in AgentPier trust system

## Installation

```bash
pip install agentpier-crewai
```

> ⚠️ **Installation Time Notice**: First-time installation may take 5+ minutes due to large dependencies (ONNX runtime, PyArrow). This is expected behavior for ML-enabled packages.

## Quick Start

### 1. Basic Trust Monitoring

```python
from crewai import Agent, Task, Crew
from agentpier_crewai import AgentPierMonitor

# Initialize monitor with your API key
monitor = AgentPierMonitor(api_key="ap_live_your_key_here")

# Create your agents and tasks
researcher = Agent(role="researcher", goal="Research topics")
writer = Agent(role="writer", goal="Write content")

research_task = Task(description="Research AI trends", agent=researcher)
writing_task = Task(description="Write blog post", agent=writer)

# Create crew with trust monitoring
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    callbacks=[monitor.on_task_complete, monitor.on_task_fail]
)

# Run with automatic trust reporting
result = crew.kickoff()
```

### 2. Trust Verification Before Execution

```python
from agentpier_crewai import TrustVerifier

# Verify all agents meet minimum trust requirements
verifier = TrustVerifier(api_key="ap_live_your_key_here", min_score=60)

if verifier.check_all(crew.agents):
    print("✅ All agents verified - starting workflow")
    result = crew.kickoff()
else:
    print("❌ Trust verification failed - review agent credentials")
```

### 3. Mid-Workflow Trust Checking

```python
from agentpier_crewai import TrustScoreChecker

# Create trust checking tool for agents to use
trust_checker = TrustScoreChecker(api_key="ap_live_your_key_here")

# Add to agent's tools
supervisor = Agent(
    role="supervisor",
    goal="Delegate tasks to trusted agents",
    tools=[trust_checker]
)
```

## Configuration

### Agent ID Mapping

By default, agent IDs are derived from their role names. You can provide explicit mappings:

```python
monitor = AgentPierMonitor(
    api_key="ap_live_your_key_here",
    agent_mapping={
        "Research Specialist": "researcher_v2",
        "Content Writer": "writer_pro"
    }
)
```

### Custom Trust Thresholds

```python
# Different thresholds for different workflows
verifier = TrustVerifier(
    api_key="ap_live_your_key_here",
    min_score=80  # Higher threshold for critical tasks
)
```

### Auto-Registration

Control whether new agents are automatically registered:

```python
monitor = AgentPierMonitor(
    api_key="ap_live_your_key_here",
    auto_register=False  # Require manual registration
)
```

## API Reference

### AgentPierMonitor

Main class for workflow monitoring.

```python
monitor = AgentPierMonitor(
    api_key: str,                           # Required: AgentPier API key
    base_url: str = "...",                  # Optional: API base URL
    agent_mapping: Dict[str, str] = None,   # Optional: Agent name to ID mapping
    auto_register: bool = True              # Optional: Auto-register new agents
)

# Callback methods for CrewAI
monitor.on_task_complete(task, agent, result)  # Report successful completion
monitor.on_task_fail(task, agent, error)      # Report task failure
monitor.on_task_start(task, agent)            # Optional: Report task start
```

### TrustVerifier

Verify agent trust levels before workflow execution.

```python
verifier = TrustVerifier(
    api_key: str,                           # Required: AgentPier API key
    min_score: float = 60.0,               # Optional: Minimum trust score
    base_url: str = "..."                  # Optional: API base URL
)

# Verification methods
verifier.check_agent(agent_id: str) -> Dict         # Check single agent
verifier.check_agents(agent_ids: List[str]) -> Dict # Check multiple agents  
verifier.check_crew(crew) -> Dict                   # Check entire crew
verifier.check_all(crew_or_agents) -> bool          # Simple pass/fail check
```

### TrustScoreChecker (Tool)

CrewAI tool for checking trust scores during workflow execution.

```python
checker = TrustScoreChecker(api_key="ap_live_your_key_here")

# Add to agent tools
agent = Agent(
    role="supervisor",
    tools=[checker]
)
```

### AgentTrustVerifier (Tool)

CrewAI tool for verifying multiple agents meet trust thresholds.

```python
verifier_tool = AgentTrustVerifier(api_key="ap_live_your_key_here")

# Add to agent tools  
agent = Agent(
    role="project_manager", 
    tools=[verifier_tool]
)
```

## Advanced Usage

### Custom Callbacks

You can create custom callbacks by extending `AgentPierTaskCallback`:

```python
from agentpier_crewai.callbacks import AgentPierTaskCallback

class CustomCallback(AgentPierTaskCallback):
    def on_task_complete(self, task, agent, result=None, **kwargs):
        # Custom logic before reporting
        print(f"Task completed by {agent.role}")
        
        # Call parent to report to AgentPier
        super().on_task_complete(task, agent, result, **kwargs)
        
        # Custom logic after reporting
        self.log_to_custom_system(task, agent, result)

callback = CustomCallback(api_key="ap_live_your_key_here")
```

### Error Handling

The integration handles common error scenarios gracefully:

- **Network errors**: Logged but don't interrupt workflow
- **API errors**: Graceful degradation with error messages
- **Agent not found**: Option to auto-register or fail gracefully
- **Invalid trust scores**: Clear error messages and recommendations

### Integration with CrewAI Tracing

Works alongside CrewAI's built-in tracing:

```python
crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2], 
    tracing=True,  # Enable CrewAI tracing
    callbacks=[monitor.on_task_complete, monitor.on_task_fail]  # Add AgentPier
)
```

## Trust Score Interpretation

- **0-20**: Unverified - New or unreliable agents
- **21-40**: Basic - Some positive history  
- **41-60**: Verified - Consistent performance
- **61-80**: Certified - High reliability
- **81-100**: Elite - Exceptional track record

## Troubleshooting

### Common Issues

1. **Agent not found**: Check agent ID mapping or enable auto-registration
2. **API key errors**: Verify key is valid and has sufficient permissions
3. **Network timeouts**: Check firewall settings and network connectivity
4. **Rate limiting**: Reduce frequency of trust checks or upgrade API plan

### Debugging

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

monitor = AgentPierMonitor(api_key="ap_live_your_key_here")
```

## Contributing

Contributions are welcome! Please see the [main AgentPier repository](https://github.com/gatewaybuddy/agentpier) for guidelines.

## License

Apache 2.0 - see [LICENSE](../../LICENSE) for details.