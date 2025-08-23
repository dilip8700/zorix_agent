"""Streaming utilities for real-time communication."""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """Types of streaming events."""
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_RESULT = "tool_call_result"
    TOOL_CALL_END = "tool_call_end"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"


class StreamEvent(BaseModel):
    """A streaming event."""
    event_type: StreamEventType
    event_id: str
    timestamp: datetime
    session_id: Optional[str] = None
    data: Dict[str, Any] = {}
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Events format."""
        lines = []
        
        # Add event type
        lines.append(f"event: {self.event_type}")
        
        # Add event ID
        lines.append(f"id: {self.event_id}")
        
        # Add data
        event_data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            **self.data
        }
        lines.append(f"data: {json.dumps(event_data)}")
        
        # Add empty line to end event
        lines.append("")
        
        return "\n".join(lines) + "\n"


class StreamingChatSession:
    """Manages a streaming chat session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.is_active = True
        self.client_count = 0
        self.message_buffer = []
        self.tool_calls = {}
        
    def add_client(self):
        """Add a client connection."""
        self.client_count += 1
        self.last_activity = datetime.now()
        
    def remove_client(self):
        """Remove a client connection."""
        self.client_count = max(0, self.client_count - 1)
        self.last_activity = datetime.now()
        
        if self.client_count == 0:
            self.is_active = False
    
    def is_expired(self, timeout_seconds: int = 3600) -> bool:
        """Check if session is expired."""
        return (datetime.now() - self.last_activity).total_seconds() > timeout_seconds


class StreamingManager:
    """Manages streaming connections and events."""
    
    def __init__(self):
        self.sessions: Dict[str, StreamingChatSession] = {}
        self.cleanup_task = None
        
    async def start(self):
        """Start the streaming manager."""
        self.cleanup_task = asyncio.create_task(self._cleanup_sessions())
        
    async def stop(self):
        """Stop the streaming manager."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    def get_or_create_session(self, session_id: str) -> StreamingChatSession:
        """Get or create a streaming session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = StreamingChatSession(session_id)
        return self.sessions[session_id]
    
    def remove_session(self, session_id: str):
        """Remove a streaming session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    async def _cleanup_sessions(self):
        """Periodically cleanup expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                expired_sessions = [
                    session_id for session_id, session in self.sessions.items()
                    if session.is_expired()
                ]
                
                for session_id in expired_sessions:
                    logger.info(f"Cleaning up expired session: {session_id}")
                    self.remove_session(session_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")


class StreamingChatHandler:
    """Handles streaming chat interactions."""
    
    def __init__(self, bedrock_client, memory_provider=None, orchestrator=None):
        self.bedrock_client = bedrock_client
        self.memory_provider = memory_provider
        self.orchestrator = orchestrator
        
    async def stream_chat_response(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat response with tool calling support."""
        
        try:
            # Send connection established event
            yield StreamEvent(
                event_type=StreamEventType.CONNECTION_ESTABLISHED,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"message": "Connection established"}
            )
            
            # Send message start event
            yield StreamEvent(
                event_type=StreamEventType.MESSAGE_START,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"user_message": message}
            )
            
            # Prepare conversation context
            messages = conversation_history or []
            messages.append({"role": "user", "content": message})
            
            # Check if this might require tool calling
            needs_tools = await self._analyze_for_tool_needs(message, context)
            
            if needs_tools and self.orchestrator:
                # Stream with tool calling
                async for event in self._stream_with_tools(session_id, message, messages, context):
                    yield event
            else:
                # Stream regular chat response
                async for event in self._stream_regular_chat(session_id, messages, context):
                    yield event
            
            # Send message stop event
            yield StreamEvent(
                event_type=StreamEventType.MESSAGE_STOP,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"message": "Response completed"}
            )
            
        except Exception as e:
            logger.error(f"Streaming chat error: {e}")
            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _stream_regular_chat(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream regular chat response without tools."""
        
        try:
            # Stream response from Bedrock
            response_chunks = self.bedrock_client.chat(
                messages=messages,
                context=context or {},
                stream=True
            )
            
            full_response = ""
            async for chunk in response_chunks:
                content = chunk.get("content", "")
                if content:
                    full_response += content
                    
                    yield StreamEvent(
                        event_type=StreamEventType.MESSAGE_DELTA,
                        event_id=str(uuid4()),
                        timestamp=datetime.now(),
                        session_id=session_id,
                        data={
                            "delta": content,
                            "accumulated": full_response
                        }
                    )
            
            # Store conversation if memory provider available
            if self.memory_provider and full_response:
                try:
                    await self.memory_provider.store_conversation_turn(
                        session_id=session_id,
                        user_message=messages[-1]["content"],
                        assistant_response=full_response,
                        context=context
                    )
                except Exception as e:
                    logger.warning(f"Failed to store conversation: {e}")
                    
        except Exception as e:
            logger.error(f"Regular chat streaming error: {e}")
            raise
    
    async def _stream_with_tools(
        self,
        session_id: str,
        message: str,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat response with tool calling."""
        
        try:
            # Create execution plan
            yield StreamEvent(
                event_type=StreamEventType.TOOL_CALL_START,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"message": "Analyzing request and creating plan..."}
            )
            
            # Use orchestrator to handle the request
            execution_id = str(uuid4())
            
            # Stream execution progress
            async for progress in self.orchestrator.stream_execution(
                instruction=message,
                context=context or {},
                execution_id=execution_id
            ):
                
                if progress.get("type") == "tool_call":
                    yield StreamEvent(
                        event_type=StreamEventType.TOOL_CALL_DELTA,
                        event_id=str(uuid4()),
                        timestamp=datetime.now(),
                        session_id=session_id,
                        data={
                            "tool_name": progress.get("tool_name"),
                            "tool_input": progress.get("tool_input"),
                            "step": progress.get("step"),
                            "progress": progress.get("progress", {})
                        }
                    )
                
                elif progress.get("type") == "tool_result":
                    yield StreamEvent(
                        event_type=StreamEventType.TOOL_CALL_RESULT,
                        event_id=str(uuid4()),
                        timestamp=datetime.now(),
                        session_id=session_id,
                        data={
                            "tool_name": progress.get("tool_name"),
                            "result": progress.get("result"),
                            "success": progress.get("success", True)
                        }
                    )
                
                elif progress.get("type") == "response":
                    # Stream the final response
                    content = progress.get("content", "")
                    if content:
                        yield StreamEvent(
                            event_type=StreamEventType.MESSAGE_DELTA,
                            event_id=str(uuid4()),
                            timestamp=datetime.now(),
                            session_id=session_id,
                            data={
                                "delta": content,
                                "accumulated": progress.get("accumulated", content)
                            }
                        )
            
            yield StreamEvent(
                event_type=StreamEventType.TOOL_CALL_END,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"message": "Tool execution completed"}
            )
            
        except Exception as e:
            logger.error(f"Tool streaming error: {e}")
            raise
    
    async def _analyze_for_tool_needs(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Analyze if message might need tool calling."""
        
        # Simple heuristics for tool detection
        tool_indicators = [
            "create", "write", "modify", "delete", "search", "find",
            "run", "execute", "install", "build", "test", "deploy",
            "git", "commit", "push", "pull", "branch", "merge",
            "file", "directory", "folder", "code", "function"
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in tool_indicators)


# Global streaming manager instance
streaming_manager = StreamingManager()