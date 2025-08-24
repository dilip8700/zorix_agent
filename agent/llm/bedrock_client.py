"""AWS Bedrock client for LLM integration in Zorix Agent."""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from agent.config import get_settings
from agent.models.base import Message, ToolCall, ToolResult
from agent.llm.exceptions import BedrockError, BedrockRateLimitError, BedrockTimeoutError

logger = logging.getLogger(__name__)


class BedrockClient:
    """AWS Bedrock client for LLM interactions with streaming and tool calling support."""
    
    def __init__(
        self,
        region: Optional[str] = None,
        model_id: Optional[str] = None,
        embed_model_id: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 120
    ):
        """Initialize Bedrock client.
        
        Args:
            region: AWS region for Bedrock
            model_id: Model ID for text generation
            embed_model_id: Model ID for embeddings
            max_retries: Maximum number of retries for failed requests
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        
        self.region = region or settings.bedrock_region
        self.model_id = model_id or settings.bedrock_model_id
        self.embed_model_id = embed_model_id or settings.bedrock_embed_model_id
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Configure boto3 with retries and timeout
        config = Config(
            region_name=self.region,
            retries={
                'max_attempts': max_retries,
                'mode': 'adaptive'
            },
            read_timeout=timeout,
            connect_timeout=30
        )
        
        try:
            self.bedrock_runtime = boto3.client('bedrock-runtime', config=config)
            logger.info(f"Initialized Bedrock client for region {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise BedrockError(f"Failed to initialize Bedrock client: {e}") from e
    
    async def chat_with_tools(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """Chat with the model using tool calling.
        
        Args:
            messages: List of conversation messages
            tools: Available tools for function calling
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response
            
        Returns:
            Response dict or async iterator for streaming
        """
        settings = get_settings()
        
        # Prepare request body
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": self._format_messages(messages),
            "max_tokens": max_tokens or settings.max_tokens,
            "temperature": temperature or settings.temperature,
        }
        
        # Add tools if provided
        if tools:
            request_body["tools"] = tools
        
        # Add system message if needed
        system_message = self._extract_system_message(messages)
        if system_message:
            request_body["system"] = system_message
        
        try:
            if stream:
                return self._stream_chat(request_body)
            else:
                return await self._invoke_chat(request_body)
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'ThrottlingException':
                raise BedrockRateLimitError(f"Rate limit exceeded: {error_message}") from e
            elif error_code in ['ValidationException', 'AccessDeniedException']:
                raise BedrockError(f"Bedrock API error ({error_code}): {error_message}") from e
            else:
                raise BedrockError(f"Bedrock service error ({error_code}): {error_message}") from e
        
        except BotoCoreError as e:
            raise BedrockError(f"Boto3 error: {e}") from e
        
        except Exception as e:
            logger.error(f"Unexpected error in chat_with_tools: {e}")
            raise BedrockError(f"Unexpected error: {e}") from e
    
    async def _invoke_chat(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke chat model without streaming."""
        start_time = time.time()
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.bedrock_runtime.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType='application/json',
                    accept='application/json'
                )
            )
            
            duration = time.time() - start_time
            logger.debug(f"Bedrock invoke_model completed in {duration:.2f}s")
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Log token usage
            usage = response_body.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            logger.info(f"Token usage - Input: {input_tokens}, Output: {output_tokens}")
            
            return response_body
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Bedrock invoke_model failed after {duration:.2f}s: {e}")
            raise
    
    async def _stream_chat(self, request_body: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream chat model response."""
        start_time = time.time()
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.bedrock_runtime.invoke_model_with_response_stream(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType='application/json',
                    accept='application/json'
                )
            )
            
            logger.debug("Started streaming response from Bedrock")
            
            # Process streaming response
            stream = response.get('body')
            if stream:
                async for chunk in self._process_stream(stream):
                    yield chunk
            
            duration = time.time() - start_time
            logger.debug(f"Bedrock streaming completed in {duration:.2f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Bedrock streaming failed after {duration:.2f}s: {e}")
            raise
    
    async def _process_stream(self, stream) -> AsyncIterator[Dict[str, Any]]:
        """Process streaming response from Bedrock."""
        try:
            for event in stream:
                chunk = event.get('chunk')
                if chunk:
                    chunk_data = json.loads(chunk.get('bytes').decode())
                    yield chunk_data
                    
                    # Small delay to prevent overwhelming the consumer
                    await asyncio.sleep(0.001)
        
        except Exception as e:
            logger.error(f"Error processing stream: {e}")
            raise BedrockError(f"Stream processing error: {e}") from e
    
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """Stream response content as text chunks.
        
        This is a convenience method for streaming just the text content.
        """
        async for chunk in self.chat(
            messages=messages,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        ):
            # Extract text content from chunk
            content = ""
            
            if isinstance(chunk, dict):
                # Handle different response formats
                if "content" in chunk:
                    content = chunk["content"]
                elif "delta" in chunk and "text" in chunk["delta"]:
                    content = chunk["delta"]["text"]
                elif "text" in chunk:
                    content = chunk["text"]
                elif "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
            
            if content:
                yield content
    
    async def generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 10
    ) -> List[List[float]]:
        """Generate embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches to avoid rate limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self._generate_batch_embeddings(batch)
            embeddings.extend(batch_embeddings)
            
            # Small delay between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        logger.info(f"Generated embeddings for {len(texts)} texts")
        return embeddings
    
    async def _generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        start_time = time.time()
        
        try:
            # Prepare request for each text
            embeddings = []
            
            for text in texts:
                request_body = {
                    "inputText": text
                }
                
                # Run in thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.bedrock_runtime.invoke_model(
                        modelId=self.embed_model_id,
                        body=json.dumps(request_body),
                        contentType='application/json',
                        accept='application/json'
                    )
                )
                
                response_body = json.loads(response['body'].read())
                embedding = response_body.get('embedding', [])
                embeddings.append(embedding)
            
            duration = time.time() - start_time
            logger.debug(f"Generated {len(embeddings)} embeddings in {duration:.2f}s")
            
            return embeddings
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Embedding generation failed after {duration:.2f}s: {e}")
            raise BedrockError(f"Embedding generation failed: {e}") from e
    
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Format messages for Bedrock API using Anthropic format."""
        formatted = []
        
        for message in messages:
            # Skip system messages (handled separately)
            if message.role == "system":
                continue
            
            # Format message using Anthropic format
            formatted_message = {
                "role": message.role,
                "content": [
                    {
                        "type": "text",
                        "text": message.content
                    }
                ]
            }
            
            formatted.append(formatted_message)
        
        return formatted
    
    def _extract_system_message(self, messages: List[Message]) -> Optional[str]:
        """Extract system message from message list."""
        for message in messages:
            if message.role == "system":
                return message.content
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Bedrock service health."""
        try:
            # Simple test request
            test_messages = [
                Message(role="user", content="Hello")
            ]
            
            start_time = time.time()
            response = await self.chat_with_tools(
                messages=test_messages,
                max_tokens=10,
                temperature=0.1
            )
            duration = time.time() - start_time
            
            return {
                "status": "healthy",
                "model_id": self.model_id,
                "embed_model_id": self.embed_model_id,
                "region": self.region,
                "response_time_ms": int(duration * 1000),
                "test_successful": True
            }
            
        except Exception as e:
            logger.error(f"Bedrock health check failed: {e}")
            return {
                "status": "unhealthy",
                "model_id": self.model_id,
                "embed_model_id": self.embed_model_id,
                "region": self.region,
                "error": str(e),
                "test_successful": False
            }
    
    def parse_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """Parse tool calls from Bedrock response.
        
        Args:
            response: Bedrock API response
            
        Returns:
            List of parsed tool calls
        """
        tool_calls = []
        
        content = response.get('content', [])
        for item in content:
            if item.get('type') == 'tool_use':
                tool_call = ToolCall(
                    id=item.get('id', ''),
                    name=item.get('name', ''),
                    arguments=item.get('input', {})
                )
                tool_calls.append(tool_call)
        
        return tool_calls
    
    def format_tool_result(self, tool_result: ToolResult) -> Dict[str, Any]:
        """Format tool result for Bedrock API.
        
        Args:
            tool_result: Tool execution result
            
        Returns:
            Formatted tool result for API
        """
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_result.tool_call_id,
                    "content": json.dumps(tool_result.result) if tool_result.success else tool_result.error
                }
            ]
        }
    
    async def close(self):
        """Clean up resources."""
        # Bedrock client doesn't need explicit cleanup
        logger.info("Bedrock client closed")


