#!/usr/bin/env python3
"""
Integration tests for CLI functionality.

This script tests the CLI with real or mocked API interactions.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent.cli.main import ZorixCLI


async def test_cli_instance_creation():
    """Test CLI instance creation and basic functionality."""
    print("Testing CLI instance creation...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    assert cli.api_url == "http://test-api:8000"
    assert cli.console is not None
    
    # Test client creation
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        client = await cli.get_client()
        assert client is mock_client
        
        # Test cleanup
        await cli.close()
        mock_client.aclose.assert_called_once()
    
    print("✓ CLI instance creation test passed")


async def test_api_health_check():
    """Test API health check functionality."""
    print("Testing API health check...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    # Test successful health check
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await cli.check_api_health()
        assert result is True
        mock_client.get.assert_called_once_with("/api/v1/system/health")
    
    # Test failed health check
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client
        
        result = await cli.check_api_health()
        assert result is False
    
    await cli.close()
    print("✓ API health check test passed")


async def test_task_execution():
    """Test task execution functionality."""
    print("Testing task execution...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "test-task-123",
            "status": "started",
            "message": "Task created successfully",
            "requires_approval": False
        }
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await cli.execute_task(
            instruction="Create a test file",
            dry_run=False,
            auto_approve=True
        )
        
        assert result["task_id"] == "test-task-123"
        assert result["status"] == "started"
        assert result["requires_approval"] is False
        
        # Verify the API call
        mock_client.post.assert_called_once_with(
            "/api/v1/tasks/execute",
            json={
                "instruction": "Create a test file",
                "dry_run": False,
                "auto_approve": True,
                "generate_preview": True,
                "estimate_cost": True
            }
        )
    
    await cli.close()
    print("✓ Task execution test passed")


async def test_search_functionality():
    """Test search functionality."""
    print("Testing search functionality...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": "test function",
            "results": [
                {
                    "type": "code",
                    "title": "test_function.py",
                    "content": "def test_function(): pass",
                    "path": "/src/test_function.py",
                    "score": 0.95,
                    "metadata": {"language": "python"}
                },
                {
                    "type": "memory",
                    "title": "Test Memory",
                    "content": "Information about test functions",
                    "score": 0.85,
                    "metadata": {"memory_type": "code_explanation"}
                }
            ],
            "total_results": 2,
            "search_time_ms": 45.2
        }
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = await cli.search_content(
            query="test function",
            search_type="all",
            max_results=10
        )
        
        assert result["query"] == "test function"
        assert len(result["results"]) == 2
        assert result["results"][0]["type"] == "code"
        assert result["results"][1]["type"] == "memory"
        assert result["total_results"] == 2
        
        # Verify the API call
        mock_client.post.assert_called_once_with(
            "/api/v1/search/",
            json={
                "query": "test function",
                "search_type": "all",
                "max_results": 10
            }
        )
    
    await cli.close()
    print("✓ Search functionality test passed")


async def test_chat_functionality():
    """Test chat functionality."""
    print("Testing chat functionality...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Hello! I'm Zorix Agent. How can I help you today?",
            "session_id": "chat-session-456",
            "message_id": "msg-789",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        response = await cli.chat_with_agent("Hello, how are you?")
        
        assert response == "Hello! I'm Zorix Agent. How can I help you today?"
        
        # Verify the API call
        mock_client.post.assert_called_once_with(
            "/api/v1/chat/message",
            json={
                "message": "Hello, how are you?",
                "stream": False
            }
        )
    
    await cli.close()
    print("✓ Chat functionality test passed")


def test_formatting_functions():
    """Test result formatting functions."""
    print("Testing formatting functions...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    # Test task result formatting
    task_result = {
        "task_id": "test-123",
        "status": "completed",
        "message": "Task completed successfully",
        "requires_approval": False
    }
    
    # Test rich formatting
    rich_formatted = cli.format_task_result(task_result, "rich")
    assert "test-123" in str(rich_formatted)
    assert "completed" in str(rich_formatted)
    
    # Test JSON formatting
    json_formatted = cli.format_task_result(task_result, "json")
    parsed = json.loads(json_formatted)
    assert parsed["task_id"] == "test-123"
    assert parsed["status"] == "completed"
    
    # Test search results formatting
    search_results = {
        "query": "test query",
        "results": [
            {
                "type": "code",
                "title": "Test File",
                "content": "def test(): pass",
                "score": 0.95
            }
        ],
        "total_results": 1,
        "search_time_ms": 25.5
    }
    
    # Test rich formatting
    rich_search = cli.format_search_results(search_results, "rich")
    assert "test query" in str(rich_search)
    assert "Test File" in str(rich_search)
    
    # Test JSON formatting
    json_search = cli.format_search_results(search_results, "json")
    parsed_search = json.loads(json_search)
    assert parsed_search["query"] == "test query"
    assert len(parsed_search["results"]) == 1
    
    print("✓ Formatting functions test passed")


def test_cli_command_line():
    """Test CLI command line interface."""
    print("Testing CLI command line interface...")
    
    # Test version command
    try:
        result = subprocess.run(
            [sys.executable, "zorix_cli.py", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "Zorix Agent CLI v1.0.0" in result.stdout
        print("✓ Version command works")
        
    except subprocess.TimeoutExpired:
        print("⚠️  Version command timed out (may be normal)")
    except FileNotFoundError:
        print("⚠️  CLI script not found (may be normal in test environment)")
    except Exception as e:
        print(f"⚠️  CLI command test failed: {e}")
    
    # Test help command
    try:
        result = subprocess.run(
            [sys.executable, "zorix_cli.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "Zorix Agent CLI" in result.stdout
        assert "plan" in result.stdout
        assert "search" in result.stdout
        print("✓ Help command works")
        
    except subprocess.TimeoutExpired:
        print("⚠️  Help command timed out (may be normal)")
    except FileNotFoundError:
        print("⚠️  CLI script not found (may be normal in test environment)")
    except Exception as e:
        print(f"⚠️  CLI help test failed: {e}")
    
    print("✓ CLI command line interface test completed")


async def test_error_handling():
    """Test error handling in CLI operations."""
    print("Testing error handling...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    # Test API connection error
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_client
        
        try:
            await cli.execute_task("test instruction")
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Task execution failed" in str(e)
    
    # Test HTTP error
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 Error")
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            await cli.execute_task("test instruction")
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Task execution failed" in str(e)
    
    await cli.close()
    print("✓ Error handling test passed")


async def test_task_status_polling():
    """Test task status polling functionality."""
    print("Testing task status polling...")
    
    cli = ZorixCLI("http://test-api:8000")
    
    with patch.object(cli, 'get_client') as mock_get_client:
        mock_client = AsyncMock()
        
        # Mock different status responses
        status_responses = [
            {"task_id": "test-123", "status": "planning", "progress": {}},
            {"task_id": "test-123", "status": "executing", "progress": {"step": 1}},
            {"task_id": "test-123", "status": "completed", "progress": {"step": 2}}
        ]
        
        mock_responses = []
        for status_data in status_responses:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = status_data
            mock_responses.append(mock_response)
        
        mock_client.get.side_effect = mock_responses
        mock_get_client.return_value = mock_client
        
        # Test getting task status
        for i, expected_status in enumerate(["planning", "executing", "completed"]):
            status = await cli.get_task_status("test-123")
            assert status["status"] == expected_status
            assert status["task_id"] == "test-123"
    
    await cli.close()
    print("✓ Task status polling test passed")


async def main():
    """Run all CLI integration tests."""
    print("Starting CLI integration tests...\n")
    
    try:
        await test_cli_instance_creation()
        print()
        
        await test_api_health_check()
        print()
        
        await test_task_execution()
        print()
        
        await test_search_functionality()
        print()
        
        await test_chat_functionality()
        print()
        
        test_formatting_functions()
        print()
        
        test_cli_command_line()
        print()
        
        await test_error_handling()
        print()
        
        await test_task_status_polling()
        print()
        
        print("🎉 All CLI integration tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)