"""Memory models for conversation and project context."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4


class MemoryType(Enum):
    """Types of memory entries."""
    CONVERSATION = "conversation"
    PROJECT = "project"
    SYSTEM = "system"
    USER_PREFERENCE = "user_preference"
    CODE_CONTEXT = "code_context"
    TASK_CONTEXT = "task_context"


class MessageRole(Enum):
    """Roles in conversation messages."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class ConversationMessage:
    """A single message in a conversation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    role: MessageRole = MessageRole.USER
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            tool_calls=data.get("tool_calls"),
            tool_results=data.get("tool_results"),
        )


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str = field(default_factory=lambda: str(uuid4()))
    memory_type: MemoryType = MemoryType.CONVERSATION
    content: str = ""
    summary: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "project_id": self.project_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "embedding": self.embedding,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            summary=data.get("summary", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id"),
            project_id=data.get("project_id"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            embedding=data.get("embedding"),
        )
    
    def mark_accessed(self):
        """Mark this memory as accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)


@dataclass
class ConversationSession:
    """A conversation session with messages and context."""
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    messages: List[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    def add_message(self, message: ConversationMessage):
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        
        # Auto-generate title from first user message if not set
        if not self.title and message.role == MessageRole.USER and message.content:
            self.title = self._generate_title(message.content)
    
    def _generate_title(self, content: str) -> str:
        """Generate a title from message content."""
        # Take first 50 characters and clean up
        title = content.strip()[:50]
        if len(content) > 50:
            title += "..."
        return title
    
    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """Get the most recent messages."""
        return self.messages[-count:] if self.messages else []
    
    def get_message_count(self) -> int:
        """Get total message count."""
        return len(self.messages)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "project_id": self.project_id,
            "metadata": self.metadata,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            messages=[ConversationMessage.from_dict(msg) for msg in data.get("messages", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            project_id=data.get("project_id"),
            metadata=data.get("metadata", {}),
            is_active=data.get("is_active", True),
        )


@dataclass
class ProjectContext:
    """Project-specific context and knowledge."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    workspace_path: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    is_active: bool = True
    
    # Project-specific knowledge
    file_patterns: List[str] = field(default_factory=list)
    important_files: List[str] = field(default_factory=list)
    coding_conventions: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "is_active": self.is_active,
            "file_patterns": self.file_patterns,
            "important_files": self.important_files,
            "coding_conventions": self.coding_conventions,
            "dependencies": self.dependencies,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectContext":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            workspace_path=data.get("workspace_path", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            is_active=data.get("is_active", True),
            file_patterns=data.get("file_patterns", []),
            important_files=data.get("important_files", []),
            coding_conventions=data.get("coding_conventions", {}),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class MemorySearchResult:
    """Result from memory search operation."""
    entry: MemoryEntry
    score: float
    relevance_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry": self.entry.to_dict(),
            "score": self.score,
            "relevance_reason": self.relevance_reason,
        }