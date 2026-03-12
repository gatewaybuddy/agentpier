"""
AgentPier V3 Multi-Agent Coordination Framework POC
MCP-Compatible Coordination Protocol - Enables agent-to-agent communication and task delegation
"""

import json
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import websockets
import aiohttp
from abc import ABC, abstractmethod

from .agent_registry import AgentRegistry, AgentIdentity
from .trust_propagation import TrustPropagationEngine, TrustEventType

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response" 
    NOTIFICATION = "notification"
    ERROR = "error"

class CoordinationMessageType(Enum):
    TASK_DELEGATION = "task_delegation"
    CAPABILITY_INQUIRY = "capability_inquiry"
    TRUST_VERIFICATION = "trust_verification"
    STATUS_UPDATE = "status_update"
    WORKFLOW_COORDINATION = "workflow_coordination"
    RESOURCE_REQUEST = "resource_request"

@dataclass
class MCPMessage:
    """MCP-compatible message structure"""
    id: str
    type: MessageType
    method: Optional[str] = None
    params: Optional[Dict] = None
    result: Optional[Any] = None
    error: Optional[Dict] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        data['type'] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MCPMessage':
        if 'timestamp' in data and data['timestamp']:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['type'] = MessageType(data['type'])
        return cls(**data)

@dataclass
class TaskDelegation:
    """Task delegation request structure"""
    task_id: str
    requesting_agent: str
    target_agent: str
    task_type: str
    task_description: str
    parameters: Dict
    required_capabilities: List[str]
    priority: int  # 1-10
    deadline: Optional[datetime] = None
    trust_requirements: Optional[Dict] = None
    callback_endpoint: Optional[str] = None

@dataclass
class TaskResult:
    """Task completion result"""
    task_id: str
    status: str  # "completed", "failed", "in_progress", "cancelled"
    result_data: Optional[Dict] = None
    error_message: Optional[str] = None
    completion_time: Optional[datetime] = None
    trust_feedback: Optional[float] = None

class MCPTransport(ABC):
    """Abstract base class for MCP transport mechanisms"""
    
    @abstractmethod
    async def send_message(self, target_endpoint: str, message: MCPMessage) -> bool:
        pass
    
    @abstractmethod
    async def receive_message(self) -> Optional[MCPMessage]:
        pass
    
    @abstractmethod
    async def start_listening(self, endpoint: str, message_handler: Callable):
        pass

class WebSocketTransport(MCPTransport):
    """WebSocket-based MCP transport"""
    
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.server = None
        self.message_handler: Optional[Callable] = None
    
    async def send_message(self, target_endpoint: str, message: MCPMessage) -> bool:
        try:
            # Parse endpoint (ws://host:port/path)
            async with websockets.connect(target_endpoint) as websocket:
                await websocket.send(json.dumps(message.to_dict()))
                return True
        except Exception as e:
            print(f"Error sending message to {target_endpoint}: {e}")
            return False
    
    async def receive_message(self) -> Optional[MCPMessage]:
        # This would be handled by the message_handler in start_listening
        pass
    
    async def start_listening(self, endpoint: str, message_handler: Callable):
        self.message_handler = message_handler
        
        # Parse endpoint to get host and port
        # Format: ws://host:port or just port
        if endpoint.startswith('ws://'):
            url_parts = endpoint.replace('ws://', '').split(':')
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 8765
        else:
            host = 'localhost'
            port = int(endpoint)
        
        async def handle_client(websocket, path):
            try:
                async for message_data in websocket:
                    message = MCPMessage.from_dict(json.loads(message_data))
                    await message_handler(message, websocket)
            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                print(f"Error handling client message: {e}")
        
        self.server = await websockets.serve(handle_client, host, port)
        print(f"MCP WebSocket server listening on {host}:{port}")
        await self.server.wait_closed()

