"""Tests for streaming chat functionality."""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agent.web.streaming import (
    StreamEvent,
    StreamEventType,
    StreamingChatHandler,
    StreamingChatSession,
    StreamingManager,
)


class TestStreamEvent:
    """Test StreamEvent functionality."""
    
    def test_stream_event_creation(self):
        """Test creating a stream event."""
        event = StreamEvent(
            event_type=StreamEventType.MESSAGE_START,
            event_id="test-123",
            timestamp=datetime.now(),
            session_id="session-123",
            data={"message": "Hello"}
        )
        
        assert event.event_type == StreamEventType.MESSAGE_START
        assert event.event_id == "test-123"
        assert event.session_id == "session-123"
        assert event.data["message"] == "Hello"
    
    def test_stream_event_to_sse(self):
        """Test converting stream event to SSE format."""
        event = StreamEvent(
            event_type=StreamEventType.MESSAGE_DELTA,
            event_id="test-123",
            timestamp=datetime.now(),
            session_id="session-123",
            data={"delta": "Hello", "accumulated": "Hello"}
        )
        
        sse_output = event.to_sse()
        
        assert "event: message_delta" in sse_output
        assert "id: test-123" in sse_output
        assert "data: " in sse_output
        assert "session-123" in sse_output
        assert sse_output.endswith("\n\n")


class TestStreamingChatSession:
    """Test StreamingChatSession functionality."""
    
    def test_session_creation(self):
        """Test creating a streaming session."""
        session = StreamingChatSession("test-session")
        
        assert session.session_id == "test-session"
        assert session.is_active is True
        assert session.client_count == 0
        assert len(session.message_buffer) == 0
    
    def test_client_management(self):
        """Test adding and removing clients."""
        session = StreamingChatSession("test-session")
        
        # Add clients
        session.add_client()
        assert session.client_count == 1
        assert session.is_active is True
        
        session.add_client()
        assert session.client_count == 2
        
        # Remove clients
        session.remove_client()
        assert session.client_count == 1
        assert session.is_active is True
        
        session.remove_client()
        assert session.client_count == 0
        assert session.is_active is False
    
    def test_session_expiry(self):
        """Test session expiry logic."""
        session = StreamingChatSession("test-session")
        
        # Fresh session should not be expired
        assert session.is_expired(timeout_seconds=3600) is False
        
        # Test with very short timeout
        assert session.is_expired(timeout_seconds=0) is True


class TestStreamingManager:
    """Test StreamingManager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a streaming manager for testing."""
        return StreamingManager()
    
    def test_get_or_create_session(self, manager):
        """Test getting or creating sessions."""
        session_id = "test-session"
        
        # Should create new session
        session1 = manager.get_or_create_session(session_id)
        assert session1.session_id == session_id
        assert session_id in manager.sessions
        
        # Should return existing session
        session2 = manager.get_or_create_session(session_id)
        assert session1 is session2
    
    def test_remove_session(self, manager):
        """Test removing sessions."""
        session_id = "test-session"
        
        # Create session
        manager.get_or_create_session(session_id)
        assert session_id in manager.sessions
        
        # Remove session
        manager.remove_session(session_id)
        assert session_id not in manager.sessions
    
    @pytest.mark.asyncio
    async def test_cleanup_sessions(self, manager):
        """Test session cleanup."""
        # Create expired session
        session = StreamingChatSession("expired-session")
        session.last_activity = datetime.fromtimestamp(0)  # Very old
        manager.sessions["expired-session"] = session
        
        # Create active session
        active_session = StreamingChatSession("active-session")
        manager.sessions["active-session"] = active_session
        
        # Run cleanup manually
        expired_sessions = [
            session_id for session_id, session in manager.sessions.items()
            if session.is_expired(timeout_seconds=3600)
        ]
        
        for session_id in expired_sessions:
            manager.remove_session(session_id)
        
        # Check results
        assert "expired-session" not in manager.sessions
        assert "active-session" in manager.sessions


