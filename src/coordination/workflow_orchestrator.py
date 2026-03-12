"""
AgentPier V3 Multi-Agent Coordination Framework POC
Workflow Orchestrator - Unified API for multi-agent task coordination and workflow management
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from .agent_registry import AgentRegistry, AgentIdentity, CapabilityType
from .trust_propagation import TrustPropagationEngine, TrustEventType
from .mcp_protocol import AgentCoordinationProtocol, MCPTransport, TaskDelegation, TaskResult

class WorkflowStatus(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class WorkflowTask:
    """Individual task within a workflow"""
    task_id: str
    name: str
    description: str
    required_capabilities: List[str]
    parameters: Dict
    dependencies: List[str]  # Task IDs this task depends on
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    estimated_duration: Optional[int] = None  # minutes
    actual_start_time: Optional[datetime] = None
    actual_completion_time: Optional[datetime] = None
    result: Optional[Dict] = None
    error_message: Optional[str] = None

@dataclass
class Workflow:
    """Multi-agent workflow definition"""
    workflow_id: str
    name: str
    description: str
    coordinator_agent: str
    tasks: List[WorkflowTask]
    workflow_type: str  # "sequential", "parallel", "dag"
    status: WorkflowStatus
    created_time: datetime
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    trust_requirements: Optional[Dict] = None
    metadata: Optional[Dict] = None

@dataclass
class WorkflowExecution:
    """Runtime execution state of a workflow"""
    workflow: Workflow
    execution_id: str
    participating_agents: List[str]
    task_assignments: Dict[str, str]  # task_id -> agent_id
    trust_analysis: Dict
    execution_log: List[Dict]
    performance_metrics: Dict

class WorkflowOrchestrator:
    """Central orchestrator for multi-agent workflows"""
    
    def __init__(self, 
                 agent_registry: AgentRegistry,
                 trust_engine: TrustPropagationEngine,
                 coordination_protocol: AgentCoordinationProtocol,
                 storage_path: str = "data/workflows.json"):
        self.registry = agent_registry
        self.trust_engine = trust_engine
        self.protocol = coordination_protocol
        self.storage_path = storage_path
        
        # Workflow storage
        self.workflows: Dict[str, Workflow] = {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        
        # Scheduling and optimization
        self.scheduling_algorithms = {
            'trust_optimized': self._schedule_by_trust,
            'capability_optimized': self._schedule_by_capability,
            'load_balanced': self._schedule_load_balanced,
            'deadline_optimized': self._schedule_by_deadline
        }
        
        self.load_workflows()
    
    def create_workflow(self, 
                       name: str,
                       description: str,
                       coordinator_agent: str,
                       tasks: List[Dict],
                       workflow_type: str = "dag",
                       trust_requirements: Optional[Dict] = None,
                       metadata: Optional[Dict] = None) -> str:
        """Create a new multi-agent workflow"""
        
        workflow_id = str(uuid.uuid4())
        
        # Convert task dictionaries to WorkflowTask objects
        workflow_tasks = []
        for task_data in tasks:
            task = WorkflowTask(
                task_id=task_data.get('task_id', str(uuid.uuid4())),
                name=task_data['name'],
                description=task_data['description'],
                required_capabilities=task_data['required_capabilities'],
                parameters=task_data.get('parameters', {}),
                dependencies=task_data.get('dependencies', []),
                priority=task_data.get('priority', 5),
                estimated_duration=task_data.get('estimated_duration')
            )
            workflow_tasks.append(task)
        
        # Create workflow
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            coordinator_agent=coordinator_agent,
            tasks=workflow_tasks,
            workflow_type=workflow_type,
            status=WorkflowStatus.PLANNING,
            created_time=datetime.now(timezone.utc),
            trust_requirements=trust_requirements or {},
            metadata=metadata or {}
        )
        
        self.workflows[workflow_id] = workflow
        self.save_workflows()
        
        return workflow_id
    
    async def execute_workflow(self, 
                              workflow_id: str,
                              scheduling_algorithm: str = "trust_optimized") -> Optional[str]:
        """Execute a workflow using specified scheduling algorithm"""
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None
        
        # Plan execution
        execution_plan = await self._plan_workflow_execution(workflow, scheduling_algorithm)
        if not execution_plan:
            workflow.status = WorkflowStatus.FAILED
            self.save_workflows()
            return None
        
        # Start execution
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            workflow=workflow,
            execution_id=execution_id,
            participating_agents=list(set(execution_plan['task_assignments'].values())),
            task_assignments=execution_plan['task_assignments'],
            trust_analysis=execution_plan['trust_analysis'],
            execution_log=[],
            performance_metrics={}
        )
        
        self.active_executions[execution_id] = execution
        workflow.status = WorkflowStatus.EXECUTING
        workflow.start_time = datetime.now(timezone.utc)
        
        # Start workflow execution
        asyncio.create_task(self._execute_workflow_tasks(execution))
        
        return execution_id
    
    async def _plan_workflow_execution(self, 
                                      workflow: Workflow,
                                      scheduling_algorithm: str) -> Optional[Dict]:
        """Plan workflow execution with agent assignment and trust verification"""
        
        scheduler = self.scheduling_algorithms.get(scheduling_algorithm)
        if not scheduler:
            return None
        
        # Get agent assignments
        task_assignments = await scheduler(workflow.tasks)
        if not task_assignments:
            return None
        
        # Verify trust relationships for all assignments
        participating_agents = [workflow.coordinator_agent] + list(set(task_assignments.values()))
        trust_analysis = self.trust_engine.calculate_workflow_trust(
            participating_agents,
            workflow.workflow_type
        )
        
        if 'error' in trust_analysis or trust_analysis['recommendation'] != 'APPROVED':
            return None
        
        return {
            'task_assignments': task_assignments,
            'trust_analysis': trust_analysis,
            'participating_agents': participating_agents,
            'execution_plan': self._generate_execution_order(workflow.tasks, workflow.workflow_type)
        }
    
    async def _schedule_by_trust(self, tasks: List[WorkflowTask]) -> Dict[str, str]:
        """Schedule tasks based on trust optimization"""
        assignments = {}
        
        for task in tasks:
            # Find agents with required capabilities
            best_agent = None
            best_score = 0
            
            for capability_name in task.required_capabilities:
                # Find capability type
                capability_type = None
                for cap_type in CapabilityType:
                    if capability_name in cap_type.value:
                        capability_type = cap_type
                        break
                
                if capability_type:
                    candidates = self.registry.find_agents_by_capability(capability_type)
                    
                    for agent in candidates:
                        # Calculate combined score (capability + trust)
                        capability_confidence = max(
                            cap.confidence for cap in agent.capabilities 
                            if cap.name == capability_name
                        )
                        
                        # Get trust score with coordinator
                        trust_score = self.trust_engine.get_trust_score(
                            self.protocol.agent_id, agent.agent_id
                        )
                        trust_value = trust_score.overall_score if trust_score else 0.5
                        
                        combined_score = (capability_confidence * 0.6) + (trust_value * 0.4)
                        
                        if combined_score > best_score:
                            best_score = combined_score
                            best_agent = agent.agent_id
            
            if best_agent:
                assignments[task.task_id] = best_agent
        
        return assignments
    
    async def _schedule_by_capability(self, tasks: List[WorkflowTask]) -> Dict[str, str]:
        """Schedule tasks based on capability optimization"""
        assignments = {}
        
        for task in tasks:
            best_agent = None
            best_confidence = 0
            
            for capability_name in task.required_capabilities:
                capability_type = None
                for cap_type in CapabilityType:
                    if capability_name in cap_type.value:
                        capability_type = cap_type
                        break
                
                if capability_type:
                    candidates = self.registry.find_agents_by_capability(capability_type)
                    
                    for agent in candidates:
                        capability_confidence = max(
                            cap.confidence for cap in agent.capabilities 
                            if cap.name == capability_name
                        )
                        
                        if capability_confidence > best_confidence:
                            best_confidence = capability_confidence
                            best_agent = agent.agent_id
            
            if best_agent:
                assignments[task.task_id] = best_agent
        
        return assignments
    
    async def _schedule_load_balanced(self, tasks: List[WorkflowTask]) -> Dict[str, str]:
        """Schedule tasks with load balancing across agents"""
        assignments = {}
        agent_workload = {}
        
        # Get all available agents
        all_agents = [agent.agent_id for agent in self.registry.agents.values()]
        
        for agent_id in all_agents:
            agent_workload[agent_id] = 0
        
        # Sort tasks by priority
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        for task in sorted_tasks:
            best_agent = None
            best_score = -1
            
            for capability_name in task.required_capabilities:
                capability_type = None
                for cap_type in CapabilityType:
                    if capability_name in cap_type.value:
                        capability_type = cap_type
                        break
                
                if capability_type:
                    candidates = self.registry.find_agents_by_capability(capability_type)
                    
                    for agent in candidates:
                        capability_confidence = max(
                            cap.confidence for cap in agent.capabilities 
                            if cap.name == capability_name
                        )
                        
                        # Balance score with current workload
                        workload_penalty = agent_workload.get(agent.agent_id, 0) * 0.2
                        balanced_score = capability_confidence - workload_penalty
                        
                        if balanced_score > best_score:
                            best_score = balanced_score
                            best_agent = agent.agent_id
            
            if best_agent:
                assignments[task.task_id] = best_agent
                agent_workload[best_agent] += task.estimated_duration or 30
        
        return assignments
    
    async def _schedule_by_deadline(self, tasks: List[WorkflowTask]) -> Dict[str, str]:
        """Schedule tasks optimized for deadline constraints"""
        # Sort by priority and estimated duration
        sorted_tasks = sorted(
            tasks, 
            key=lambda t: (t.priority, -(t.estimated_duration or 30)),
            reverse=True
        )
        
        return await self._schedule_by_capability(sorted_tasks)
    
    def _generate_execution_order(self, tasks: List[WorkflowTask], workflow_type: str) -> List[List[str]]:
        """Generate execution order based on dependencies and workflow type"""
        
        if workflow_type == "sequential":
            # Execute tasks in order
            return [[task.task_id] for task in tasks]
        
        elif workflow_type == "parallel":
            # Execute all tasks in parallel (if no dependencies)
            return [[task.task_id for task in tasks]]
        
        elif workflow_type == "dag":
            # Topological sort based on dependencies
            return self._topological_sort(tasks)
        
        else:
            # Default to sequential
            return [[task.task_id] for task in tasks]
    
    def _topological_sort(self, tasks: List[WorkflowTask]) -> List[List[str]]:
        """Perform topological sort on tasks based on dependencies"""
        
        # Create dependency graph
        task_dict = {task.task_id: task for task in tasks}
        in_degree = {task.task_id: 0 for task in tasks}
        
        for task in tasks:
            for dep in task.dependencies:
                if dep in in_degree:
                    in_degree[task.task_id] += 1
        
        # Find tasks with no dependencies
        ready_queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while ready_queue:
            current_batch = ready_queue.copy()
            ready_queue = []
            execution_order.append(current_batch)
            
            # Remove current batch from graph and update dependencies
            for task_id in current_batch:
                # Find tasks that depend on this one
                for dependent_task in tasks:
                    if task_id in dependent_task.dependencies:
                        in_degree[dependent_task.task_id] -= 1
                        if in_degree[dependent_task.task_id] == 0:
                            ready_queue.append(dependent_task.task_id)
        
        return execution_order
    
    async def _execute_workflow_tasks(self, execution: WorkflowExecution):
        """Execute workflow tasks according to execution plan"""
        
        workflow = execution.workflow
        execution_plan = execution.trust_analysis.get('execution_plan', [])
        
        try:
            for batch in execution_plan:
                # Execute batch of tasks in parallel
                batch_tasks = []
                
                for task_id in batch:
                    task = next(t for t in workflow.tasks if t.task_id == task_id)
                    assigned_agent = execution.task_assignments.get(task_id)
                    
                    if assigned_agent:
                        batch_tasks.append(self._execute_single_task(task, assigned_agent, execution))
                
                # Wait for batch completion
                if batch_tasks:
                    await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Check if workflow completed successfully
            all_completed = all(
                task.status == TaskStatus.COMPLETED 
                for task in workflow.tasks
            )
            
            if all_completed:
                workflow.status = WorkflowStatus.COMPLETED
                workflow.completion_time = datetime.now(timezone.utc)
                
                # Record positive trust events for all participants
                for agent_id in execution.participating_agents:
                    if agent_id != workflow.coordinator_agent:
                        self.trust_engine.record_trust_event(
                            workflow.coordinator_agent, agent_id,
                            TrustEventType.COLLABORATION_SUCCESS,
                            0.2,
                            {'workflow_id': workflow.workflow_id, 'workflow_name': workflow.name}
                        )
            else:
                workflow.status = WorkflowStatus.FAILED
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            execution.execution_log.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event': 'workflow_error',
                'error': str(e)
            })
        
        finally:
            self.save_workflows()
    
    async def _execute_single_task(self, 
                                  task: WorkflowTask, 
                                  assigned_agent: str,
                                  execution: WorkflowExecution):
        """Execute a single task"""
        
        try:
            task.status = TaskStatus.ASSIGNED
            task.actual_start_time = datetime.now(timezone.utc)
            
            execution.execution_log.append({
                'timestamp': task.actual_start_time.isoformat(),
                'event': 'task_started',
                'task_id': task.task_id,
                'assigned_agent': assigned_agent
            })
            
            # Delegate task to assigned agent
            task_id = await self.protocol.delegate_task(
                target_agent=assigned_agent,
                task_type=task.name,
                task_description=task.description,
                parameters=task.parameters,
                required_capabilities=task.required_capabilities,
                priority=task.priority
            )
            
            if task_id:
                task.status = TaskStatus.IN_PROGRESS
                
                # Wait for completion (in real implementation, this would be event-driven)
                # For now, simulate with delay
                await asyncio.sleep(2)
                
                # Mark as completed (placeholder)
                task.status = TaskStatus.COMPLETED
                task.actual_completion_time = datetime.now(timezone.utc)
                task.result = {'status': 'completed', 'simulated': True}
                
                execution.execution_log.append({
                    'timestamp': task.actual_completion_time.isoformat(),
                    'event': 'task_completed',
                    'task_id': task.task_id,
                    'assigned_agent': assigned_agent
                })
                
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "Failed to delegate task"
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            
            execution.execution_log.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event': 'task_failed',
                'task_id': task.task_id,
                'error': str(e)
            })
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID"""
        return self.workflows.get(workflow_id)
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution by ID"""
        return self.active_executions.get(execution_id)
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get detailed workflow status"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None
        
        # Find active execution
        active_execution = None
        for execution in self.active_executions.values():
            if execution.workflow.workflow_id == workflow_id:
                active_execution = execution
                break
        
        task_summary = {}
        for status in TaskStatus:
            task_summary[status.value] = len([
                t for t in workflow.tasks if t.status == status
            ])
        
        return {
            'workflow_id': workflow.workflow_id,
            'name': workflow.name,
            'status': workflow.status.value,
            'created_time': workflow.created_time.isoformat(),
            'start_time': workflow.start_time.isoformat() if workflow.start_time else None,
            'completion_time': workflow.completion_time.isoformat() if workflow.completion_time else None,
            'total_tasks': len(workflow.tasks),
            'task_summary': task_summary,
            'participating_agents': active_execution.participating_agents if active_execution else [],
            'trust_analysis': active_execution.trust_analysis if active_execution else {},
            'execution_id': active_execution.execution_id if active_execution else None
        }
    
    def list_workflows(self, status_filter: Optional[WorkflowStatus] = None) -> List[Dict]:
        """List workflows with optional status filter"""
        workflows = []
        
        for workflow in self.workflows.values():
            if status_filter is None or workflow.status == status_filter:
                workflows.append({
                    'workflow_id': workflow.workflow_id,
                    'name': workflow.name,
                    'description': workflow.description,
                    'status': workflow.status.value,
                    'created_time': workflow.created_time.isoformat(),
                    'total_tasks': len(workflow.tasks),
                    'coordinator_agent': workflow.coordinator_agent
                })
        
        return sorted(workflows, key=lambda w: w['created_time'], reverse=True)
    
    def get_orchestrator_stats(self) -> Dict:
        """Get orchestrator statistics"""
        status_counts = {}
        for status in WorkflowStatus:
            status_counts[status.value] = len([
                w for w in self.workflows.values() if w.status == status
            ])
        
        return {
            'total_workflows': len(self.workflows),
            'active_executions': len(self.active_executions),
            'workflow_status_distribution': status_counts,
            'scheduling_algorithms': list(self.scheduling_algorithms.keys()),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
    
    def save_workflows(self):
        """Save workflows to storage"""
        try:
            import os
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            workflows_data = {}
            for workflow_id, workflow in self.workflows.items():
                workflow_dict = asdict(workflow)
                workflow_dict['created_time'] = workflow.created_time.isoformat()
                if workflow.start_time:
                    workflow_dict['start_time'] = workflow.start_time.isoformat()
                if workflow.completion_time:
                    workflow_dict['completion_time'] = workflow.completion_time.isoformat()
                workflow_dict['status'] = workflow.status.value
                
                # Handle task status enums
                for task in workflow_dict['tasks']:
                    task['status'] = task['status'].value if hasattr(task['status'], 'value') else task['status']
                    if task.get('actual_start_time'):
                        task['actual_start_time'] = task['actual_start_time'].isoformat()
                    if task.get('actual_completion_time'):
                        task['actual_completion_time'] = task['actual_completion_time'].isoformat()
                
                workflows_data[workflow_id] = workflow_dict
            
            data = {
                'workflows': workflows_data,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving workflows: {e}")
    
    def load_workflows(self):
        """Load workflows from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            for workflow_id, workflow_data in data.get('workflows', {}).items():
                # Convert timestamps
                workflow_data['created_time'] = datetime.fromisoformat(workflow_data['created_time'])
                if workflow_data.get('start_time'):
                    workflow_data['start_time'] = datetime.fromisoformat(workflow_data['start_time'])
                if workflow_data.get('completion_time'):
                    workflow_data['completion_time'] = datetime.fromisoformat(workflow_data['completion_time'])
                
                # Convert status
                workflow_data['status'] = WorkflowStatus(workflow_data['status'])
                
                # Convert tasks
                tasks = []
                for task_data in workflow_data['tasks']:
                    if task_data.get('actual_start_time'):
                        task_data['actual_start_time'] = datetime.fromisoformat(task_data['actual_start_time'])
                    if task_data.get('actual_completion_time'):
                        task_data['actual_completion_time'] = datetime.fromisoformat(task_data['actual_completion_time'])
                    task_data['status'] = TaskStatus(task_data['status'])
                    tasks.append(WorkflowTask(**task_data))
                
                workflow_data['tasks'] = tasks
                self.workflows[workflow_id] = Workflow(**workflow_data)
                
        except FileNotFoundError:
            # First run, workflows will be empty
            pass
        except Exception as e:
            print(f"Error loading workflows: {e}")


