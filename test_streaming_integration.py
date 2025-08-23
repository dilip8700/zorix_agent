#!/usr/bin/env python3
"""
Integration tests for streaming chat functionality.

This script tests the streaming chat endpoints with real components.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent.web.streaming import (
    StreamEvent,
    StreamEventType,
    StreamingChatHandler,
    StreamingManager,
    streaming_manager
)


async def test_stream_event_sse_format():
    """Test Server-Sent Events formatting."""
    print("Testing SSE format...")
    
    event = StreamEvent(
        event_type=StreamEventType.MESSAGE_DELTA,
        event_id="test-123",
        timestamp=datetime.now(),
        session_id="session-123",
        data={"delta": "Hello", "accumulated": "Hello world"}
    )
    
    sse_output = event.to_sse()
    print(f"SSE Output:\n{sse_output}")
    
    # Verify format
    lines = sse_output.strip().split('\n')
    assert lines[0] == "event: message_delta"
    assert lines[1] == "id: test-123"
    assert lines[2].startswith("data: ")
    
    # Parse data
    data_json = lines[2][6:]  # Remove "data: " prefix
    data = json.loads(data_json)
    assert data["session_id"] == "session-123"
    assert data["delta"] == "Hello"
    
    print("✓ SSE format test passed")


async def test_streaming_manager():
    """Test streaming manager functionality."""
    print("Testing streaming manager...")
    
    manager = StreamingManager()
    
    # Test session creation
    session_id = "test-session-123"
    session = manager.get_or_create_session(session_id)
    
    assert session.session_id == session_id
    assert session.is_active is True
    assert session.client_count == 0
    
    # Test client management
    session.add_client()
    assert session.client_count == 1
    
    session.add_client()
    assert session.client_count == 2
    
    session.remove_client()
    assert session.client_count == 1
    assert session.is_active is True
    
    session.remove_client()
    assert session.client_count == 0
    assert session.is_active is False
    
    print("✓ Streaming manager test passed")


async def test_streaming_chat_handler():
    """Test streaming chat handler."""
    print("Testing streaming chat handler...")
    
    # Create mock Bedrock client
    bedrock_client = AsyncMock()
    
    # Mock streaming response
    async def mock_chat_stream(*args, **kwargs):
        responses = [
            {"content": "Hello"},
            {"content": " there"},
            {"content": "! How"},
            {"content": " can I"},
            {"content": " help you?"}
        ]
        for response in responses:
            yield response
            await asyncio.sleep(0.01)  # Simulate streaming delay
    
    bedrock_client.chat.return_value = mock_chat_stream()
    
    # Create handler
    handler = StreamingChatHandler(
        bedrock_client=bedrock_client,
        memory_provider=None,
        orchestrator=None
    )
    
    # Test streaming
    session_id = "test-session"
    message = "Hello"
    
    events = []
    full_response = ""
    
    async for event in handler.stream_chat_response(session_id, message):
        events.append(event)
        
        if event.event_type == StreamEventType.MESSAGE_DELTA:
            delta = event.data.get("delta", "")
            full_response += delta
            print(f"Received delta: '{delta}' (accumulated: '{full_response}')")
    
    # Verify events
    event_types = [e.event_type for e in events]
    print(f"Event types received: {event_types}")
    
    assert StreamEventType.CONNECTION_ESTABLISHED in event_types
    assert StreamEventType.MESSAGE_START in event_types
    assert StreamEventType.MESSAGE_DELTA in event_types
    assert StreamEventType.MESSAGE_STOP in event_types
    
    # Verify full response
    expected_response = "Hello there! How can I help you?"
    assert full_response == expected_response
    
    print(f"✓ Full response: '{full_response}'")
    print("✓ Streaming chat handler test passed")


async def test_tool_calling_stream():
    """Test streaming with tool calling."""
    print("Testing tool calling stream...")
    
    # Create mock components
    bedrock_client = AsyncMock()
    orchestrator = AsyncMock()
    
    # Mock tool execution stream
    async def mock_tool_stream(*args, **kwargs):
        tool_events = [
            {"type": "tool_call", "tool_name": "file_writer", "step": "Analyzing request"},
            {"type": "tool_call", "tool_name": "file_writer", "step": "Creating file"},
            {"type": "tool_result", "tool_name": "file_writer", "result": "File created: test.py"},
            {"type": "response", "content": "I've successfully created the file test.py for you."}
        ]
        
        for event in tool_events:
            yield event
            await asyncio.sleep(0.02)
    
    orchestrator.stream_execution.return_value = mock_tool_stream()
    
    # Create handler
    handler = StreamingChatHandler(
        bedrock_client=bedrock_client,
        memory_provider=None,
        orchestrator=orchestrator
    )
    
    # Test tool calling message
    session_id = "test-tool-session"
    message = "Create a new file called test.py"
    
    events = []
    tool_calls = []
    
    async for event in handler.stream_chat_response(session_id, message):
        events.append(event)
        
        if event.event_type == StreamEventType.TOOL_CALL_DELTA:
            tool_name = event.data.get("tool_name")
            step = event.data.get("step")
            print(f"Tool call: {tool_name} - {step}")
            tool_calls.append((tool_name, step))
        
        elif event.event_type == StreamEventType.TOOL_CALL_RESULT:
            tool_name = event.data.get("tool_name")
            result = event.data.get("result")
            print(f"Tool result: {tool_name} - {result}")
    
    # Verify tool events
    event_types = [e.event_type for e in events]
    print(f"Tool event types: {event_types}")
    
    assert StreamEventType.TOOL_CALL_START in event_types
    assert StreamEventType.TOOL_CALL_DELTA in event_types
    assert StreamEventType.TOOL_CALL_RESULT in event_types
    assert StreamEventType.TOOL_CALL_END in event_types
    
    # Verify tool calls were made
    assert len(tool_calls) >= 2
    assert all("file_writer" in call[0] for call in tool_calls)
    
    print("✓ Tool calling stream test passed")


async def test_error_handling():
    """Test error handling in streaming."""
    print("Testing error handling...")
    
    # Create mock client that raises error
    bedrock_client = AsyncMock()
    
    async def error_stream(*args, **kwargs):
        yield {"content": "Starting response..."}
        await asyncio.sleep(0.01)
        raise Exception("Simulated streaming error")
    
    bedrock_client.chat.return_value = error_stream()
    
    # Create handler
    handler = StreamingChatHandler(
        bedrock_client=bedrock_client,
        memory_provider=None,
        orchestrator=None
    )
    
    # Test error handling
    session_id = "error-test-session"
    message = "This will cause an error"
    
    events = []
    error_caught = False
    
    try:
        async for event in handler.stream_chat_response(session_id, message):
            events.append(event)
            
            if event.event_type == StreamEventType.ERROR:
                error_caught = True
                error_msg = event.data.get("error")
                print(f"Error event received: {error_msg}")
    
    except Exception as e:
        print(f"Exception caught: {e}")
        error_caught = True
    
    assert error_caught, "Error should have been caught"
    print("✓ Error handling test passed")


async def test_connection_management():
    """Test connection management."""
    print("Testing connection management...")
    
    manager = StreamingManager()
    
    # Create multiple sessions
    sessions = []
    for i in range(3):
        session_id = f"session-{i}"
        session = manager.get_or_create_session(session_id)
        sessions.append(session)
        
        # Add multiple clients to each session
        for j in range(2):
            session.add_client()
    
    # Verify sessions
    assert len(manager.sessions) == 3
    for session in sessions:
        assert session.client_count == 2
        assert session.is_active is True
    
    # Remove clients
    for session in sessions:
        session.remove_client()  # Still has 1 client
        assert session.is_active is True
        
        session.remove_client()  # No clients left
        assert session.is_active is False
    
    print("✓ Connection management test passed")


async def main():
    """Run all streaming integration tests."""
    print("Starting streaming integration tests...\n")
    
    try:
        await test_stream_event_sse_format()
        print()
        
        await test_streaming_manager()
        print()
        
        await test_streaming_chat_handler()
        print()
        
        await test_tool_calling_stream()
        print()
        
        await test_error_handling()
        print()
        
        await test_connection_management()
        print()
        
        print("🎉 All streaming integration tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    from datetime import datetime
    
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)