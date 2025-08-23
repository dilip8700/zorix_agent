"""Chat API routes."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent.web.api import get_app_state
from agent.web.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationInfo,
)
from agent.web.streaming import (
    StreamingChatHandler,
    StreamingManager,
    streaming_manager,
    StreamEvent,
    StreamEventType
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Active chat sessions
chat_sessions: Dict[str, Dict] = {}


@router.post("/message", response_model=ChatResponse)
async def send_message(chat_request: ChatRequest):
    """Send a message to the agent."""
    app_state = get_app_state()
    bedrock_client = app_state.get("bedrock_client")
    memory_provider = app_state.get("memory_provider")
    
    if not bedrock_client or not memory_provider:
        raise HTTPException(status_code=500, detail="Chat components not initialized")
    
    # Get or create session
    session_id = chat_request.session_id or str(uuid4())
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "id": session_id,
            "messages": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    session = chat_sessions[session_id]
    
    try:
        # Add user message to session
        user_message = ChatMessage(
            role="user",
            content=chat_request.message,
            timestamp=datetime.now()
        )
        session["messages"].append(user_message)
        
        # Get conversation context
        conversation_context = []
        for msg in session["messages"][-10:]:  # Last 10 messages
            conversation_context.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Generate response using Bedrock
        response = await bedrock_client.generate_response(
            messages=conversation_context,
            context=chat_request.context or {}
        )
        
        # Create assistant message
        assistant_message = ChatMessage(
            role="assistant",
            content=response["content"],
            timestamp=datetime.now(),
            metadata=response.get("metadata")
        )
        
        # Add to session
        session["messages"].append(assistant_message)
        session["updated_at"] = datetime.now()
        
        # Store in memory if available
        try:
            await memory_provider.store_conversation_turn(
                session_id=session_id,
                user_message=chat_request.message,
                assistant_response=response["content"],
                context=chat_request.context
            )
        except Exception as e:
            logger.warning(f"Failed to store conversation: {e}")
        
        return ChatResponse(
            message=response["content"],
            session_id=session_id,
            message_id=str(uuid4()),
            timestamp=datetime.now(),
            metadata=response.get("metadata")
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/stream")
async def stream_message(chat_request: ChatRequest, request: Request):
    """Stream a chat response with Server-Sent Events."""
    app_state = get_app_state()
    bedrock_client = app_state.get("bedrock_client")
    memory_provider = app_state.get("memory_provider")
    orchestrator = app_state.get("orchestrator")
    
    if not bedrock_client:
        raise HTTPException(status_code=500, detail="Chat components not initialized")
    
    # Get or create session
    session_id = chat_request.session_id or str(uuid4())
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "id": session_id,
            "messages": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    session = chat_sessions[session_id]
    
    # Create streaming handler
    streaming_handler = StreamingChatHandler(
        bedrock_client=bedrock_client,
        memory_provider=memory_provider,
        orchestrator=orchestrator
    )
    
    # Get streaming session
    streaming_session = streaming_manager.get_or_create_session(session_id)
    streaming_session.add_client()
    
    async def stream_generator():
        """Generate Server-Sent Events for chat response."""
        try:
            # Add user message to session
            user_message = ChatMessage(
                role="user",
                content=chat_request.message,
                timestamp=datetime.now()
            )
            session["messages"].append(user_message)
            
            # Get conversation context
            conversation_history = []
            for msg in session["messages"][-10:]:  # Last 10 messages
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Send heartbeat to establish connection
            heartbeat_event = StreamEvent(
                event_type=StreamEventType.HEARTBEAT,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"status": "connected"}
            )
            yield heartbeat_event.to_sse()
            
            # Stream the chat response
            full_response = ""
            async for event in streaming_handler.stream_chat_response(
                session_id=session_id,
                message=chat_request.message,
                context=chat_request.context,
                conversation_history=conversation_history[:-1]  # Exclude the just-added user message
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from session {session_id}")
                    break
                
                # Accumulate response content
                if event.event_type == StreamEventType.MESSAGE_DELTA:
                    full_response += event.data.get("delta", "")
                
                yield event.to_sse()
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
            
            # Add complete response to session
            if full_response:
                assistant_message = ChatMessage(
                    role="assistant",
                    content=full_response,
                    timestamp=datetime.now()
                )
                session["messages"].append(assistant_message)
                session["updated_at"] = datetime.now()
            
            # Send connection closed event
            close_event = StreamEvent(
                event_type=StreamEventType.CONNECTION_CLOSED,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"message": "Stream completed"}
            )
            yield close_event.to_sse()
            
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            error_event = StreamEvent(
                event_type=StreamEventType.ERROR,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={"error": str(e), "error_type": type(e).__name__}
            )
            yield error_event.to_sse()
        finally:
            # Remove client from streaming session
            streaming_session.remove_client()
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/sessions", response_model=List[ConversationInfo])
async def list_sessions(limit: int = 20):
    """List chat sessions."""
    sessions = []
    
    for session_id, session_data in list(chat_sessions.items())[-limit:]:
        sessions.append(ConversationInfo(
            id=session_id,
            title=f"Chat {session_id[:8]}",
            message_count=len(session_data["messages"]),
            created_at=session_data["created_at"],
            updated_at=session_data["updated_at"],
            is_current=False  # Could implement current session logic
        ))
    
    return sessions


@router.get("/sessions/{session_id}", response_model=List[ChatMessage])
async def get_session_messages(session_id: str, limit: int = 50):
    """Get messages from a chat session."""
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = chat_sessions[session_id]
    messages = session["messages"][-limit:]
    
    return messages


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del chat_sessions[session_id]
    
    return {"message": f"Session {session_id} deleted"}


@router.post("/sessions/{session_id}/clear")
async def clear_session(session_id: str):
    """Clear messages from a chat session."""
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    chat_sessions[session_id]["messages"] = []
    chat_sessions[session_id]["updated_at"] = datetime.now()
    
    return {"message": f"Session {session_id} cleared"}


@router.get("/sessions/{session_id}/export")
async def export_session(session_id: str):
    """Export chat session as JSON."""
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = chat_sessions[session_id]
    
    export_data = {
        "session_id": session_id,
        "created_at": session["created_at"].isoformat(),
        "updated_at": session["updated_at"].isoformat(),
        "message_count": len(session["messages"]),
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "metadata": msg.metadata
            }
            for msg in session["messages"]
        ]
    }
    
    return export_data


@router.post("/stream/enhanced")
async def stream_enhanced_chat(chat_request: ChatRequest, request: Request):
    """Enhanced streaming chat with tool calling and progress updates."""
    app_state = get_app_state()
    bedrock_client = app_state.get("bedrock_client")
    memory_provider = app_state.get("memory_provider")
    orchestrator = app_state.get("orchestrator")
    
    if not bedrock_client:
        raise HTTPException(status_code=500, detail="Chat components not initialized")
    
    # Get or create session
    session_id = chat_request.session_id or str(uuid4())
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "id": session_id,
            "messages": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    session = chat_sessions[session_id]
    
    # Create streaming handler with orchestrator for tool calling
    streaming_handler = StreamingChatHandler(
        bedrock_client=bedrock_client,
        memory_provider=memory_provider,
        orchestrator=orchestrator
    )
    
    # Get streaming session
    streaming_session = streaming_manager.get_or_create_session(session_id)
    streaming_session.add_client()
    
    async def enhanced_stream_generator():
        """Generate enhanced streaming response with tool calling."""
        try:
            # Add user message to session
            user_message = ChatMessage(
                role="user",
                content=chat_request.message,
                timestamp=datetime.now()
            )
            session["messages"].append(user_message)
            
            # Get conversation context
            conversation_history = []
            for msg in session["messages"][-10:]:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Send connection established event
            connection_event = StreamEvent(
                event_type=StreamEventType.CONNECTION_ESTABLISHED,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={
                    "message": "Enhanced streaming connection established",
                    "capabilities": ["tool_calling", "progress_updates", "real_time_feedback"]
                }
            )
            yield connection_event.to_sse()
            
            # Stream the enhanced chat response
            full_response = ""
            tool_calls_made = []
            
            async for event in streaming_handler.stream_chat_response(
                session_id=session_id,
                message=chat_request.message,
                context=chat_request.context,
                conversation_history=conversation_history[:-1]
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from enhanced session {session_id}")
                    break
                
                # Track tool calls
                if event.event_type in [StreamEventType.TOOL_CALL_START, StreamEventType.TOOL_CALL_DELTA]:
                    tool_name = event.data.get("tool_name")
                    if tool_name and tool_name not in tool_calls_made:
                        tool_calls_made.append(tool_name)
                
                # Accumulate response content
                if event.event_type == StreamEventType.MESSAGE_DELTA:
                    full_response += event.data.get("delta", "")
                
                yield event.to_sse()
                
                # Smaller delay for enhanced streaming
                await asyncio.sleep(0.005)
            
            # Add complete response to session with metadata
            if full_response or tool_calls_made:
                assistant_message = ChatMessage(
                    role="assistant",
                    content=full_response or "Task completed successfully.",
                    timestamp=datetime.now(),
                    metadata={
                        "tool_calls_made": tool_calls_made,
                        "enhanced_streaming": True,
                        "session_id": session_id
                    }
                )
                session["messages"].append(assistant_message)
                session["updated_at"] = datetime.now()
            
            # Send final summary event
            summary_event = StreamEvent(
                event_type=StreamEventType.MESSAGE_STOP,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={
                    "message": "Enhanced stream completed",
                    "tool_calls_made": tool_calls_made,
                    "response_length": len(full_response),
                    "duration_ms": (datetime.now() - user_message.timestamp).total_seconds() * 1000
                }
            )
            yield summary_event.to_sse()
            
        except asyncio.CancelledError:
            logger.info(f"Enhanced stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Enhanced streaming error: {e}")
            error_event = StreamEvent(
                event_type=StreamEventType.ERROR,
                event_id=str(uuid4()),
                timestamp=datetime.now(),
                session_id=session_id,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "enhanced_streaming": True
                }
            )
            yield error_event.to_sse()
        finally:
            # Remove client from streaming session
            streaming_session.remove_client()
    
    return StreamingResponse(
        enhanced_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/stream/status/{session_id}")
async def get_streaming_status(session_id: str):
    """Get streaming session status."""
    streaming_session = streaming_manager.sessions.get(session_id)
    
    if not streaming_session:
        raise HTTPException(status_code=404, detail="Streaming session not found")
    
    return {
        "session_id": session_id,
        "is_active": streaming_session.is_active,
        "client_count": streaming_session.client_count,
        "created_at": streaming_session.created_at,
        "last_activity": streaming_session.last_activity,
        "message_buffer_size": len(streaming_session.message_buffer)
    }


@router.post("/stream/heartbeat/{session_id}")
async def send_heartbeat(session_id: str):
    """Send heartbeat to keep streaming session alive."""
    streaming_session = streaming_manager.sessions.get(session_id)
    
    if not streaming_session:
        raise HTTPException(status_code=404, detail="Streaming session not found")
    
    streaming_session.last_activity = datetime.now()
    
    return {
        "session_id": session_id,
        "heartbeat_sent": True,
        "timestamp": datetime.now()
    }