class HTTPTransport(MCPTransport):
    """HTTP-based MCP transport"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def send_message(self, target_endpoint: str, message: MCPMessage) -> bool:
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(
                target_endpoint,
                json=message.to_dict(),
                headers={'Content-Type': 'application/json'}
            ) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error sending HTTP message to {target_endpoint}: {e}")
            return False
    
    async def receive_message(self) -> Optional[MCPMessage]:
        # HTTP is request-response, no persistent receiving
        pass
    
    async def start_listening(self, endpoint: str, message_handler: Callable):
        from aiohttp import web
        
        async def handle_request(request):
            try:
                data = await request.json()
                message = MCPMessage.from_dict(data)
                response = await message_handler(message)
                
                if response:
                    return web.json_response(response.to_dict())
                else:
                    return web.Response(status=200)
            except Exception as e:
                print(f"Error handling HTTP request: {e}")
                return web.Response(status=500, text=str(e))
        
        app = web.Application()
        app.router.add_post('/', handle_request)
        
        # Parse endpoint
        if ':' in endpoint:
            host, port = endpoint.split(':')
            port = int(port)
        else:
            host = 'localhost'
            port = int(endpoint)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        print(f"MCP HTTP server listening on {host}:{port}")
        
        # Keep running indefinitely
        while True:
            await asyncio.sleep(1)

class AgentCoordinationProtocol:
    """Main coordination protocol for multi-agent communication"""
    
    def __init__(self, 
                 agent_id: str,
                 registry: AgentRegistry,
                 trust_engine: TrustPropagationEngine,
                 transport: MCPTransport,
                 endpoint: str):
        self.agent_id = agent_id
        self.registry = registry
        self.trust_engine = trust_engine
        self.transport = transport
        self.endpoint = endpoint
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {
            'task_delegation': self._handle_task_delegation,
            'capability_inquiry': self._handle_capability_inquiry,
            'trust_verification': self._handle_trust_verification,
            'status_update': self._handle_status_update,
            'workflow_coordination': self._handle_workflow_coordination,
            'resource_request': self._handle_resource_request,
        }
        
        # Active tasks
        self.active_tasks: Dict[str, TaskDelegation] = {}
        self.task_results: Dict[str, TaskResult] = {}
        
        # Coordination state
        self.coordination_sessions: Dict[str, Dict] = {}
    
    async def start_coordination_service(self):
        """Start the coordination service to listen for messages"""
        await self.transport.start_listening(self.endpoint, self._handle_incoming_message)
    
    async def _handle_incoming_message(self, message: MCPMessage, connection=None) -> Optional[MCPMessage]:
        """Handle incoming MCP messages"""
        try:
            if message.method in self.message_handlers:
                handler = self.message_handlers[message.method]
                response = await handler(message, connection)
                
                # Record trust event if this was a successful interaction
                if message.params and 'source_agent' in message.params:
                    source_agent = message.params['source_agent']
                    self.trust_engine.record_trust_event(
                        source_agent, self.agent_id,
                        TrustEventType.COMMUNICATION_SUCCESS,
                        0.1,  # Small positive trust increment
                        {'message_type': message.method, 'timestamp': datetime.now(timezone.utc).isoformat()}
                    )
                
                return response
            else:
                return MCPMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.ERROR,
                    error={'code': -32601, 'message': f'Unknown method: {message.method}'}
                )
        except Exception as e:
            print(f"Error handling message: {e}")
            return MCPMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                error={'code': -32603, 'message': f'Internal error: {str(e)}'}
            )
    
    async def delegate_task(self, 
                           target_agent: str, 
                           task_type: str,
                           task_description: str,
                           parameters: Dict,
                           required_capabilities: List[str],
                           priority: int = 5) -> Optional[str]:
        """Delegate a task to another agent"""
        
        # Check if target agent exists and has required capabilities
        target_identity = self.registry.get_agent(target_agent)
        if not target_identity:
            print(f"Target agent {target_agent} not found")
            return None
        
        # Check trust relationship
        trust_score = self.trust_engine.get_trust_score(self.agent_id, target_agent)
        if not trust_score or trust_score.overall_score < 0.5:
            print(f"Insufficient trust relationship with {target_agent}")
            return None
        
        # Create task delegation
        task_id = str(uuid.uuid4())
        delegation = TaskDelegation(
            task_id=task_id,
            requesting_agent=self.agent_id,
            target_agent=target_agent,
            task_type=task_type,
            task_description=task_description,
            parameters=parameters,
            required_capabilities=required_capabilities,
            priority=priority,
            callback_endpoint=self.endpoint
        )
        
        # Send delegation message
        message = MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.REQUEST,
            method='task_delegation',
            params={
                'source_agent': self.agent_id,
                'task_delegation': asdict(delegation)
            }
        )
        
        success = await self.transport.send_message(target_identity.endpoint, message)
        if success:
            self.active_tasks[task_id] = delegation
            return task_id
        else:
            return None
    
    async def _handle_task_delegation(self, message: MCPMessage, connection=None) -> MCPMessage:
        """Handle incoming task delegation request"""
        task_data = message.params['task_delegation']
        delegation = TaskDelegation(**task_data)
        
        # Check if we can handle this task
        my_identity = self.registry.get_agent(self.agent_id)
        can_handle = any(
            capability.name in delegation.required_capabilities
            for capability in my_identity.capabilities
        )
        
        if not can_handle:
            return MCPMessage(
                id=str(uuid.uuid4()),
                type=MessageType.RESPONSE,
                result={
                    'status': 'rejected',
                    'reason': 'insufficient_capabilities',
                    'task_id': delegation.task_id
                }
            )
        
        # Accept task
        self.active_tasks[delegation.task_id] = delegation
        
        # Start task execution (in real implementation, this would trigger actual work)
        asyncio.create_task(self._execute_delegated_task(delegation))
        
        return MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            result={
                'status': 'accepted',
                'task_id': delegation.task_id,
                'estimated_completion': (datetime.now(timezone.utc) + 
                                       datetime.timedelta(minutes=30)).isoformat()
            }
        )
    
    async def _execute_delegated_task(self, delegation: TaskDelegation):
        """Execute a delegated task (placeholder implementation)"""
        # Simulate task execution
        await asyncio.sleep(2)
        
        # Create result
        result = TaskResult(
            task_id=delegation.task_id,
            status='completed',
            result_data={
                'message': f'Task {delegation.task_type} completed successfully',
                'output': delegation.parameters  # Echo parameters for demo
            },
            completion_time=datetime.now(timezone.utc),
            trust_feedback=0.8
        )
        
        self.task_results[delegation.task_id] = result
        
        # Send result back to requesting agent
        if delegation.callback_endpoint:
            callback_message = MCPMessage(
                id=str(uuid.uuid4()),
                type=MessageType.NOTIFICATION,
                method='task_completed',
                params={
                    'source_agent': self.agent_id,
                    'task_result': asdict(result)
                }
            )
            
            await self.transport.send_message(delegation.callback_endpoint, callback_message)
    
    async def inquire_capabilities(self, target_agent: str) -> Optional[List[Dict]]:
        """Inquire about another agent's capabilities"""
        target_identity = self.registry.get_agent(target_agent)
        if not target_identity:
            return None
        
        message = MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.REQUEST,
            method='capability_inquiry',
            params={'source_agent': self.agent_id}
        )
        
        # In real implementation, this would wait for response
        # For now, return capabilities from registry
        return [asdict(cap) for cap in target_identity.capabilities]
    
    async def _handle_capability_inquiry(self, message: MCPMessage, connection=None) -> MCPMessage:
        """Handle capability inquiry"""
        my_identity = self.registry.get_agent(self.agent_id)
        capabilities = [asdict(cap) for cap in my_identity.capabilities]
        
        return MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            result={
                'agent_id': self.agent_id,
                'capabilities': capabilities,
                'status': my_identity.status.value,
                'trust_score': my_identity.trust_score
            }
        )
    
    async def verify_trust_relationship(self, target_agent: str) -> Optional[Dict]:
        """Verify trust relationship with another agent"""
        trust_score = self.trust_engine.get_trust_score(self.agent_id, target_agent)
        
        if not trust_score:
            return None
        
        return {
            'agent_a': self.agent_id,
            'agent_b': target_agent,
            'trust_score': trust_score.overall_score,
            'confidence': trust_score.confidence,
            'last_updated': trust_score.last_updated.isoformat(),
            'components': {
                'collaboration': trust_score.collaboration_score,
                'reliability': trust_score.reliability_score,
                'communication': trust_score.communication_score,
                'verification': trust_score.verification_score
            }
        }
    
    async def _handle_trust_verification(self, message: MCPMessage, connection=None) -> MCPMessage:
        """Handle trust verification request"""
        source_agent = message.params['source_agent']
        trust_data = await self.verify_trust_relationship(source_agent)
        
        return MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            result=trust_data or {'error': 'No trust relationship found'}
        )
    
    async def coordinate_workflow(self, 
                                 participants: List[str],
                                 workflow_description: str,
                                 coordination_type: str = "collaborative") -> Optional[str]:
        """Coordinate a multi-agent workflow"""
        
        # Verify all participants exist and have sufficient trust
        workflow_trust = self.trust_engine.calculate_workflow_trust(
            [self.agent_id] + participants, 
            coordination_type
        )
        
        if 'error' in workflow_trust or workflow_trust['recommendation'] != 'APPROVED':
            print(f"Workflow trust check failed: {workflow_trust}")
            return None
        
        # Create coordination session
        session_id = str(uuid.uuid4())
        self.coordination_sessions[session_id] = {
            'participants': participants,
            'workflow_description': workflow_description,
            'coordination_type': coordination_type,
            'status': 'active',
            'created': datetime.now(timezone.utc),
            'trust_analysis': workflow_trust
        }
        
        # Notify all participants
        for participant in participants:
            participant_identity = self.registry.get_agent(participant)
            if participant_identity and participant_identity.endpoint:
                notification = MCPMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.NOTIFICATION,
                    method='workflow_coordination',
                    params={
                        'source_agent': self.agent_id,
                        'session_id': session_id,
                        'workflow_description': workflow_description,
                        'coordination_type': coordination_type,
                        'participants': participants
                    }
                )
                
                await self.transport.send_message(participant_identity.endpoint, notification)
        
        return session_id
    
    async def _handle_status_update(self, message: MCPMessage, connection=None) -> MCPMessage:
        """Handle status update from another agent"""
        # Update registry with new status information
        source_agent = message.params['source_agent']
        status_data = message.params.get('status_data', {})
        
        if 'status' in status_data:
            from .agent_registry import AgentStatus
            new_status = AgentStatus(status_data['status'])
            self.registry.update_agent_status(source_agent, new_status)
        
        return MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            result={'acknowledged': True}
        )
    
    async def _handle_workflow_coordination(self, message: MCPMessage, connection=None) -> MCPMessage:
        """Handle workflow coordination request"""
        session_id = message.params['session_id']
        workflow_description = message.params['workflow_description']
        
        # Accept workflow participation (in real implementation, this might involve decision logic)
        return MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            result={
                'session_id': session_id,
                'status': 'accepted',
                'agent_id': self.agent_id
            }
        )
    
    async def _handle_resource_request(self, message: MCPMessage, connection=None) -> MCPMessage:
        """Handle resource request from another agent"""
        # Placeholder for resource sharing logic
        return MCPMessage(
            id=str(uuid.uuid4()),
            type=MessageType.RESPONSE,
            result={
                'status': 'not_implemented',
                'message': 'Resource sharing not yet implemented'
            }
        )
    
    def get_coordination_stats(self) -> Dict:
        """Get coordination statistics"""
        return {
            'agent_id': self.agent_id,
            'endpoint': self.endpoint,
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len([r for r in self.task_results.values() if r.status == 'completed']),
            'active_workflows': len([s for s in self.coordination_sessions.values() if s['status'] == 'active']),
            'trust_relationships': len(self.trust_engine.trust_scores),
            'last_activity': datetime.now(timezone.utc).isoformat()
        }