class BedrockClientPool:
    """Pool of Bedrock clients for load balancing and failover."""
    
    def __init__(self, pool_size: int = 3):
        """Initialize client pool.
        
        Args:
            pool_size: Number of clients in the pool
        """
        self.pool_size = pool_size
        self.clients = []
        self.current_index = 0
        
        # Initialize clients
        for i in range(pool_size):
            client = BedrockClient()
            self.clients.append(client)
        
        logger.info(f"Initialized Bedrock client pool with {pool_size} clients")
    
    def get_client(self) -> BedrockClient:
        """Get next available client from pool."""
        client = self.clients[self.current_index]
        self.current_index = (self.current_index + 1) % self.pool_size
        return client
    
    async def health_check_all(self) -> Dict[str, Any]:
        """Check health of all clients in pool."""
        results = []
        
        for i, client in enumerate(self.clients):
            health = await client.health_check()
            health['client_id'] = i
            results.append(health)
        
        healthy_count = sum(1 for r in results if r['status'] == 'healthy')
        
        return {
            "pool_size": self.pool_size,
            "healthy_clients": healthy_count,
            "unhealthy_clients": self.pool_size - healthy_count,
            "clients": results
        }
    
    async def close_all(self):
        """Close all clients in pool."""
        for client in self.clients:
            await client.close()
        logger.info("Closed all clients in pool")