# Example usage and testing
async def test_orchestrator():
    """Test the workflow orchestrator"""
    from agent_registry import AgentRegistry, CapabilityType, AgentCapability
    from trust_propagation import TrustPropagationEngine
    from mcp_protocol import AgentCoordinationProtocol, WebSocketTransport
    
    # Setup
    registry = AgentRegistry("data/test_orchestrator_registry.json")
    trust_engine = TrustPropagationEngine(registry, "data/test_orchestrator_trust.json")
    
    # Create test agents
    forge_capabilities = [
        AgentCapability(CapabilityType.CODE_GENERATION, "development", "Software development", 0.9),
        AgentCapability(CapabilityType.TASK_EXECUTION, "automation", "Task automation", 0.8)
    ]
    
    scout_capabilities = [
        AgentCapability(CapabilityType.DATA_ANALYSIS, "research", "Data analysis and research", 0.9),
        AgentCapability(CapabilityType.MONITORING, "observation", "System monitoring", 0.8)
    ]
    
    forge_id = registry.register_agent(
        "Forge", "Development agent", "constellation", "1.0.0", 
        forge_capabilities, "ws://localhost:8765"
    )
    
    scout_id = registry.register_agent(
        "Scout", "Research agent", "constellation", "1.0.0",
        scout_capabilities, "ws://localhost:8766"
    )
    
    # Establish trust relationships
    trust_engine.establish_trust_relationship(forge_id, scout_id, 0.8)
    trust_engine.establish_trust_relationship(scout_id, forge_id, 0.8)
    
    # Create coordination protocol
    transport = WebSocketTransport()
    protocol = AgentCoordinationProtocol(forge_id, registry, trust_engine, transport, "ws://localhost:8765")
    
    # Create orchestrator
    orchestrator = WorkflowOrchestrator(registry, trust_engine, protocol)
    
    # Create example workflow
    tasks = [
        {
            'name': 'Research Requirements',
            'description': 'Research project requirements and constraints',
            'required_capabilities': ['research'],
            'parameters': {'project_name': 'Test Project'},
            'dependencies': []
        },
        {
            'name': 'Develop Solution',
            'description': 'Develop solution based on requirements',
            'required_capabilities': ['development'],
            'parameters': {'requirements_source': 'research_task'},
            'dependencies': ['Research Requirements']
        }
    ]
    
    workflow_id = orchestrator.create_workflow(
        name="Example Multi-Agent Workflow",
        description="Demonstrates research and development coordination",
        coordinator_agent=forge_id,
        tasks=tasks,
        workflow_type="dag"
    )
    
    print(f"Created workflow: {workflow_id}")
    print(f"Workflow status: {orchestrator.get_workflow_status(workflow_id)}")
    print(f"Orchestrator stats: {orchestrator.get_orchestrator_stats()}")
    
    # Execute workflow
    execution_id = await orchestrator.execute_workflow(workflow_id, "trust_optimized")
    print(f"Started execution: {execution_id}")

if __name__ == "__main__":
    asyncio.run(test_orchestrator())