# Example usage and testing
async def test_coordination():
    """Test the coordination protocol"""
    from agent_registry import AgentRegistry, CapabilityType, AgentCapability
    from trust_propagation import TrustPropagationEngine
    
    # Setup
    registry = AgentRegistry("data/test_coordination_registry.json")
    trust_engine = TrustPropagationEngine(registry, "data/test_coordination_trust.json")
    
    # Create test agents
    forge_capabilities = [
        AgentCapability(CapabilityType.CODE_GENERATION, "development", "Development tasks", 0.9),
        AgentCapability(CapabilityType.TASK_EXECUTION, "coordination", "Task coordination", 0.8)
    ]
    
    forge_id = registry.register_agent(
        "Forge", "Development agent", "constellation", "1.0.0", 
        forge_capabilities, "ws://localhost:8765"
    )
    
    scout_capabilities = [
        AgentCapability(CapabilityType.DATA_ANALYSIS, "research", "Research tasks", 0.9)
    ]
    
    scout_id = registry.register_agent(
        "Scout", "Research agent", "constellation", "1.0.0",
        scout_capabilities, "ws://localhost:8766"
    )
    
    # Establish trust relationship
    trust_engine.establish_trust_relationship(forge_id, scout_id, 0.8)
    
    # Create coordination protocols
    forge_transport = WebSocketTransport()
    forge_protocol = AgentCoordinationProtocol(
        forge_id, registry, trust_engine, forge_transport, "ws://localhost:8765"
    )
    
    scout_transport = WebSocketTransport()
    scout_protocol = AgentCoordinationProtocol(
        scout_id, registry, trust_engine, scout_transport, "ws://localhost:8766"
    )
    
    print("Coordination protocol test setup complete")
    print(f"Forge stats: {forge_protocol.get_coordination_stats()}")
    print(f"Scout stats: {scout_protocol.get_coordination_stats()}")

if __name__ == "__main__":
    asyncio.run(test_coordination())