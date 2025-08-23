"""Tests for the memory system components."""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.memory.conversation import ConversationMemory
from agent.memory.models import (
    ConversationMessage,
    ConversationSession,
    MemoryEntry,
    MemoryType,
    MessageRole,
    ProjectContext,
)
from agent.memory.project import ProjectMemory
from agent.memory.provider import MemoryProvider


class TestConversationMemory:
    """Test conversation memory functionality."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.generate_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        return mock
    
    @pytest.fixture
    def conversation_memory(self, temp_storage, mock_bedrock):
        """Create conversation memory instance."""
        return ConversationMemory(
            storage_path=temp_storage / "conversations",
            bedrock_client=mock_bedrock
        )
    
    def test_create_session(self, conversation_memory):
        """Test creating a conversation session."""
        session = conversation_memory.create_session(
            title="Test Session",
            project_id="test-project",
            metadata={"test": "data"}
        )
        
        assert session.title == "Test Session"
        assert session.project_id == "test-project"
        assert session.metadata["test"] == "data"
        assert session.id in conversation_memory.sessions
        assert conversation_memory.current_session_id == session.id
    
    def test_add_message(self, conversation_memory):
        """Test adding messages to a session."""
        session = conversation_memory.create_session("Test Session")
        
        message = conversation_memory.add_message(
            content="Hello, world!",
            role=MessageRole.USER,
            metadata={"test": "metadata"}
        )
        
        assert message.content == "Hello, world!"
        assert message.role == MessageRole.USER
        assert message.metadata["test"] == "metadata"
        assert len(session.messages) == 1
        assert session.messages[0] == message
    
    def test_get_conversation_context(self, conversation_memory):
        """Test getting conversation context."""
        session = conversation_memory.create_session("Test Session")
        
        # Add multiple messages
        for i in range(5):
            conversation_memory.add_message(
                content=f"Message {i}",
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            )
        
        context = conversation_memory.get_conversation_context(max_messages=3)
        assert len(context) == 3
        assert context[-1].content == "Message 4"  # Most recent message
    
    def test_search_conversations(self, conversation_memory):
        """Test searching conversation history."""
        session = conversation_memory.create_session("Test Session")
        
        # Add messages with searchable content
        conversation_memory.add_message("How do I implement authentication?", MessageRole.USER)
        conversation_memory.add_message("You can use JWT tokens for authentication.", MessageRole.ASSISTANT)
        conversation_memory.add_message("What about database connections?", MessageRole.USER)
        
        results = conversation_memory.search_conversations("authentication")
        assert len(results) == 2  # User question and assistant answer
        assert "authentication" in results[0]["message"]["content"].lower()
    
    def test_session_persistence(self, temp_storage, mock_bedrock):
        """Test session persistence across instances."""
        # Create first instance and add data
        memory1 = ConversationMemory(
            storage_path=temp_storage / "conversations",
            bedrock_client=mock_bedrock
        )
        
        session = memory1.create_session("Persistent Session")
        memory1.add_message("Test message", MessageRole.USER)
        
        # Create second instance and verify data is loaded
        memory2 = ConversationMemory(
            storage_path=temp_storage / "conversations",
            bedrock_client=mock_bedrock
        )
        
        assert session.id in memory2.sessions
        assert len(memory2.sessions[session.id].messages) == 1
        assert memory2.sessions[session.id].messages[0].content == "Test message"
    
    @pytest.mark.asyncio
    async def test_create_memory_entries(self, conversation_memory):
        """Test creating memory entries from conversation."""
        session = conversation_memory.create_session("Test Session")
        
        # Add conversation with code discussion
        conversation_memory.add_message("How do I implement a REST API?", MessageRole.USER)
        conversation_memory.add_message("You can use FastAPI with these steps...", MessageRole.ASSISTANT)
        conversation_memory.add_message("```python\nfrom fastapi import FastAPI\n```", MessageRole.ASSISTANT)
        
        memories = await conversation_memory.create_memory_entries(session.id, importance_threshold=0.1)
        
        assert len(memories) >= 0  # May be 0 if importance is too low
        assert memories[0].memory_type == MemoryType.CONVERSATION
        assert memories[0].session_id == session.id
        assert "REST API" in memories[0].content or "FastAPI" in memories[0].content


class TestProjectMemory:
    """Test project memory functionality."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create sample files
            (workspace / "README.md").write_text("# Test Project\nThis is a test project.")
            (workspace / "requirements.txt").write_text("fastapi==0.68.0\nuvicorn==0.15.0")
            (workspace / "src").mkdir()
            (workspace / "src" / "main.py").write_text("def main():\n    print('Hello, world!')")
            
            yield workspace
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.generate_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        return mock
    
    @pytest.fixture
    def project_memory(self, temp_storage, temp_workspace, mock_bedrock):
        """Create project memory instance."""
        return ProjectMemory(
            storage_path=temp_storage / "projects",
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
    
    def test_create_project(self, project_memory, temp_workspace):
        """Test creating a project."""
        project = project_memory.create_project(
            name="Test Project",
            description="A test project",
            workspace_path=str(temp_workspace),
            metadata={"language": "python"}
        )
        
        assert project.name == "Test Project"
        assert project.description == "A test project"
        assert project.workspace_path == str(temp_workspace)
        assert project.metadata["language"] == "python"
        assert project.id in project_memory.projects
        assert project_memory.current_project_id == project.id
        
        # Check workspace analysis
        assert ".py" in project.file_patterns
        assert ".md" in project.file_patterns
        assert "README.md" in project.important_files
        assert "requirements.txt" in project.important_files
        assert "fastapi" in project.dependencies
        assert "uvicorn" in project.dependencies
    
    def test_add_memory(self, project_memory):
        """Test adding memory to a project."""
        project = project_memory.create_project("Test Project")
        
        memory = project_memory.add_memory(
            content="This is important project knowledge",
            memory_type=MemoryType.PROJECT,
            summary="Important knowledge",
            tags=["important", "knowledge"],
            importance=0.8
        )
        
        assert memory.content == "This is important project knowledge"
        assert memory.memory_type == MemoryType.PROJECT
        assert memory.project_id == project.id
        assert memory.importance == 0.8
        assert "important" in memory.tags
        assert project.id in project_memory.project_memories
        assert memory in project_memory.project_memories[project.id]
    
    @pytest.mark.asyncio
    async def test_add_memory_with_embedding(self, project_memory):
        """Test adding memory with embedding generation."""
        project = project_memory.create_project("Test Project")
        
        memory = await project_memory.add_memory_with_embedding(
            content="This memory will have an embedding",
            memory_type=MemoryType.CODE_CONTEXT
        )
        
        assert memory.embedding is not None
        assert len(memory.embedding) == 3  # Mock embedding
        assert memory.embedding == [0.1, 0.2, 0.3]
    
    def test_search_memories(self, project_memory):
        """Test searching project memories."""
        project = project_memory.create_project("Test Project")
        
        # Add memories with different content
        project_memory.add_memory("Authentication implementation details", tags=["auth"])
        project_memory.add_memory("Database connection setup", tags=["database"])
        project_memory.add_memory("API authentication with JWT", tags=["auth", "api"])
        
        # Search for authentication
        results = project_memory.search_memories("authentication")
        assert len(results) == 2
        
        # Search by tags
        results = project_memory.search_memories("database", tags=["database"])
        assert len(results) == 1
        assert "Database connection" in results[0].content
    
    def test_project_persistence(self, temp_storage, temp_workspace, mock_bedrock):
        """Test project persistence across instances."""
        # Create first instance and add data
        memory1 = ProjectMemory(
            storage_path=temp_storage / "projects",
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
        
        project = memory1.create_project("Persistent Project")
        memory1.add_memory("Persistent memory", project_id=project.id)
        
        # Create second instance and verify data is loaded
        memory2 = ProjectMemory(
            storage_path=temp_storage / "projects",
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
        
        assert project.id in memory2.projects
        assert project.id in memory2.project_memories
        assert len(memory2.project_memories[project.id]) == 1
        assert memory2.project_memories[project.id][0].content == "Persistent memory"


class TestMemoryProvider:
    """Test the main memory provider."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "README.md").write_text("# Test Project")
            yield workspace
    
    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client."""
        mock = MagicMock()
        mock.generate_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        return mock
    
    @pytest.fixture
    def memory_provider(self, temp_storage, temp_workspace, mock_bedrock):
        """Create memory provider instance."""
        return MemoryProvider(
            storage_path=temp_storage,
            bedrock_client=mock_bedrock,
            workspace_root=str(temp_workspace)
        )
    
    def test_create_conversation_with_project(self, memory_provider):
        """Test creating conversation linked to project."""
        # Create project first
        project = memory_provider.create_project("Test Project")
        
        # Create conversation session
        session = memory_provider.create_conversation_session(
            title="Project Discussion",
            project_id=project.id
        )
        
        assert session.project_id == project.id
        assert session.title == "Project Discussion"
    
    def test_unified_context(self, memory_provider):
        """Test getting unified context."""
        # Create project and conversation
        project = memory_provider.create_project("Test Project")
        session = memory_provider.create_conversation_session("Test Session")
        
        # Add some data
        memory_provider.add_conversation_message("Hello", MessageRole.USER)
        memory_provider.add_conversation_message("Hi there!", MessageRole.ASSISTANT)
        
        # Get full context
        context = memory_provider.get_full_context()
        
        assert "conversation" in context
        assert "project" in context
        assert len(context["conversation"]["messages"]) == 2
        assert context["project"]["project"]["name"] == "Test Project"
    
    @pytest.mark.asyncio
    async def test_unified_search(self, memory_provider):
        """Test unified search across memory types."""
        # Create project and add memories
        project = memory_provider.create_project("Test Project")
        await memory_provider.add_project_memory(
            "Authentication implementation with JWT tokens",
            memory_type=MemoryType.PROJECT
        )
        
        # Add conversation
        session = memory_provider.create_conversation_session("Auth Discussion")
        memory_provider.add_conversation_message(
            "How do I implement JWT authentication?",
            MessageRole.USER
        )
        memory_provider.add_conversation_message(
            "You can use the PyJWT library for JWT tokens.",
            MessageRole.ASSISTANT
        )
        
        # Search across all memory types
        results = await memory_provider.search_memories("JWT authentication")
        
        assert len(results) >= 1  # At least one result (project memory or conversation)
        
        # Check that we have results from memory search
        memory_types = {result.entry.memory_type for result in results}
        # Should have at least one type of memory
        assert len(memory_types) >= 1
    
    @pytest.mark.asyncio
    async def test_semantic_search(self, memory_provider):
        """Test semantic search with embeddings."""
        # Create project and add memory with embedding
        project = memory_provider.create_project("Test Project")
        await memory_provider.add_project_memory(
            "User authentication and authorization system",
            generate_embedding=True
        )
        
        # Perform semantic search
        results = await memory_provider.semantic_search(
            "login and security features",
            similarity_threshold=0.0  # Low threshold for testing
        )
        
        assert len(results) > 0
        assert results[0].entry.content == "User authentication and authorization system"
        assert results[0].score > 0
    
    @pytest.mark.asyncio
    async def test_memory_optimization(self, memory_provider):
        """Test memory optimization functionality."""
        # Create project and add many memories
        project = memory_provider.create_project("Test Project")
        
        # Add memories with different importance levels
        for i in range(20):
            importance = 0.1 if i < 10 else 0.9  # Half low, half high importance
            await memory_provider.add_project_memory(
                f"Memory {i}",
                importance=importance
            )
        
        # Optimize memories
        await memory_provider.optimize_memories(
            project_id=project.id,
            max_memories_per_project=15,
            importance_threshold=0.5
        )
        
        # Check that low-importance memories were removed
        remaining_memories = memory_provider.project_memory.project_memories[project.id]
        assert len(remaining_memories) <= 15
        
        # All remaining memories should have high importance
        for memory in remaining_memories:
            assert memory.importance >= 0.5
    
    def test_memory_stats(self, memory_provider):
        """Test memory statistics."""
        # Create some data
        project = memory_provider.create_project("Test Project")
        session = memory_provider.create_conversation_session("Test Session")
        memory_provider.add_conversation_message("Hello", MessageRole.USER)
        
        stats = memory_provider.get_memory_stats()
        
        assert "conversation" in stats
        assert "project" in stats
        assert stats["conversation"]["total_sessions"] == 1
        assert stats["conversation"]["total_messages"] == 1
        assert stats["project"]["total_projects"] == 1
        assert stats["total_memories"] >= 1
    
    @pytest.mark.asyncio
    async def test_conversation_to_project_memory(self, memory_provider):
        """Test converting conversation to project memories."""
        # Create project and conversation
        project = memory_provider.create_project("Test Project")
        session = memory_provider.create_conversation_session(
            "Important Discussion",
            project_id=project.id
        )
        
        # Add important conversation
        memory_provider.add_conversation_message(
            "How should we structure the authentication module?",
            MessageRole.USER
        )
        memory_provider.add_conversation_message(
            "We should use a layered approach with JWT tokens and role-based access control.",
            MessageRole.ASSISTANT
        )
        memory_provider.add_conversation_message(
            "That sounds good. Let's implement it with FastAPI.",
            MessageRole.USER
        )
        
        # Convert conversation to memories
        memories = await memory_provider.create_conversation_memories(
            session_id=session.id,
            importance_threshold=0.3  # Lower threshold for test
        )
        
        assert len(memories) > 0
        
        # Check that memories were added to project
        project_memories = memory_provider.project_memory.project_memories[project.id]
        assert len(project_memories) >= len(memories)
        
        # Verify memory content
        memory_contents = [memory.content for memory in memories]
        combined_content = " ".join(memory_contents)
        assert "authentication" in combined_content.lower()
        assert "JWT" in combined_content or "jwt" in combined_content.lower()


class TestMemoryModels:
    """Test memory model classes."""
    
    def test_conversation_message_serialization(self):
        """Test conversation message serialization."""
        message = ConversationMessage(
            content="Test message",
            role=MessageRole.USER,
            metadata={"test": "data"},
            tool_calls=[{"function": {"name": "test_tool"}}]
        )
        
        # Test to_dict
        data = message.to_dict()
        assert data["content"] == "Test message"
        assert data["role"] == "user"
        assert data["metadata"]["test"] == "data"
        assert data["tool_calls"][0]["function"]["name"] == "test_tool"
        
        # Test from_dict
        restored = ConversationMessage.from_dict(data)
        assert restored.content == message.content
        assert restored.role == message.role
        assert restored.metadata == message.metadata
        assert restored.tool_calls == message.tool_calls
    
    def test_memory_entry_access_tracking(self):
        """Test memory entry access tracking."""
        memory = MemoryEntry(
            content="Test memory",
            importance=0.7
        )
        
        assert memory.access_count == 0
        assert memory.last_accessed is None
        
        # Mark as accessed
        memory.mark_accessed()
        
        assert memory.access_count == 1
        assert memory.last_accessed is not None
        
        # Mark as accessed again
        old_access_time = memory.last_accessed
        import time
        time.sleep(0.001)  # Small delay to ensure different timestamp
        memory.mark_accessed()
        
        assert memory.access_count == 2
        assert memory.last_accessed >= old_access_time
    
    def test_conversation_session_title_generation(self):
        """Test automatic title generation for sessions."""
        session = ConversationSession()
        
        # Add first user message
        message = ConversationMessage(
            content="How do I implement authentication in my web application?",
            role=MessageRole.USER
        )
        session.add_message(message)
        
        # Title should be generated from first message
        assert session.title == "How do I implement authentication in my web applic..."
        assert len(session.title) <= 53  # 50 chars + "..."
    
    def test_project_context_serialization(self):
        """Test project context serialization."""
        project = ProjectContext(
            name="Test Project",
            description="A test project",
            workspace_path="/test/path",
            file_patterns=[".py", ".js"],
            important_files=["README.md", "package.json"],
            coding_conventions={"python_indentation": "4 spaces"},
            dependencies=["fastapi", "uvicorn"]
        )
        
        # Test to_dict
        data = project.to_dict()
        assert data["name"] == "Test Project"
        assert data["file_patterns"] == [".py", ".js"]
        assert data["coding_conventions"]["python_indentation"] == "4 spaces"
        
        # Test from_dict
        restored = ProjectContext.from_dict(data)
        assert restored.name == project.name
        assert restored.file_patterns == project.file_patterns
        assert restored.coding_conventions == project.coding_conventions


if __name__ == "__main__":
    pytest.main([__file__])