"""Main memory provider that orchestrates conversation and project memory."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.conversation import ConversationMemory
from agent.memory.models import (
    ConversationMessage,
    ConversationSession,
    MemoryEntry,
    MemorySearchResult,
    MemoryType,
    MessageRole,
    ProjectContext,
)
from agent.memory.project import ProjectMemory
from agent.vector.index import VectorIndex

logger = logging.getLogger(__name__)


class MemoryProviderError(Exception):
    """Exception for memory provider operations."""
    pass


class MemoryProvider:
    """Main memory provider that orchestrates conversation and project memory."""
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        bedrock_client: Optional[BedrockClient] = None,
        vector_index: Optional[VectorIndex] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize memory provider.
        
        Args:
            storage_path: Path to store memory data
            bedrock_client: Bedrock client for embeddings
            vector_index: Vector index for semantic search
            workspace_root: Root directory for workspace operations
        """
        settings = get_settings()
        
        self.storage_path = storage_path or Path(settings.memory_db_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.bedrock = bedrock_client or BedrockClient()
        self.vector_index = vector_index
        self.workspace_root = workspace_root or settings.workspace_root
        
        # Initialize memory components
        self.conversation_memory = ConversationMemory(
            storage_path=self.storage_path / "conversations",
            bedrock_client=self.bedrock
        )
        
        self.project_memory = ProjectMemory(
            storage_path=self.storage_path / "projects",
            bedrock_client=self.bedrock,
            vector_index=self.vector_index,
            workspace_root=self.workspace_root
        )
        
        logger.info("Initialized MemoryProvider")
    
    # Conversation Memory Methods
    
    def create_conversation_session(
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
        # Use current project if not specified
        if not project_id:
            current_project = self.project_memory.get_current_project()
            if current_project:
                project_id = current_project.id
        
        return self.conversation_memory.create_session(
            title=title,
            project_id=project_id,
            metadata=metadata
        )
    
    def add_conversation_message(
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
        return self.conversation_memory.add_message(
            content=content,
            role=role,
            session_id=session_id,
            metadata=metadata,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
    
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
        return self.conversation_memory.get_conversation_context(
            session_id=session_id,
            max_messages=max_messages,
            include_system=include_system
        )
    
    # Project Memory Methods
    
    def create_project(
        self,
        name: str,
        description: str = "",
        workspace_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProjectContext:
        """Create a new project context.
        
        Args:
            name: Project name
            description: Project description
            workspace_path: Path to project workspace
            metadata: Additional metadata
            
        Returns:
            New project context
        """
        return self.project_memory.create_project(
            name=name,
            description=description,
            workspace_path=workspace_path,
            metadata=metadata
        )
    
    def get_current_project(self) -> Optional[ProjectContext]:
        """Get the current active project.
        
        Returns:
            Current project or None
        """
        return self.project_memory.get_current_project()
    
    def set_current_project(self, project_id: str) -> bool:
        """Set the current active project.
        
        Args:
            project_id: Project ID to make current
            
        Returns:
            True if successful, False if project not found
        """
        return self.project_memory.set_current_project(project_id)
    
    async def add_project_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT,
        project_id: Optional[str] = None,
        summary: str = "",
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        generate_embedding: bool = True
    ) -> MemoryEntry:
        """Add a memory entry to a project.
        
        Args:
            content: Memory content
            memory_type: Type of memory
            project_id: Project ID (uses current if None)
            summary: Memory summary
            tags: Memory tags
            importance: Importance score (0.0 to 1.0)
            metadata: Additional metadata
            generate_embedding: Whether to generate embedding
            
        Returns:
            Created memory entry
        """
        if generate_embedding:
            return await self.project_memory.add_memory_with_embedding(
                content=content,
                memory_type=memory_type,
                project_id=project_id,
                summary=summary,
                tags=tags,
                importance=importance,
                metadata=metadata
            )
        else:
            return self.project_memory.add_memory(
                content=content,
                memory_type=memory_type,
                project_id=project_id,
                summary=summary,
                tags=tags,
                importance=importance,
                metadata=metadata
            )
    
    # Unified Search Methods
    
    async def search_memories(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_types: Optional[List[MemoryType]] = None,
        include_conversations: bool = True,
        include_project_memories: bool = True,
        max_results: int = 10,
        min_importance: float = 0.0,
        use_semantic_search: bool = True
    ) -> List[MemorySearchResult]:
        """Search across all memory types.
        
        Args:
            query: Search query
            project_id: Project ID to filter by
            memory_types: Filter by memory types
            include_conversations: Whether to search conversations
            include_project_memories: Whether to search project memories
            max_results: Maximum results to return
            min_importance: Minimum importance threshold
            use_semantic_search: Whether to use semantic search with embeddings
            
        Returns:
            List of memory search results
        """
        results = []
        
        # Search project memories
        if include_project_memories:
            project_results = self.project_memory.search_memories(
                query=query,
                project_id=project_id,
                memory_types=memory_types,
                min_importance=min_importance,
                max_results=max_results
            )
            
            for memory in project_results:
                results.append(MemorySearchResult(
                    entry=memory,
                    score=memory.importance,
                    relevance_reason="Project memory match"
                ))
        
        # Search conversations
        if include_conversations:
            conversation_results = self.conversation_memory.search_conversations(
                query=query,
                project_id=project_id,
                max_results=max_results
            )
            
            for result in conversation_results:
                # Convert conversation result to memory entry
                message_data = result["message"]
                memory = MemoryEntry(
                    memory_type=MemoryType.CONVERSATION,
                    content=message_data["content"],
                    summary=f"Conversation in {result['session_title']}",
                    session_id=result["session_id"],
                    project_id=project_id,
                    timestamp=datetime.fromisoformat(message_data["timestamp"]),
                    metadata={
                        "session_title": result["session_title"],
                        "message_role": message_data["role"],
                        "context_messages": len(result["context"])
                    }
                )
                
                results.append(MemorySearchResult(
                    entry=memory,
                    score=0.7,  # Default score for conversation matches
                    relevance_reason="Conversation history match"
                ))
        
        # Sort by score and importance
        results.sort(key=lambda r: (r.score, r.entry.importance), reverse=True)
        
        return results[:max_results]
    
    async def semantic_search(
        self,
        query: str,
        project_id: Optional[str] = None,
        max_results: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[MemorySearchResult]:
        """Perform semantic search using embeddings.
        
        Args:
            query: Search query
            project_id: Project ID to filter by
            max_results: Maximum results to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of memory search results
        """
        try:
            # Generate query embedding
            query_embeddings = await self.bedrock.generate_embeddings([query])
            if not query_embeddings:
                logger.warning("Failed to generate query embedding for semantic search")
                return []
            
            query_embedding = query_embeddings[0]
            
            # Search project memories with embeddings
            project_memories = []
            if project_id:
                project_memories = self.project_memory.project_memories.get(project_id, [])
            else:
                # Search all projects
                for memories in self.project_memory.project_memories.values():
                    project_memories.extend(memories)
            
            results = []
            
            for memory in project_memories:
                if not memory.embedding:
                    continue
                
                # Calculate cosine similarity
                similarity = self._calculate_cosine_similarity(
                    query_embedding,
                    memory.embedding
                )
                
                if similarity >= similarity_threshold:
                    results.append(MemorySearchResult(
                        entry=memory,
                        score=similarity,
                        relevance_reason=f"Semantic similarity: {similarity:.3f}"
                    ))
            
            # Sort by similarity score
            results.sort(key=lambda r: r.score, reverse=True)
            
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            import math
            
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            
            # Calculate magnitudes
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))
            
            # Calculate cosine similarity
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception:
            return 0.0
    
    # Context Management Methods
    
    def get_full_context(
        self,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        max_conversation_messages: int = 20,
        max_project_memories: int = 10,
        include_workspace_analysis: bool = True
    ) -> Dict[str, Any]:
        """Get comprehensive context including project and conversation data.
        
        Args:
            project_id: Project ID (uses current if None)
            session_id: Session ID (uses current if None)
            max_conversation_messages: Maximum conversation messages
            max_project_memories: Maximum project memories
            include_workspace_analysis: Whether to include workspace analysis
            
        Returns:
            Dictionary with full context
        """
        context = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation": {},
            "project": {},
            "memories": []
        }
        
        # Get conversation context
        conversation_messages = self.get_conversation_context(
            session_id=session_id,
            max_messages=max_conversation_messages
        )
        
        context["conversation"] = {
            "messages": [msg.to_dict() for msg in conversation_messages],
            "message_count": len(conversation_messages),
            "session_id": session_id or self.conversation_memory.current_session_id
        }
        
        # Get project context
        project_context = self.project_memory.get_project_context(
            project_id=project_id,
            include_memories=True,
            memory_limit=max_project_memories
        )
        
        context["project"] = project_context
        
        return context
    
    async def create_conversation_memories(
        self,
        session_id: Optional[str] = None,
        importance_threshold: float = 0.7
    ) -> List[MemoryEntry]:
        """Create memory entries from conversation session.
        
        Args:
            session_id: Session ID (uses current if None)
            importance_threshold: Minimum importance for creating memories
            
        Returns:
            List of created memory entries
        """
        if not session_id:
            session_id = self.conversation_memory.current_session_id
            if not session_id:
                return []
        
        # Create memories from conversation
        memories = await self.conversation_memory.create_memory_entries(
            session_id=session_id,
            importance_threshold=importance_threshold
        )
        
        # Add memories to project memory if project is associated
        session = self.conversation_memory.get_session(session_id)
        if session and session.project_id:
            for memory in memories:
                # Add to project memory system
                self.project_memory.project_memories.setdefault(session.project_id, []).append(memory)
            
            # Save project memories
            if memories:
                self.project_memory._save_project_memories(session.project_id)
        
        return memories
    
    # Cleanup and Optimization Methods
    
    async def optimize_memories(
        self,
        project_id: Optional[str] = None,
        max_memories_per_project: int = 1000,
        importance_threshold: float = 0.3
    ):
        """Optimize memory storage by removing low-importance entries.
        
        Args:
            project_id: Project ID (optimizes current if None)
            max_memories_per_project: Maximum memories to keep per project
            importance_threshold: Minimum importance to keep
        """
        projects_to_optimize = []
        
        if project_id:
            if project_id in self.project_memory.project_memories:
                projects_to_optimize = [project_id]
        else:
            # Optimize all projects
            projects_to_optimize = list(self.project_memory.project_memories.keys())
        
        for pid in projects_to_optimize:
            memories = self.project_memory.project_memories[pid]
            
            # Filter by importance
            important_memories = [
                memory for memory in memories
                if memory.importance >= importance_threshold
            ]
            
            # Sort by importance and access patterns
            important_memories.sort(
                key=lambda m: (m.importance, m.access_count, m.timestamp.timestamp()),
                reverse=True
            )
            
            # Keep only the most important memories
            optimized_memories = important_memories[:max_memories_per_project]
            
            # Update memory storage
            removed_count = len(memories) - len(optimized_memories)
            self.project_memory.project_memories[pid] = optimized_memories
            
            # Save optimized memories
            self.project_memory._save_project_memories(pid)
            
            if removed_count > 0:
                logger.info(f"Optimized project {pid}: removed {removed_count} low-importance memories")
    
    async def regenerate_embeddings(
        self,
        project_id: Optional[str] = None,
        force_regenerate: bool = False
    ):
        """Regenerate embeddings for memories that don't have them.
        
        Args:
            project_id: Project ID (processes current if None)
            force_regenerate: Whether to regenerate existing embeddings
        """
        projects_to_process = []
        
        if project_id:
            if project_id in self.project_memory.project_memories:
                projects_to_process = [project_id]
        else:
            # Process all projects
            projects_to_process = list(self.project_memory.project_memories.keys())
        
        for pid in projects_to_process:
            memories = self.project_memory.project_memories[pid]
            memories_to_process = []
            
            for memory in memories:
                if force_regenerate or not memory.embedding:
                    memories_to_process.append(memory)
            
            if not memories_to_process:
                continue
            
            # Generate embeddings in batches
            batch_size = 10
            for i in range(0, len(memories_to_process), batch_size):
                batch = memories_to_process[i:i + batch_size]
                contents = [memory.content for memory in batch]
                
                try:
                    embeddings = await self.bedrock.generate_embeddings(contents)
                    
                    for memory, embedding in zip(batch, embeddings):
                        memory.embedding = embedding
                    
                    logger.info(f"Generated embeddings for {len(batch)} memories in project {pid}")
                    
                except Exception as e:
                    logger.error(f"Failed to generate embeddings for project {pid}: {e}")
            
            # Save updated memories
            if memories_to_process:
                self.project_memory._save_project_memories(pid)
    
    # Statistics and Monitoring
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory system statistics.
        
        Returns:
            Dictionary with memory statistics
        """
        conversation_stats = self.conversation_memory.get_stats()
        
        # Project memory stats
        total_project_memories = sum(
            len(memories) for memories in self.project_memory.project_memories.values()
        )
        
        memories_with_embeddings = 0
        total_importance = 0.0
        
        for memories in self.project_memory.project_memories.values():
            for memory in memories:
                if memory.embedding:
                    memories_with_embeddings += 1
                total_importance += memory.importance
        
        avg_importance = total_importance / total_project_memories if total_project_memories > 0 else 0
        
        project_stats = {
            "total_projects": len(self.project_memory.projects),
            "active_projects": sum(1 for p in self.project_memory.projects.values() if p.is_active),
            "current_project_id": self.project_memory.current_project_id,
            "total_project_memories": total_project_memories,
            "memories_with_embeddings": memories_with_embeddings,
            "average_importance": avg_importance,
        }
        
        return {
            "conversation": conversation_stats,
            "project": project_stats,
            "storage_path": str(self.storage_path),
            "total_memories": conversation_stats["total_messages"] + total_project_memories,
        }
    
    # Utility Methods
    
    def list_sessions(
        self,
        project_id: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List conversation sessions."""
        return self.conversation_memory.list_sessions(
            project_id=project_id,
            active_only=active_only,
            limit=limit
        )
    
    def list_projects(
        self,
        active_only: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List projects."""
        return self.project_memory.list_projects(
            active_only=active_only,
            limit=limit
        )
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a conversation session."""
        return self.conversation_memory.delete_session(session_id)
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and its memories."""
        return self.project_memory.delete_project(project_id)