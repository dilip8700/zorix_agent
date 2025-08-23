"""Main CLI application for Zorix Agent."""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.syntax import Syntax

from agent.config import get_settings
from agent.observability import configure_logging, get_logger
from agent.cli.config import cli_config, config, get_config_value

console = Console()
logger = get_logger(__name__)


class ZorixCLI:
    """Main CLI application class."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:8000"):
        self.settings = get_settings()
        self.console = console
        self.api_url = api_url.rstrip('/')
        self._client = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for API communication."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=httpx.Timeout(30.0)
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
    
    async def check_api_health(self) -> bool:
        """Check if the API is healthy."""
        try:
            client = await self.get_client()
            response = await client.get("/api/v1/system/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False
    
    async def execute_task(
        self,
        instruction: str,
        dry_run: bool = False,
        auto_approve: bool = False,
        output_format: str = "rich"
    ) -> Dict[str, Any]:
        """Execute a task via the API."""
        try:
            client = await self.get_client()
            
            payload = {
                "instruction": instruction,
                "dry_run": dry_run,
                "auto_approve": auto_approve,
                "generate_preview": True,
                "estimate_cost": True
            }
            
            response = await client.post("/api/v1/tasks/execute", json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error executing task: {e}")
            raise click.ClickException(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            raise click.ClickException(f"Task execution failed: {e}")
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status."""
        try:
            client = await self.get_client()
            response = await client.get(f"/api/v1/tasks/{task_id}/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            raise click.ClickException(f"Failed to get task status: {e}")
    
    async def search_content(
        self,
        query: str,
        search_type: str = "all",
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Search content via API."""
        try:
            client = await self.get_client()
            
            payload = {
                "query": query,
                "search_type": search_type,
                "max_results": max_results
            }
            
            response = await client.post("/api/v1/search/", json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error searching content: {e}")
            raise click.ClickException(f"Search failed: {e}")
    
    async def chat_with_agent(self, message: str) -> str:
        """Send a chat message to the agent."""
        try:
            client = await self.get_client()
            
            payload = {
                "message": message,
                "stream": False
            }
            
            response = await client.post("/api/v1/chat/message", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get("message", "No response")
            
        except Exception as e:
            logger.error(f"Error chatting with agent: {e}")
            raise click.ClickException(f"Chat failed: {e}")
    
    def format_task_result(self, result: Dict[str, Any], output_format: str = "rich"):
        """Format task execution result."""
        if output_format == "json":
            return json.dumps(result, indent=2)
        
        # Rich formatting
        task_id = result.get("task_id", "unknown")
        status = result.get("status", "unknown")
        message = result.get("message", "")
        
        panel_title = f"Task {task_id}"
        panel_content = f"Status: {status}\nMessage: {message}"
        
        if result.get("requires_approval"):
            panel_content += f"\n\n⚠️  Approval Required: {result.get('approval_message', '')}"
        
        return Panel(panel_content, title=panel_title, border_style="blue")
    
    def format_search_results(self, results: Dict[str, Any], output_format: str = "rich"):
        """Format search results."""
        if output_format == "json":
            return json.dumps(results, indent=2)
        
        # Rich formatting
        query = results.get("query", "")
        search_results = results.get("results", [])
        total = results.get("total_results", 0)
        search_time = results.get("search_time_ms", 0)
        
        table = Table(title=f"Search Results for '{query}' ({total} results, {search_time:.1f}ms)")
        table.add_column("Type", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Content", style="white")
        table.add_column("Score", style="yellow")
        
        for result in search_results:
            content = result.get("content", "")[:100] + "..." if len(result.get("content", "")) > 100 else result.get("content", "")
            
            table.add_row(
                result.get("type", ""),
                result.get("title", ""),
                content,
                f"{result.get('score', 0):.2f}"
            )
        
        return table
    
    def format_git_status(self, status_info: Dict[str, Any], output_format: str = "rich"):
        """Format git status information."""
        if output_format == "json":
            return json.dumps(status_info, indent=2)
        
        # Rich formatting
        tree = Tree("Git Status")
        
        if status_info.get("modified"):
            modified_branch = tree.add("Modified Files", style="yellow")
            for file in status_info["modified"]:
                modified_branch.add(file)
        
        if status_info.get("untracked"):
            untracked_branch = tree.add("Untracked Files", style="red")
            for file in status_info["untracked"]:
                untracked_branch.add(file)
        
        if status_info.get("staged"):
            staged_branch = tree.add("Staged Files", style="green")
            for file in status_info["staged"]:
                staged_branch.add(file)
        
        return tree


# Global CLI instance
cli_instance = ZorixCLI()


@click.group()
@click.option("--api-url", help="API server URL")
@click.option("--log-level", help="Logging level")
@click.option("--output", "-o", type=click.Choice(["rich", "json"]), help="Output format")
@click.pass_context
def cli(ctx, api_url, log_level, output):
    """Zorix Agent CLI - AI-powered development assistant."""
    
    # Get configuration values with CLI options taking precedence
    api_url = api_url or get_config_value("api_url", "http://127.0.0.1:8000", "ZORIX_API_URL")
    log_level = log_level or get_config_value("log_level", "INFO", "ZORIX_LOG_LEVEL")
    output = output or get_config_value("output_format", "rich", "ZORIX_OUTPUT_FORMAT")
    
    # Configure logging
    configure_logging(level=log_level, format_type="text")
    
    # Store context
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url
    ctx.obj["output_format"] = output
    
    # Update CLI instance
    global cli_instance
    cli_instance = ZorixCLI(api_url)


@cli.command()
@click.argument("instruction")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.option("--auto-approve", is_flag=True, help="Auto-approve low-risk tasks")
@click.option("--wait", is_flag=True, help="Wait for task completion")
@click.pass_context
def plan(ctx, instruction, dry_run, auto_approve, wait):
    """Create and optionally execute a plan from natural language instruction."""
    
    async def execute_plan():
        output_format = ctx.obj["output_format"]
        
        # Check API health
        if not await cli_instance.check_api_health():
            console.print("❌ API server is not available", style="red")
            return
        
        console.print(f"🤖 Planning: {instruction}")
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Creating plan...", total=None)
                
                result = await cli_instance.execute_task(
                    instruction=instruction,
                    dry_run=dry_run,
                    auto_approve=auto_approve,
                    output_format=output_format
                )
                
                progress.update(task, description="Plan created!")
            
            # Display result
            formatted_result = cli_instance.format_task_result(result, output_format)
            console.print(formatted_result)
            
            # Wait for completion if requested
            if wait and not dry_run:
                task_id = result.get("task_id")
                if task_id:
                    await wait_for_task_completion(task_id, output_format)
        
        except click.ClickException:
            raise
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(execute_plan())


@cli.command()
@click.argument("task_id")
@click.option("--approve", is_flag=True, help="Approve the task")
@click.option("--reject", is_flag=True, help="Reject the task")
@click.pass_context
def apply(ctx, task_id, approve, reject):
    """Apply or manage a pending task."""
    
    async def manage_task():
        output_format = ctx.obj["output_format"]
        
        if not await cli_instance.check_api_health():
            console.print("❌ API server is not available", style="red")
            return
        
        try:
            # Get task status first
            status = await cli_instance.get_task_status(task_id)
            console.print(f"Task {task_id} status: {status.get('status', 'unknown')}")
            
            if approve:
                client = await cli_instance.get_client()
                response = await client.post(
                    f"/api/v1/tasks/{task_id}/approve",
                    json={"task_id": task_id, "approved": True}
                )
                response.raise_for_status()
                console.print("✅ Task approved", style="green")
                
                # Wait for completion
                await wait_for_task_completion(task_id, output_format)
            
            elif reject:
                client = await cli_instance.get_client()
                response = await client.post(
                    f"/api/v1/tasks/{task_id}/approve",
                    json={"task_id": task_id, "approved": False, "response_message": "Rejected via CLI"}
                )
                response.raise_for_status()
                console.print("❌ Task rejected", style="red")
            
            else:
                # Just show status
                if output_format == "json":
                    console.print(json.dumps(status, indent=2))
                else:
                    formatted_status = cli_instance.format_task_result(status, output_format)
                    console.print(formatted_status)
        
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(manage_task())


@cli.command()
@click.argument("query")
@click.option("--type", "-t", default="all", type=click.Choice(["all", "code", "memory", "files"]), help="Search type")
@click.option("--max-results", "-n", default=10, help="Maximum results to return")
@click.pass_context
def search(ctx, query, type, max_results):
    """Search through code, memory, and files."""
    
    async def perform_search():
        output_format = ctx.obj["output_format"]
        
        if not await cli_instance.check_api_health():
            console.print("❌ API server is not available", style="red")
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Searching...", total=None)
                
                results = await cli_instance.search_content(
                    query=query,
                    search_type=type,
                    max_results=max_results
                )
                
                progress.update(task, description="Search completed!")
            
            # Display results
            formatted_results = cli_instance.format_search_results(results, output_format)
            console.print(formatted_results)
        
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(perform_search())


@cli.command()
@click.argument("message")
@click.pass_context
def chat(ctx, message):
    """Chat with the agent."""
    
    async def chat_session():
        output_format = ctx.obj["output_format"]
        
        if not await cli_instance.check_api_health():
            console.print("❌ API server is not available", style="red")
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Thinking...", total=None)
                
                response = await cli_instance.chat_with_agent(message)
                
                progress.update(task, description="Response received!")
            
            # Display response
            if output_format == "json":
                console.print(json.dumps({"response": response}, indent=2))
            else:
                console.print(Panel(response, title="Agent Response", border_style="green"))
        
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(chat_session())


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status."""
    
    async def show_status():
        output_format = ctx.obj["output_format"]
        
        try:
            client = await cli_instance.get_client()
            response = await client.get("/api/v1/system/status")
            
            if response.status_code == 200:
                status_data = response.json()
                
                if output_format == "json":
                    console.print(json.dumps(status_data, indent=2))
                else:
                    # Rich formatting
                    table = Table(title="System Status")
                    table.add_column("Component", style="cyan")
                    table.add_column("Status", style="green")
                    table.add_column("Details", style="white")
                    
                    table.add_row("API", "✅ Running", f"Uptime: {status_data.get('uptime_seconds', 0):.0f}s")
                    table.add_row("Bedrock", status_data.get('bedrock_status', 'unknown'), "")
                    table.add_row("Vector Index", status_data.get('vector_index_status', 'unknown'), "")
                    table.add_row("Active Tasks", str(status_data.get('active_tasks', 0)), "")
                    table.add_row("Memory Usage", f"{status_data.get('memory_usage_mb', 0):.1f} MB", "")
                    
                    console.print(table)
            else:
                console.print("❌ API server is not responding properly", style="red")
        
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(show_status())


@cli.group()
def git():
    """Git operations."""
    pass


@git.command()
@click.pass_context
def git_status(ctx):
    """Show git status."""
    
    async def show_git_status():
        output_format = ctx.obj["output_format"]
        
        try:
            # Execute git status command via the agent
            result = await cli_instance.execute_task(
                instruction="Show git status",
                dry_run=True,
                auto_approve=True
            )
            
            # For now, just show the task result
            formatted_result = cli_instance.format_task_result(result, output_format)
            console.print(formatted_result)
        
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(show_git_status())


@git.command()
@click.argument("message")
@click.pass_context
def commit(ctx, message):
    """Commit changes with a message."""
    
    async def commit_changes():
        try:
            result = await cli_instance.execute_task(
                instruction=f"Commit all changes with message: {message}",
                dry_run=False,
                auto_approve=False
            )
            
            formatted_result = cli_instance.format_task_result(result, ctx.obj["output_format"])
            console.print(formatted_result)
        
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
    
    asyncio.run(commit_changes())


async def wait_for_task_completion(task_id: str, output_format: str = "rich"):
    """Wait for task completion and show progress."""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Executing task...", total=None)
        
        while True:
            try:
                status = await cli_instance.get_task_status(task_id)
                current_status = status.get("status", "unknown")
                
                progress.update(task, description=f"Status: {current_status}")
                
                if current_status in ["completed", "failed", "cancelled"]:
                    break
                
                await asyncio.sleep(2)  # Poll every 2 seconds
            
            except Exception as e:
                console.print(f"❌ Error checking task status: {e}", style="red")
                break
        
        # Show final status
        final_status = await cli_instance.get_task_status(task_id)
        formatted_status = cli_instance.format_task_result(final_status, output_format)
        console.print(formatted_status)


@cli.command()
def version():
    """Show version information."""
    console.print("Zorix Agent CLI v1.0.0", style="bold blue")


# Add config subcommand
cli.add_command(config)


if __name__ == "__main__":
    try:
        cli()
    finally:
        # Cleanup
        try:
            asyncio.run(cli_instance.close())
        except:
            pass