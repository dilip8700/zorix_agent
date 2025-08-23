"""Tests for AWS Bedrock client."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from agent.llm.bedrock_client import BedrockClient
from agent.llm.exceptions import (
    BedrockError,
    BedrockRateLimitError,
    BedrockTimeoutError,
)
from agent.models.base import Message, MessageRole


class TestBedrockClient:
    """Test cases for BedrockClient."""
    
    @pytest.fixture
    def mock_bedrock_runtime(self):
        """Mock boto3 bedrock-runtime client."""
        with patch('boto3.client') as mock_client:
            mock_runtime = MagicMock()
            mock_client.return_value = mock_runtime
            yield mock_runtime
    
    @pytest.fixture
    def bedrock_client(self, mock_bedrock_runtime):
        """Create BedrockClient instance with mocked runtime."""
        return BedrockClient(
            region="us-east-1",
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            embed_model_id="amazon.titan-embed-text-v2:0"
        )
    
    def test_client_initialization(self, mock_bedrock_runtime):
        """Test BedrockClient initialization."""
        client = BedrockClient(
            region="us-west-2",
            model_id="test-model",
            embed_model_id="test-embed-model"
        )
        
        assert client.region == "us-west-2"
        assert client.model_id == "test-model"
        assert client.embed_model_id == "test-embed-model"
        assert client.bedrock_runtime is not None
    
    def test_client_initialization_no_credentials(self):
        """Test BedrockClient initialization with no credentials."""
        with patch('boto3.client', side_effect=NoCredentialsError()):
            with pytest.raises(BedrockError, match="AWS credentials not found"):
                BedrockClient()
    
    def test_convert_messages_to_bedrock(self, bedrock_client):
        """Test message conversion to Bedrock format."""
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are a helpful assistant"),
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!")
        ]
        
        bedrock_messages = bedrock_client._convert_messages_to_bedrock(messages)
        
        # System messages should be filtered out
        assert len(bedrock_messages) == 2
        
        # Check user message format
        user_msg = bedrock_messages[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][0]["text"] == "Hello"
        
        # Check assistant message format
        assistant_msg = bedrock_messages[1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"][0]["text"] == "Hi there!"
    
    def test_parse_text_response(self, bedrock_client):
        """Test parsing text-only response."""
        response_body = {
            "content": [
                {
                    "type": "text",
                    "text": "Hello! How can I help you today?"
                }
            ]
        }
        
        result = bedrock_client._parse_response(response_body)
        assert result == "Hello! How can I help you today?"
    
    def test_parse_tool_call_response(self, bedrock_client):
        """Test parsing response with tool calls."""
        response_body = {
            "content": [
                {
                    "type": "text",
                    "text": "I'll read the file for you."
                },
                {
                    "type": "tool_use",
                    "id": "call_123",
                    "name": "read_file",
                    "input": {"path": "test.py"}
                }
            ]
        }
        
        result = bedrock_client._parse_response(response_body)
        
        assert result["type"] == "tool_calls"
        assert result["text"] == "I'll read the file for you."
        assert len(result["tool_calls"]) == 1
        
        tool_call = result["tool_calls"][0]
        assert tool_call["id"] == "call_123"
        assert tool_call["name"] == "read_file"
        assert tool_call["arguments"] == {"path": "test.py"}
    
    @pytest.mark.asyncio
    async def test_invoke_model_success(self, bedrock_client, mock_bedrock_runtime):
        """Test successful model invocation."""
        # Mock successful response
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            "content": [
                {"type": "text", "text": "Hello!"}
            ]
        })
        
        mock_bedrock_runtime.invoke_model.return_value = mock_response
        
        request_body = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        result = await bedrock_client._invoke_model(request_body)
        assert result == "Hello!"
        
        # Verify the call was made correctly
        mock_bedrock_runtime.invoke_model.assert_called_once()
        call_args = mock_bedrock_runtime.invoke_model.call_args
        assert call_args[1]["modelId"] == bedrock_client.model_id
        assert call_args[1]["contentType"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_invoke_model_throttling_retry(self, bedrock_client, mock_bedrock_runtime):
        """Test retry logic for throttling errors."""
        # Mock throttling error then success
        throttling_error = ClientError(
            error_response={'Error': {'Code': 'ThrottlingException'}},
            operation_name='InvokeModel'
        )
        
        success_response = {
            'body': MagicMock()
        }
        success_response['body'].read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Success!"}]
        })
        
        mock_bedrock_runtime.invoke_model.side_effect = [
            throttling_error,
            success_response
        ]
        
        request_body = {"messages": [], "max_tokens": 100}
        
        result = await bedrock_client._invoke_model(request_body)
        assert result == "Success!"
        assert mock_bedrock_runtime.invoke_model.call_count == 2
    
    @pytest.mark.asyncio
    async def test_invoke_model_rate_limit_exceeded(self, bedrock_client, mock_bedrock_runtime):
        """Test rate limit exceeded after retries."""
        throttling_error = ClientError(
            error_response={'Error': {'Code': 'ThrottlingException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock_runtime.invoke_model.side_effect = throttling_error
        
        request_body = {"messages": [], "max_tokens": 100}
        
        with pytest.raises(BedrockRateLimitError):
            await bedrock_client._invoke_model(request_body)
        
        assert mock_bedrock_runtime.invoke_model.call_count == 3  # Max retries
    
    @pytest.mark.asyncio
    async def test_invoke_model_access_denied(self, bedrock_client, mock_bedrock_runtime):
        """Test access denied error."""
        access_denied_error = ClientError(
            error_response={'Error': {'Code': 'AccessDeniedException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock_runtime.invoke_model.side_effect = access_denied_error
        
        request_body = {"messages": [], "max_tokens": 100}
        
        with pytest.raises(BedrockError, match="Access denied"):
            await bedrock_client._invoke_model(request_body)
    
    @pytest.mark.asyncio
    async def test_chat_with_tools_text_response(self, bedrock_client, mock_bedrock_runtime):
        """Test chat with tools returning text response."""
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Hello! How can I help?"}]
        })
        
        mock_bedrock_runtime.invoke_model.return_value = mock_response
        
        messages = [Message(role=MessageRole.USER, content="Hi")]
        tool_schemas = []
        
        result = await bedrock_client.chat_with_tools(messages, tool_schemas)
        assert result == "Hello! How can I help?"
    
    @pytest.mark.asyncio
    async def test_chat_with_tools_tool_calls(self, bedrock_client, mock_bedrock_runtime):
        """Test chat with tools returning tool calls."""
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            "content": [
                {"type": "text", "text": "I'll read that file."},
                {
                    "type": "tool_use",
                    "id": "call_123",
                    "name": "read_file",
                    "input": {"path": "test.py"}
                }
            ]
        })
        
        mock_bedrock_runtime.invoke_model.return_value = mock_response
        
        messages = [Message(role=MessageRole.USER, content="Read test.py")]
        tool_schemas = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}}
                }
            }
        ]
        
        result = await bedrock_client.chat_with_tools(messages, tool_schemas)
        
        assert result["type"] == "tool_calls"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "read_file"
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_single(self, bedrock_client, mock_bedrock_runtime):
        """Test generating embeddings for single text."""
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3, 0.4]
        })
        
        mock_bedrock_runtime.invoke_model.return_value = mock_response
        
        texts = ["Hello world"]
        embeddings = await bedrock_client.generate_embeddings(texts)
        
        assert len(embeddings) == 1
        assert embeddings[0] == [0.1, 0.2, 0.3, 0.4]
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_empty(self, bedrock_client):
        """Test generating embeddings for empty list."""
        embeddings = await bedrock_client.generate_embeddings([])
        assert embeddings == []
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, bedrock_client, mock_bedrock_runtime):
        """Test successful health check."""
        mock_response = {
            'body': MagicMock()
        }
        mock_response['body'].read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Hi!"}]
        })
        
        mock_bedrock_runtime.invoke_model.return_value = mock_response
        
        health = await bedrock_client.health_check()
        
        assert health["status"] == "healthy"
        assert health["model_id"] == bedrock_client.model_id
        assert health["region"] == bedrock_client.region
        assert "response_time_ms" in health
        assert "test_response" in health
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, bedrock_client, mock_bedrock_runtime):
        """Test health check failure."""
        mock_bedrock_runtime.invoke_model.side_effect = Exception("Connection failed")
        
        health = await bedrock_client.health_check()
        
        assert health["status"] == "unhealthy"
        assert "Connection failed" in health["error"]
        assert health["model_id"] == bedrock_client.model_id
    
    def test_get_token_count_estimate(self, bedrock_client):
        """Test token count estimation."""
        # Test various text lengths
        assert bedrock_client.get_token_count_estimate("") == 1  # Minimum 1
        assert bedrock_client.get_token_count_estimate("Hi") == 1  # Short text
        assert bedrock_client.get_token_count_estimate("Hello world") == 2  # ~11 chars / 4
        assert bedrock_client.get_token_count_estimate("A" * 100) == 25  # 100 chars / 4
    
    def test_calculate_cost_estimate(self, bedrock_client):
        """Test cost calculation."""
        cost = bedrock_client.calculate_cost_estimate(
            input_tokens=1000,
            output_tokens=500
        )
        
        assert cost["input_tokens"] == 1000
        assert cost["output_tokens"] == 500
        assert cost["total_tokens"] == 1500
        
        # Check cost calculations (Claude 3.5 Sonnet pricing)
        expected_input_cost = (1000 / 1000) * 0.003  # $0.003
        expected_output_cost = (500 / 1000) * 0.015  # $0.0075
        expected_total = expected_input_cost + expected_output_cost  # $0.0105
        
        assert cost["input_cost_usd"] == expected_input_cost
        assert cost["output_cost_usd"] == expected_output_cost
        assert cost["total_cost_usd"] == expected_total
        assert cost["model_id"] == bedrock_client.model_id


class TestBedrockStreaming:
    """Test cases for Bedrock streaming functionality."""
    
    @pytest.fixture
    def mock_bedrock_runtime(self):
        """Mock boto3 bedrock-runtime client."""
        with patch('boto3.client') as mock_client:
            mock_runtime = MagicMock()
            mock_client.return_value = mock_runtime
            yield mock_runtime
    
    @pytest.fixture
    def bedrock_client(self, mock_bedrock_runtime):
        """Create BedrockClient instance with mocked runtime."""
        return BedrockClient()
    
    @pytest.mark.asyncio
    async def test_stream_response_text_only(self, bedrock_client, mock_bedrock_runtime):
        """Test streaming text-only response."""
        # Mock streaming response
        mock_stream_events = [
            {
                'chunk': {
                    'bytes': json.dumps({
                        'type': 'content_block_delta',
                        'delta': {'type': 'text_delta', 'text': 'Hello'}
                    }).encode()
                }
            },
            {
                'chunk': {
                    'bytes': json.dumps({
                        'type': 'content_block_delta',
                        'delta': {'type': 'text_delta', 'text': ' world!'}
                    }).encode()
                }
            },
            {
                'chunk': {
                    'bytes': json.dumps({
                        'type': 'message_stop'
                    }).encode()
                }
            }
        ]
        
        mock_response = {
            'body': iter(mock_stream_events)
        }
        
        mock_bedrock_runtime.invoke_model_with_response_stream.return_value = mock_response
        
        request_body = {"messages": [], "max_tokens": 100}
        
        events = []
        async for event in bedrock_client._stream_response(request_body):
            events.append(event)
        
        # Should have text deltas and final completion
        assert len(events) == 3
        
        # Check first text delta
        assert events[0]['type'] == 'text_delta'
        assert events[0]['text'] == 'Hello'
        assert events[0]['accumulated_text'] == 'Hello'
        
        # Check second text delta
        assert events[1]['type'] == 'text_delta'
        assert events[1]['text'] == ' world!'
        assert events[1]['accumulated_text'] == 'Hello world!'
        
        # Check completion
        assert events[2]['type'] == 'message_complete'
        assert events[2]['text'] == 'Hello world!'
    
    @pytest.mark.asyncio
    async def test_stream_response_with_tools(self, bedrock_client, mock_bedrock_runtime):
        """Test streaming response with tool calls."""
        mock_stream_events = [
            {
                'chunk': {
                    'bytes': json.dumps({
                        'type': 'content_block_start',
                        'content_block': {
                            'type': 'tool_use',
                            'id': 'call_123',
                            'name': 'read_file'
                        }
                    }).encode()
                }
            },
            {
                'chunk': {
                    'bytes': json.dumps({
                        'type': 'message_stop'
                    }).encode()
                }
            }
        ]
        
        mock_response = {
            'body': iter(mock_stream_events)
        }
        
        mock_bedrock_runtime.invoke_model_with_response_stream.return_value = mock_response
        
        request_body = {"messages": [], "max_tokens": 100}
        
        events = []
        async for event in bedrock_client._stream_response(request_body):
            events.append(event)
        
        assert len(events) == 2
        
        # Check tool use start
        assert events[0]['type'] == 'tool_use_start'
        assert events[0]['tool_call']['id'] == 'call_123'
        assert events[0]['tool_call']['name'] == 'read_file'
        
        # Check completion with tool calls
        assert events[1]['type'] == 'message_complete'
        assert len(events[1]['tool_calls']) == 1