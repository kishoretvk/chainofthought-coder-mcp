"""
Base agent framework for MCP agent system
"""
import asyncio
import uuid
from typing import Any, Dict, Optional

class AgentBase:
    def __init__(self, agent_type: str):
        self.agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type
        self.message_queue = asyncio.Queue()
        self.running = False
        
    async def send(self, recipient: 'AgentBase', message: Dict[str, Any]):
        """Send message to another agent"""
        await recipient.message_queue.put({
            'sender': self.agent_id,
            'content': message
        })
        
    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive message from queue"""
        return await self.message_queue.get()
    
    async def run(self):
        """Main agent loop to be implemented by subclasses"""
        self.running = True
        while self.running:
            message = await self.receive()
            if message:
                await self.handle_message(message)
                
    async def handle_message(self, message: Dict[str, Any]):
        """Process incoming messages"""
        raise NotImplementedError("Subclasses must implement handle_message")
    
    def stop(self):
        """Gracefully stop the agent"""
        self.running = False