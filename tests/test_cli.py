"""Tests for CLI functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from agent.cli.main import ZorixCLI, cli


class TestZorixCLI:
    """Test ZorixCLI class functionality."""
    
    @pytest.fixture
    def cli_instance(self):
        """Create CLI instance for testing."""
        return ZorixCLI(api_url="http://test-api:8000")
    
    @pytest.mark.asyncio
    async def test_check_api_health_success(self, cli_instance):
        """Test successful API health check."""
        with patch.object(cli_instance, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await cli_instance.check_api_health()
            assert result is True
            mock_client.get.assert_called_once_with("/api/v1/system/health")
    
    @pytest.mark.asyncio
    async def test_check_api_health_failure(self, cli_instance):
        """Test failed API health check."""
        with patch.object(cli_instance, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection failed")
            mock_get_client.return_value = mock_client
            
            result = await cli_instance.check_api_health()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self, cli_instance):
        """Test successful task execution."""
        with patch.object(cli_instance, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "task_id": "test-123",
                "status": "started",
                "message": "Task created successfully"
            }
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await cli_instance.execute_task("test instruction")
            
            assert result["task_id"] == "test-123"
            assert result["status"] == "started"
            mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_content(self, cli_instance):
        """Test content search."""
        with patch.object(cli_instance, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "query": "test query",
                "results": [
                    {
                        "type": "code",
                        "title": "Test Function",
                        "content": "def test(): pass",
                        "score": 0.95
                    }
                ],
                "total_results": 1,
                "search_time_ms": 50.0
            }
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await cli_instance.search_content("test query")
            
            assert result["query"] == "test query"
            assert len(result["results"]) == 1
            assert result["results"][0]["type"] == "code"
    
    @pytest.mark.asyncio
    async def test_chat_with_agent(self, cli_instance):
        """Test chat functionality."""
        with patch.object(cli_instance, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "message": "Hello! How can I help you?",
                "session_id": "session-123"
            }
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await cli_instance.chat_with_agent("Hello")
            
            assert result == "Hello! How can I help you?"
    
    def test_format_task_result_rich(self, cli_instance):
        """Test rich formatting of task results."""
        result = {
            "task_id": "test-123",
            "status": "completed",
            "message": "Task completed successfully"
        }
        
        formatted = cli_instance.format_task_result(result, "rich")
        assert "test-123" in str(formatted)
        assert "completed" in str(formatted)
    
    def test_format_task_result_json(self, cli_instance):
        """Test JSON formatting of task results."""
        result = {
            "task_id": "test-123",
            "status": "completed",
            "message": "Task completed successfully"
        }
        
        formatted = cli_instance.format_task_result(result, "json")
        parsed = json.loads(formatted)
        assert parsed["task_id"] == "test-123"
        assert parsed["status"] == "completed"
    
    def test_format_search_results_rich(self, cli_instance):
        """Test rich formatting of search results."""
        results = {
            "query": "test query",
            "results": [
                {
                    "type": "code",
                    "title": "Test Function",
                    "content": "def test(): pass",
                    "score": 0.95
                }
            ],
            "total_results": 1,
            "search_time_ms": 50.0
        }
        
        formatted = cli_instance.format_search_results(results, "rich")
        assert "test query" in str(formatted)
        assert "Test Function" in str(formatted)
    
    def test_format_search_results_json(self, cli_instance):
        """Test JSON formatting of search results."""
        results = {
            "query": "test query",
            "results": [
                {
                    "type": "code",
                    "title": "Test Function",
                    "content": "def test(): pass",
                    "score": 0.95
                }
            ],
            "total_results": 1,
            "search_time_ms": 50.0
        }
        
        formatted = cli_instance.format_search_results(results, "json")
        parsed = json.loads(formatted)
        assert parsed["query"] == "test query"
        assert len(parsed["results"]) == 1


class TestCLICommands:
    """Test CLI command functionality."""
    
    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Zorix Agent CLI" in result.output
        assert "plan" in result.output
        assert "search" in result.output
        assert "chat" in result.output
    
    def test_version_command(self):
        """Test version command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        
        assert result.exit_code == 0
        assert "Zorix Agent CLI v1.0.0" in result.output
    
    @patch('agent.cli.main.cli_instance')
    def test_plan_command_dry_run(self, mock_cli_instance):
        """Test plan command with dry run."""
        mock_cli_instance.check_api_health = AsyncMock(return_value=True)
        mock_cli_instance.execute_task = AsyncMock(return_value={
            "task_id": "test-123",
            "status": "planned",
            "message": "Plan created (dry run)"
        })
        mock_cli_instance.format_task_result = MagicMock(return_value="Formatted result")
        
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "create a test file", "--dry-run"])
        
        # Note: This test may not work perfectly due to asyncio in CLI
        # In a real scenario, you'd need more sophisticated mocking
        assert result.exit_code == 0
    
    @patch('agent.cli.main.cli_instance')
    def test_search_command(self, mock_cli_instance):
        """Test search command."""
        mock_cli_instance.check_api_health = AsyncMock(return_value=True)
        mock_cli_instance.search_content = AsyncMock(return_value={
            "query": "test",
            "results": [],
            "total_results": 0,
            "search_time_ms": 10.0
        })
        mock_cli_instance.format_search_results = MagicMock(return_value="No results")
        
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "test"])
        
        assert result.exit_code == 0
    
    @patch('agent.cli.main.cli_instance')
    def test_chat_command(self, mock_cli_instance):
        """Test chat command."""
        mock_cli_instance.check_api_health = AsyncMock(return_value=True)
        mock_cli_instance.chat_with_agent = AsyncMock(return_value="Hello!")
        
        runner = CliRunner()
        result = runner.invoke(cli, ["chat", "Hello"])
        
        assert result.exit_code == 0
    
    def test_git_help(self):
        """Test git subcommand help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--help"])
        
        assert result.exit_code == 0
        assert "Git operations" in result.output
    
    @patch('agent.cli.main.cli_instance')
    def test_status_command(self, mock_cli_instance):
        """Test status command."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "running",
            "uptime_seconds": 3600,
            "bedrock_status": "healthy",
            "vector_index_status": "healthy",
            "active_tasks": 0,
            "memory_usage_mb": 256.5
        }
        mock_client.get.return_value = mock_response
        mock_cli_instance.get_client = AsyncMock(return_value=mock_client)
        
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        
        assert result.exit_code == 0


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    @pytest.mark.asyncio
    async def test_cli_instance_lifecycle(self):
        """Test CLI instance creation and cleanup."""
        cli_instance = ZorixCLI("http://test:8000")
        
        # Test client creation
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            client = await cli_instance.get_client()
            assert client is mock_client
            
            # Test cleanup
            await cli_instance.close()
            mock_client.aclose.assert_called_once()
    
    def test_output_format_options(self):
        """Test different output format options."""
        runner = CliRunner()
        
        # Test rich output (default)
        result = runner.invoke(cli, ["--output", "rich", "version"])
        assert result.exit_code == 0
        
        # Test JSON output
        result = runner.invoke(cli, ["--output", "json", "version"])
        assert result.exit_code == 0
    
    def test_api_url_option(self):
        """Test API URL option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--api-url", "http://custom:9000", "version"])
        assert result.exit_code == 0
    
    def test_log_level_option(self):
        """Test log level option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--log-level", "DEBUG", "version"])
        assert result.exit_code == 0


if __name__ == "__main__":
    pytest.main([__file__])