class TestStreamingChatHandler:
    """Test StreamingChatHandler functionality."""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create mock Bedrock client."""
        client = AsyncMock()
        client.stream_response = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_memory_provider(self):
        """Create mock memory provider."""
        provider = AsyncMock()
        provider.store_conversation_turn = AsyncMock()
        return provider
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = AsyncMock()
        orchestrator.stream_execution = AsyncMock()
        return orchestrator
    
    @pytest.fixture
    def handler(self, mock_bedrock_client, mock_memory_provider, mock_orchestrator):
        """Create streaming chat handler."""
        return StreamingChatHandler(
            bedrock_client=mock_bedrock_client,
            memory_provider=mock_memory_provider,
            orchestrator=mock_orchestrator
        )
    
    @pytest.mark.asyncio
    async def test_stream_regular_chat(self, handler, mock_bedrock_client):
        """Test streaming regular chat response."""
        # Mock streaming response
        mock_bedrock_client.chat.return_value = [
            {"content": "Hello"},
            {"content": " there"},
            {"content": "!"}
        ].__aiter__()
        
        session_id = "test-session"
        messages = [{"role": "user", "content": "Hi"}]
        
        events = []
        async for event in handler._stream_regular_chat(session_id, messages):
            events.append(event)
        
        # Should have message delta events
        delta_events = [e for e in events if e.event_type == StreamEventType.MESSAGE_DELTA]
        assert len(delta_events) == 3
        
        # Check accumulated content
        accumulated_content = ""
        for event in delta_events:
            accumulated_content += event.data["delta"]
        
        assert accumulated_content == "Hello there!"
    
    @pytest.mark.asyncio
    async def test_analyze_for_tool_needs(self, handler):
        """Test tool needs analysis."""
        # Messages that should trigger tools
        tool_messages = [
            "Create a new file",
            "Search for functions",
            "Run the tests",
            "Git commit changes"
        ]
        
        for message in tool_messages:
            needs_tools = await handler._analyze_for_tool_needs(message)
            assert needs_tools is True
        
        # Messages that shouldn't trigger tools
        regular_messages = [
            "Hello there",
            "How are you?",
            "What's the weather like?"
        ]
        
        for message in regular_messages:
            needs_tools = await handler._analyze_for_tool_needs(message)
            assert needs_tools is False
    
    @pytest.mark.asyncio
    async def test_stream_chat_response_regular(self, handler, mock_bedrock_client):
        """Test streaming chat response without tools."""
        # Mock regular chat response
        mock_bedrock_client.chat.return_value = [
            {"content": "This is a regular response"}
        ].__aiter__()
        
        session_id = "test-session"
        message = "Hello"
        
        events = []
        async for event in handler.stream_chat_response(session_id, message):
            events.append(event)
        
        # Check event types
        event_types = [e.event_type for e in events]
        assert StreamEventType.CONNECTION_ESTABLISHED in event_types
        assert StreamEventType.MESSAGE_START in event_types
        assert StreamEventType.MESSAGE_DELTA in event_types
        assert StreamEventType.MESSAGE_STOP in event_types
    
    @pytest.mark.asyncio
    async def test_stream_chat_response_with_tools(self, handler, mock_orchestrator):
        """Test streaming chat response with tools."""
        # Mock tool execution
        mock_orchestrator.stream_execution.return_value = [
            {"type": "tool_call", "tool_name": "file_writer", "step": "Writing file"},
            {"type": "tool_result", "tool_name": "file_writer", "result": "File created"},
            {"type": "response", "content": "File created successfully"}
        ].__aiter__()
        
        session_id = "test-session"
        message = "Create a new file called test.py"
        
        events = []
        async for event in handler.stream_chat_response(session_id, message):
            events.append(event)
        
        # Check for tool-related events
        event_types = [e.event_type for e in events]
        assert StreamEventType.TOOL_CALL_START in event_types
        assert StreamEventType.TOOL_CALL_DELTA in event_types
        assert StreamEventType.TOOL_CALL_RESULT in event_types
        assert StreamEventType.TOOL_CALL_END in event_types
    
    @pytest.mark.asyncio
    async def test_error_handling(self, handler, mock_bedrock_client):
        """Test error handling in streaming."""
        # Mock error in streaming
        async def error_generator():
            yield {"content": "Start"}
            raise Exception("Test error")
        
        mock_bedrock_client.chat.return_value = error_generator()
        
        session_id = "test-session"
        message = "Hello"
        
        with pytest.raises(Exception):
            events = []
            async for event in handler.stream_chat_response(session_id, message):
                events.append(event)


@pytest.mark.asyncio
async def test_streaming_integration():
    """Integration test for streaming functionality."""
    # Create mock components
    bedrock_client = AsyncMock()
    bedrock_client.chat.return_value = [
        {"content": "Hello"},
        {"content": " world"},
        {"content": "!"}
    ].__aiter__()
    
    memory_provider = AsyncMock()
    
    # Create handler
    handler = StreamingChatHandler(
        bedrock_client=bedrock_client,
        memory_provider=memory_provider
    )
    
    # Test streaming
    session_id = str(uuid4())
    message = "Hello there"
    
    events = []
    async for event in handler.stream_chat_response(session_id, message):
        events.append(event)
    
    # Verify we got expected events
    assert len(events) >= 4  # At least connection, start, delta, stop
    
    # Verify event structure
    for event in events:
        assert isinstance(event, StreamEvent)
        assert event.session_id == session_id
        assert event.event_id is not None
        assert event.timestamp is not None
    
    # Verify memory storage was called
    memory_provider.store_conversation_turn.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])