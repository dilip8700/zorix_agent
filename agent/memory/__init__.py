"""Memory and context management for Zorix Agent."""

from .conversation import ConversationMemory
from .models import (
    ConversationMessage,
    ConversationSession,
    MemoryEntry,
    MemorySearchResult,
    MemoryType,
    MessageRole,
    ProjectContext,
)
from .project import ProjectMemory
from .provider import MemoryProvider

__all__ = [
    "ConversationMemory",
    "ConversationMessage", 
    "ConversationSession",
    "MemoryEntry",
    "MemorySearchResult",
    "MemoryType",
    "MessageRole",
    "ProjectContext",
    "ProjectMemory",
    "MemoryProvider",
]

from agent.memory.conversation import ConversationMemory, ConversationMemoryError
from agent.memory.models import (
    ConversationMessage,
    ConversationSession,
    MemoryEntry,
    MemorySearchResult,
    MemoryType,
    MessageRole,
    ProjectContext,
)
from agent.memory.project import ProjectMemory, ProjectMemoryError
from agent.memory.provider import MemoryProvider, MemoryProviderError

__all__ = [
    # Main provider
    "MemoryProvider",
    "MemoryProviderError",
    
    # Conversation memory
    "ConversationMemory",
    "ConversationMemoryError",
    
    # Project memory
    "ProjectMemory", 
    "ProjectMemoryError",
    
    # Models
    "ConversationMessage",
    "ConversationSession",
    "MemoryEntry",
    "MemorySearchResult",
    "MemoryType",
    "MessageRole",
    "ProjectContext",
]