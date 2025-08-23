"""Session memory management with ring buffer for recent messages."""

import json
import logging
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a conversation message."""
    
    id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        data = data.copy()
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:100]}..."


@dataclass
class ToolCall:
    """Represents a tool call and its result."""
    
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = None
    duration_ms: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool call to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolCall':
        """Create tool call from dictionary."""
        data = data.copy()
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class SessionMemory:
    """Manages session-level memory with ring buffer for recent messages."""
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        max_messages: int = 100,
        max_tool_calls: int = 50,
        max_context_tokens: int = 8000
    ):
        """Initialize session memory.
        
        Args:
            session_id: Unique session identifier
            max_messages: Maximum number of messages to keep in memory
            max_tool_calls: Maximum number of tool calls to keep in memory
            max_context_tokens: Approximate token limit for context
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.max_messages = max_messages
        self.max_tool_calls = max_tool_calls
        self.max_context_tokens = max_context_tokens
        
        # Ring buffers for recent data
        self.messages: deque[Message] = deque(maxlen=max_messages)
        self.tool_calls: deque[ToolCall] = deque(maxlen=max_tool_calls)
        
        # Session metadata
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}
        
        logger.info(f"Initialized session memory: {self.session_id}")
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add a message to the session.
        
        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Created message object
        """
        message = Message(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        self.last_activity = datetime.utcnow()
        
        logger.debug(f"Added {role} message to session {self.session_id}")
        return message
    
    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a user message."""
        return self.add_message("user", content, metadata)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add an assistant message."""
        return self.add_message("assistant", content, metadata)
    
    def add_system_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a system message."""
        return self.add_message("system", content, metadata)
    
    def add_tool_call(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Optional[Any] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> ToolCall:
        """Add a tool call to the session.
        
        Args:
            tool_name: Name of the tool called
            parameters: Tool parameters
            result: Tool execution result
            error: Error message if tool failed
            duration_ms: Execution time in milliseconds
            
        Returns:
            Created tool call object
        """
        tool_call = ToolCall(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            error=error,
            duration_ms=duration_ms
        )
        
        self.tool_calls.append(tool_call)
        self.last_activity = datetime.utcnow()
        
        logger.debug(f"Added tool call {tool_name} to session {self.session_id}")
        return tool_call
    
    def get_messages(
        self,
        limit: Optional[int] = None,
        role_filter: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Message]:
        """Get messages from the session.
        
        Args:
            limit: Maximum number of messages to return
            role_filter: Filter by message role
            since: Only return messages after this timestamp
            
        Returns:
            List of messages
        """
        messages = list(self.messages)
        
        # Apply filters
        if role_filter:
            messages = [m for m in messages if m.role == role_filter]
        
        if since:
            messages = [m for m in messages if m.timestamp > since]
        
        # Apply limit
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """Get the most recent messages.
        
        Args:
            count: Number of recent messages to return
            
        Returns:
            List of recent messages
        """
        return list(self.messages)[-count:]
    
    def get_tool_calls(
        self,
        limit: Optional[int] = None,
        tool_filter: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[ToolCall]:
        """Get tool calls from the session.
        
        Args:
            limit: Maximum number of tool calls to return
            tool_filter: Filter by tool name
            since: Only return tool calls after this timestamp
            
        Returns:
            List of tool calls
        """
        tool_calls = list(self.tool_calls)
        
        # Apply filters
        if tool_filter:
            tool_calls = [tc for tc in tool_calls if tc.tool_name == tool_filter]
        
        if since:
            tool_calls = [tc for tc in tool_calls if tc.timestamp > since]
        
        # Apply limit
        if limit:
            tool_calls = tool_calls[-limit:]
        
        return tool_calls
    
    def get_context_for_llm(
        self,
        max_tokens: Optional[int] = None,
        include_system: bool = True,
        include_tool_calls: bool = True
    ) -> List[Dict[str, Any]]:
        """Get conversation context formatted for LLM.
        
        Args:
            max_tokens: Maximum tokens to include (approximate)
            include_system: Whether to include system messages
            include_tool_calls: Whether to include tool call summaries
            
        Returns:
            List of message dictionaries for LLM context
        """
        max_tokens = max_tokens or self.max_context_tokens
        context = []
        estimated_tokens = 0
        
        # Get messages in reverse order (most recent first)
        messages = list(reversed(self.messages))
        
        for message in messages:
            # Skip system messages if not requested
            if not include_system and message.role == "system":
                continue
            
            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
            message_tokens = len(message.content) // 4
            
            if estimated_tokens + message_tokens > max_tokens and context:
                break
            
            context.insert(0, {
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat()
            })
            
            estimated_tokens += message_tokens
        
        # Add tool call summaries if requested
        if include_tool_calls and self.tool_calls:
            recent_tools = list(self.tool_calls)[-5:]  # Last 5 tool calls
            tool_summary = self._create_tool_summary(recent_tools)
            
            if tool_summary:
                tool_tokens = len(tool_summary) // 4
                if estimated_tokens + tool_tokens <= max_tokens:
                    context.insert(0, {
                        "role": "system",
                        "content": f"Recent tool usage:\n{tool_summary}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        return context
    
    def _create_tool_summary(self, tool_calls: List[ToolCall]) -> str:
        """Create a summary of recent tool calls.
        
        Args:
            tool_calls: List of tool calls to summarize
            
        Returns:
            Summary string
        """
        if not tool_calls:
            return ""
        
        summary_lines = []
        for tc in tool_calls:
            status = "✓" if tc.error is None else "✗"
            duration = f" ({tc.duration_ms}ms)" if tc.duration_ms else ""
            summary_lines.append(f"{status} {tc.tool_name}{duration}")
        
        return "\n".join(summary_lines)
    
    def clear_messages(self):
        """Clear all messages from the session."""
        self.messages.clear()
        logger.info(f"Cleared messages for session {self.session_id}")
    
    def clear_tool_calls(self):
        """Clear all tool calls from the session."""
        self.tool_calls.clear()
        logger.info(f"Cleared tool calls for session {self.session_id}")
    
    def clear_all(self):
        """Clear all session data."""
        self.clear_messages()
        self.clear_tool_calls()
        self.metadata.clear()
        logger.info(f"Cleared all data for session {self.session_id}")
    
    def set_metadata(self, key: str, value: Any):
        """Set session metadata.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        self.last_activity = datetime.utcnow()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get session metadata.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": len(self.messages),
            "tool_call_count": len(self.tool_calls),
            "metadata_keys": list(self.metadata.keys()),
            "max_messages": self.max_messages,
            "max_tool_calls": self.max_tool_calls,
            "max_context_tokens": self.max_context_tokens,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization.
        
        Returns:
            Dictionary representation of session
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata,
            "messages": [msg.to_dict() for msg in self.messages],
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "max_messages": self.max_messages,
            "max_tool_calls": self.max_tool_calls,
            "max_context_tokens": self.max_context_tokens,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionMemory':
        """Create session from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            SessionMemory instance
        """
        session = cls(
            session_id=data["session_id"],
            max_messages=data.get("max_messages", 100),
            max_tool_calls=data.get("max_tool_calls", 50),
            max_context_tokens=data.get("max_context_tokens", 8000)
        )
        
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_activity = datetime.fromisoformat(data["last_activity"])
        session.metadata = data.get("metadata", {})
        
        # Restore messages
        for msg_data in data.get("messages", []):
            message = Message.from_dict(msg_data)
            session.messages.append(message)
        
        # Restore tool calls
        for tc_data in data.get("tool_calls", []):
            tool_call = ToolCall.from_dict(tc_data)
            session.tool_calls.append(tool_call)
        
        return session
    
    def save_to_file(self, file_path: str):
        """Save session to JSON file.
        
        Args:
            file_path: Path to save file
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved session {self.session_id} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save session to file: {e}")
            raise
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'SessionMemory':
        """Load session from JSON file.
        
        Args:
            file_path: Path to load file
            
        Returns:
            SessionMemory instance
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            session = cls.from_dict(data)
            logger.info(f"Loaded session {session.session_id} from {file_path}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to load session from file: {e}")
            raise