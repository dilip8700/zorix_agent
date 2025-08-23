"""Conversation memory management for session-based context."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.models import (
    ConversationMessage,
    ConversationSession,
    MemoryEntry,
    MemoryType,
    MessageRole,
)
from agent.security.sandbox import SecuritySandbox

logger = logging.getLogger(__name__)


class ConversationMemoryError(Exception):
    """Exception for conversation memory operations."""
    pass


class ConversationMemory:
    """Manages conversation sessions and message history."""
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        bedrock_client: Optional[BedrockClient] = None,
        max_sessions: int = 100,
        max_messages_per_session: int = 1000,
    ):
        """Initialize conversation memory.
        
        Args:
            storage_path: Path to store conversation data
            bedrock_client: Bedrock client for embeddings
            max_sessions: Maximum number of sessions to keep
            max_messages_per_session: Maximum messages per session
        """
        settings = get_settings()
        
        self.storage_path = storage_path or Path(settings.memory_db_path) / "conversations"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.bedrock = bedrock_client or BedrockClient()
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        
        # In-memory cache
        self.sessions: Dict[str, ConversationSession] = {}
        self.current_session_id: Optional[str] = None
        
        # Load existing sessions
        self._load_sessions()
        
        logger.info(f"Initialized ConversationMemory with {len(self.sessions)} sessions")
    
    def _load_sessions(self):
        """Load existing sessions from storage."""
        try:
            sessions_file = self.storage_path / "sessions.json"
            if sessions_file.exists():
                with open(sessions_file, 'r', encoding='utf-8') as f:
                    sessions_data = json.load(f)
                
                for session_data in sessions_data:
                    session = ConversationSession.from_dict(session_data)
                    self.sessions[session.id] = session
                
                logger.info(f"Loaded {len(self.sessions)} conversation sessions")
            
            # Load current session ID
            current_file = self.storage_path / "current_session.txt"
            if current_file.exists():
                self.current_session_id = current_file.read_text().strip()
                
        except Exception as e:
            logger.error(f"Failed to load conversation sessions: {e}")
    
    def _save_sessions(self):
        """Save sessions to storage."""
        try:
            sessions_file = self.storage_path / "sessions.json"
            sessions_data = [session.to_dict() for session in self.sessions.values()]
            
            with open(sessions_file, 'w', encoding='utf-8') as f:
                json.dump(sessions_data, f, indent=2, ensure_ascii=False)
            
            # Save current session ID
            if self.current_session_id:
                current_file = self.storage_path / "current_session.txt"
                current_file.write_text(self.current_session_id)
            
            logger.debug(f"Saved {len(self.sessions)} conversation sessions")
            
        except Exception as e:
            logger.error(f"Failed to save conversation sessions: {e}")
    
    def create_session(
        self,
        title: str = "",
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationSession:
        """Create a new conversation session.
        
        Args:
            title: Session title
            project_id: Associated project ID
            metadata: Additional metadata
            
        Returns:
            New conversation session
        """
        session = ConversationSession(
            title=title,
            project_id=project_id,
            metadata=metadata or {}
        )
        
        self.sessions[session.id] = session
        self.current_session_id = session.id
        
        # Clean up old sessions if needed
        self._cleanup_old_sessions()
        
        # Save to storage
        self._save_sessions()
        
        logger.info(f"Created new conversation session: {session.id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get a conversation session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Conversation session or None if not found
        """
        return self.sessions.get(session_id)
    
    def get_current_session(self) -> Optional[ConversationSession]:
        """Get the current active session.
        
        Returns:
            Current session or None
        """
        if self.current_session_id:
            return self.sessions.get(self.current_session_id)
        return None
    
    def set_current_session(self, session_id: str) -> bool:
        """Set the current active session.
        
        Args:
            session_id: Session ID to make current
            
        Returns:
            True if successful, False if session not found
        """
        if session_id in self.sessions:
            self.current_session_id = session_id
            self._save_sessions()
            return True
        return False
    
    def add_message(
        self,
        content: str,
        role: MessageRole = MessageRole.USER,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None
    ) -> ConversationMessage:
        """Add a message to a conversation session.
        
        Args:
            content: Message content
            role: Message role
            session_id: Session ID (uses current if None)
            metadata: Additional metadata
            tool_calls: Tool calls made in this message
            tool_results: Results from tool calls
            
        Returns:
            Created message
        """
        # Use current session or create new one
        if session_id:
            session = self.get_session(session_id)
            if not session:
                raise ConversationMemoryError(f"Session not found: {session_id}")
        else:
            session = self.get_current_session()
            if not session:
                session = self.create_session()
        
        # Create message
        message = ConversationMessage(
            content=content,
            role=role,
            metadata=metadata or {},
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        
        # Add to session
        session.add_message(message)
        
        # Cleanup old messages if needed
        self._cleanup_session_messages(session)
        
        # Save to storage
        self._save_sessions()
        
        logger.debug(f"Added message to session {session.id}: {role.value}")
        return message
    
    def get_conversation_context(
        self,
        session_id: Optional[str] = None,
        max_messages: int = 20,
        include_system: bool = True
    ) -> List[ConversationMessage]:
        """Get conversation context for a session.
        
        Args:
            session_id: Session ID (uses current if None)
            max_messages: Maximum number of messages to return
            include_system: Whether to include system messages
            
        Returns:
            List of conversation messages
        """
        session = self.get_session(session_id) if session_id else self.get_current_session()
        if not session:
            return []
        
        messages = session.get_recent_messages(max_messages)
        
        if not include_system:
            messages = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        
        return messages
    
    def search_conversations(
        self,
        query: str,
        project_id: Optional[str] = None,
        max_results: int = 10,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Search conversation history.
        
        Args:
            query: Search query
            project_id: Filter by project ID
            max_results: Maximum results to return
            days_back: How many days back to search
            
        Returns:
            List of matching messages with context
        """
        results = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        query_lower = query.lower()
        
        for session in self.sessions.values():
            # Filter by project if specified
            if project_id and session.project_id != project_id:
                continue
            
            # Filter by date
            if session.updated_at < cutoff_date:
                continue
            
            # Search messages in session
            for i, message in enumerate(session.messages):
                if message.timestamp < cutoff_date:
                    continue
                
                # Simple text search (could be enhanced with embeddings)
                if query_lower in message.content.lower():
                    # Get context around the message
                    context_start = max(0, i - 2)
                    context_end = min(len(session.messages), i + 3)
                    context_messages = session.messages[context_start:context_end]
                    
                    results.append({
                        "session_id": session.id,
                        "session_title": session.title,
                        "message": message.to_dict(),
                        "context": [msg.to_dict() for msg in context_messages],
                        "timestamp": message.timestamp.isoformat(),
                    })
        
        # Sort by timestamp (most recent first)
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return results[:max_results]
    
    def get_session_summary(self, session_id: str) -> Optional[str]:
        """Get a summary of a conversation session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session summary or None if not found
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        message_count = session.get_message_count()
        if message_count == 0:
            return "Empty conversation"
        
        # Get first and last messages for context
        first_msg = session.messages[0] if session.messages else None
        last_msg = session.messages[-1] if session.messages else None
        
        duration = (session.updated_at - session.created_at).total_seconds() / 3600  # hours
        
        summary_parts = [
            f"Session: {session.title or 'Untitled'}",
            f"Messages: {message_count}",
            f"Duration: {duration:.1f} hours",
        ]
        
        if first_msg:
            first_preview = first_msg.content[:100] + "..." if len(first_msg.content) > 100 else first_msg.content
            summary_parts.append(f"Started with: {first_preview}")
        
        return "\n".join(summary_parts)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a conversation session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            
            # Clear current session if it was deleted
            if self.current_session_id == session_id:
                self.current_session_id = None
            
            self._save_sessions()
            logger.info(f"Deleted conversation session: {session_id}")
            return True
        
        return False
    
    def list_sessions(
        self,
        project_id: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List conversation sessions.
        
        Args:
            project_id: Filter by project ID
            active_only: Only return active sessions
            limit: Maximum number of sessions to return
            
        Returns:
            List of session summaries
        """
        sessions = []
        
        for session in self.sessions.values():
            # Apply filters
            if project_id and session.project_id != project_id:
                continue
            
            if active_only and not session.is_active:
                continue
            
            sessions.append({
                "id": session.id,
                "title": session.title,
                "message_count": session.get_message_count(),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "project_id": session.project_id,
                "is_current": session.id == self.current_session_id,
            })
        
        # Sort by update time (most recent first)
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        
        return sessions[:limit]
    
    def _cleanup_old_sessions(self):
        """Remove old sessions if we exceed the limit."""
        if len(self.sessions) <= self.max_sessions:
            return
        
        # Sort sessions by update time
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.updated_at
        )
        
        # Remove oldest sessions
        sessions_to_remove = sorted_sessions[:len(self.sessions) - self.max_sessions]
        
        for session in sessions_to_remove:
            if session.id != self.current_session_id:  # Don't remove current session
                del self.sessions[session.id]
                logger.info(f"Removed old session: {session.id}")
    
    def _cleanup_session_messages(self, session: ConversationSession):
        """Remove old messages from a session if it exceeds the limit."""
        if len(session.messages) <= self.max_messages_per_session:
            return
        
        # Keep the most recent messages
        messages_to_keep = self.max_messages_per_session
        session.messages = session.messages[-messages_to_keep:]
        
        logger.debug(f"Trimmed session {session.id} to {messages_to_keep} messages")
    
    async def create_memory_entries(
        self,
        session_id: str,
        importance_threshold: float = 0.7
    ) -> List[MemoryEntry]:
        """Create memory entries from conversation session.
        
        Args:
            session_id: Session ID to process
            importance_threshold: Minimum importance for creating memories
            
        Returns:
            List of created memory entries
        """
        session = self.get_session(session_id)
        if not session:
            return []
        
        memories = []
        
        # Process messages in chunks to create meaningful memories
        message_chunks = self._chunk_messages(session.messages)
        
        for chunk in message_chunks:
            # Calculate importance based on content and context
            importance = self._calculate_message_importance(chunk)
            
            if importance >= importance_threshold:
                # Create summary of the chunk
                summary = self._summarize_message_chunk(chunk)
                content = "\n".join([msg.content for msg in chunk])
                
                # Generate embedding for the content
                embedding = None
                try:
                    embeddings = await self.bedrock.generate_embeddings([content])
                    if embeddings:
                        embedding = embeddings[0]
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for memory: {e}")
                
                memory = MemoryEntry(
                    memory_type=MemoryType.CONVERSATION,
                    content=content,
                    summary=summary,
                    session_id=session_id,
                    project_id=session.project_id,
                    importance=importance,
                    embedding=embedding,
                    metadata={
                        "message_count": len(chunk),
                        "session_title": session.title,
                        "start_time": chunk[0].timestamp.isoformat(),
                        "end_time": chunk[-1].timestamp.isoformat(),
                    }
                )
                
                memories.append(memory)
        
        logger.info(f"Created {len(memories)} memory entries from session {session_id}")
        return memories
    
    def _chunk_messages(self, messages: List[ConversationMessage]) -> List[List[ConversationMessage]]:
        """Chunk messages into meaningful conversation segments."""
        if not messages:
            return []
        
        chunks = []
        current_chunk = []
        
        for message in messages:
            current_chunk.append(message)
            
            # End chunk on natural conversation breaks
            if (
                len(current_chunk) >= 5 or  # Max chunk size
                message.role == MessageRole.ASSISTANT and len(current_chunk) >= 2  # End on assistant response
            ):
                chunks.append(current_chunk)
                current_chunk = []
        
        # Add remaining messages
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _calculate_message_importance(self, messages: List[ConversationMessage]) -> float:
        """Calculate importance score for a message chunk."""
        if not messages:
            return 0.0
        
        importance_factors = []
        
        # Length factor (longer conversations are more important)
        total_length = sum(len(msg.content) for msg in messages)
        length_factor = min(1.0, total_length / 1000)  # Normalize to 1000 chars
        importance_factors.append(length_factor * 0.3)
        
        # Tool usage factor (conversations with tools are more important)
        has_tools = any(msg.tool_calls for msg in messages)
        if has_tools:
            importance_factors.append(0.4)
        
        # Question/answer factor (Q&A is more important)
        has_questions = any('?' in msg.content for msg in messages)
        if has_questions:
            importance_factors.append(0.2)
        
        # Code factor (code discussions are important)
        has_code = any('```' in msg.content or 'def ' in msg.content for msg in messages)
        if has_code:
            importance_factors.append(0.3)
        
        # Base importance
        importance_factors.append(0.1)
        
        return min(1.0, sum(importance_factors))
    
    def _summarize_message_chunk(self, messages: List[ConversationMessage]) -> str:
        """Create a summary of a message chunk."""
        if not messages:
            return ""
        
        # Simple extractive summary for now
        # In production, this could use LLM summarization
        
        user_messages = [msg for msg in messages if msg.role == MessageRole.USER]
        assistant_messages = [msg for msg in messages if msg.role == MessageRole.ASSISTANT]
        
        summary_parts = []
        
        if user_messages:
            first_user = user_messages[0].content[:100]
            summary_parts.append(f"User asked: {first_user}")
        
        if assistant_messages:
            last_assistant = assistant_messages[-1].content[:100]
            summary_parts.append(f"Assistant responded: {last_assistant}")
        
        # Add tool usage info
        tools_used = set()
        for msg in messages:
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tools_used.add(tool_call.get('function', {}).get('name', 'unknown'))
        
        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(tools_used)}")
        
        return " | ".join(summary_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation memory statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_messages = sum(len(session.messages) for session in self.sessions.values())
        active_sessions = sum(1 for session in self.sessions.values() if session.is_active)
        
        # Calculate average session length
        session_lengths = [len(session.messages) for session in self.sessions.values()]
        avg_session_length = sum(session_lengths) / len(session_lengths) if session_lengths else 0
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "total_messages": total_messages,
            "average_session_length": avg_session_length,
            "current_session_id": self.current_session_id,
            "storage_path": str(self.storage_path),
        }