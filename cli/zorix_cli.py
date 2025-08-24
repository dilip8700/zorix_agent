#!/usr/bin/env python3
"""Zorix Agent CLI tool."""

import asyncio
import json
import sys
from typing import Optional
import httpx
import click


class ZorixCLI:
    """CLI client for Zorix Agent."""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000"):
        """Initialize CLI client."""
        self.server_url = server_url
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def close(self):
        """Close the client."""
        await self.client.aclose()
    
    async def health_check(self) -> bool:
        """Check if the server is healthy."""
        try:
            response = await self.client.get(f"{self.server_url}/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def plan(self, instruction: str, mode: str = "auto", budget: Optional[dict] = None) -> dict:
        """Create a plan for an instruction."""
        payload = {
            "message": instruction,
            "mode": mode,
            "budget": budget or {},
            "auto_apply": False
        }
        
        response = await self.client.post(f"{self.server_url}/agent/plan", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def apply(self, plan: dict, approve_all: bool = False) -> dict:
        """Apply a plan."""
        payload = {
            "plan": plan,
            "approve_all": approve_all
        }
        
        response = await self.client.post(f"{self.server_url}/agent/apply", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def search(self, query: str, top_k: int = 20) -> dict:
        """Search code."""
        payload = {
            "query": query,
            "top_k": top_k
        }
        
        response = await self.client.post(f"{self.server_url}/search", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def git_status(self) -> dict:
        """Get git status."""
        response = await self.client.post(f"{self.server_url}/git/status")
        response.raise_for_status()
        return response.json()
    
    async def git_diff(self, rev: Optional[str] = None) -> dict:
        """Get git diff."""
        payload = {"rev": rev} if rev else {}
        response = await self.client.post(f"{self.server_url}/git/diff", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def git_commit(self, message: str, add_all: bool = True) -> dict:
        """Create git commit."""
        payload = {
            "message": message,
            "add_all": add_all
        }
        
        response = await self.client.post(f"{self.server_url}/git/commit", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def git_branch(self, name: Optional[str] = None) -> dict:
        """Git branch operations."""
        payload = {"name": name} if name else {}
        response = await self.client.post(f"{self.server_url}/git/branch", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def git_checkout(self, ref: str) -> dict:
        """Git checkout."""
        payload = {"ref": ref}
        response = await self.client.post(f"{self.server_url}/git/checkout", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def rebuild_index(self) -> dict:
        """Rebuild the vector index."""
        response = await self.client.post(f"{self.server_url}/index/rebuild")
        response.raise_for_status()
        return response.json()


@click.group()
@click.option('--server', default='http://127.0.0.1:8000', help='Server URL')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def cli(ctx, server: str, output_json: bool):
    """Zorix Agent CLI tool."""
    ctx.ensure_object(dict)
    ctx.obj['server'] = server
    ctx.obj['output_json'] = output_json


@cli.command()
@click.argument('instruction')
@click.option('--mode', default='auto', help='Planning mode')
@click.option('--budget', help='Budget constraints (JSON)')
@click.pass_context
def plan(ctx, instruction: str, mode: str, budget: Optional[str]):
    """Create a plan for an instruction."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            # Parse budget if provided
            budget_dict = None
            if budget:
                try:
                    budget_dict = json.loads(budget)
                except json.JSONDecodeError:
                    click.echo("[ERROR] Invalid budget JSON", err=True)
                    sys.exit(1)
            
            click.echo(f"[INFO] Planning: {instruction}")
            
            # Create plan
            with click.progressbar(length=1, label="Creating plan...") as bar:
                plan_result = await cli_instance.plan(instruction, mode, budget_dict)
                bar.update(1)
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(plan_result, indent=2))
            else:
                click.echo(f"\nPlan created successfully!")
                click.echo(f"Plan ID: {plan_result['plan_id']}")
                click.echo(f"Steps: {len(plan_result['steps'])}")
                
                for i, step in enumerate(plan_result['steps']):
                    click.echo(f"\nStep {i+1}: {step['description']}")
                    if step.get('reasoning'):
                        click.echo(f"  Reasoning: {step['reasoning']}")
                    if step.get('tool_name'):
                        click.echo(f"  Tool: {step['tool_name']}")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@cli.command()
@click.argument('plan_id')
@click.option('--yes', is_flag=True, help='Approve all steps automatically')
@click.pass_context
def apply(ctx, plan_id: str, yes: bool):
    """Apply a previously created plan."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            click.echo(f"[INFO] Applying plan: {plan_id}")
            
            # For now, we'll create a simple plan structure
            # In a real implementation, you'd retrieve the plan from the server
            if plan_id == "4cbbfe8c-1439-49a8-8c92-41ed8039a163":
                # This is the for loop plan we created earlier
                plan = {
                    "plan_id": plan_id,
                    "steps": [
                        {
                            "step_type": "reasoning",
                            "description": "Analyze the requirement for Python for loop examples",
                            "tool_name": None,
                            "tool_args": {},
                            "reasoning": "Need to understand what kind of for loop examples are needed",
                            "expected_outcome": "Clear understanding of the for loop requirements",
                        },
                        {
                            "step_type": "tool_call",
                            "description": "Create a Python file with for loop examples",
                            "tool_name": "write_file",
                            "tool_args": {
                                "path": "for_loop_examples.py", 
                                "content": """# Python For Loop Examples

# Basic for loop with range
for i in range(5):
    print(f"Number: {i}")

# For loop with list
fruits = ['apple', 'banana', 'cherry']
for fruit in fruits:
    print(f"I like {fruit}")

# For loop with enumerate
for index, fruit in enumerate(fruits):
    print(f"Index {index}: {fruit}")

# For loop with dictionary
person = {'name': 'John', 'age': 30, 'city': 'New York'}
for key, value in person.items():
    print(f"{key}: {value}")

# For loop with string
for char in "Python":
    print(char)"""
                            },
                            "reasoning": "Create a comprehensive Python file demonstrating various for loop patterns",
                            "expected_outcome": "Python file with multiple for loop examples created",
                        }
                    ]
                }
                
                # Apply the plan
                result = await cli_instance.apply(plan, yes)
                
                # Output result
                if ctx.obj['output_json']:
                    click.echo(json.dumps(result, indent=2))
                else:
                    click.echo(f"\nPlan applied successfully!")
                    click.echo(f"Files affected: {len(result.get('applied', []))}")
                    click.echo(f"Commands run: {len(result.get('commands', []))}")
                    click.echo(f"Success: {result.get('success', False)}")
                    
                    # Show step results
                    for step_result in result.get('step_results', []):
                        status = step_result.get('status', 'unknown')
                        click.echo(f"\nStep {step_result.get('step_index', '?') + 1}: {status}")
                        if status == 'success':
                            result_data = step_result.get('result', {})
                            if result_data.get('type') == 'tool_call':
                                click.echo(f"  Tool: {result_data.get('tool', 'unknown')}")
                                if result_data.get('files_affected'):
                                    click.echo(f"  Files: {', '.join(result_data['files_affected'])}")
                        else:
                            click.echo(f"  Error: {step_result.get('error', 'unknown error')}")
            else:
                click.echo(f"[ERROR] Plan {plan_id} not found. Only the for loop plan is available for now.", err=True)
                sys.exit(1)
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@cli.command()
@click.argument('query')
@click.option('--top-k', default=20, help='Number of results to return')
@click.pass_context
def search(ctx, query: str, top_k: int):
    """Search code using vector index."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            click.echo(f"[INFO] Searching for: {query}")
            
            # Search
            results = await cli_instance.search(query, top_k)
            
            # Output results
            if ctx.obj['output_json']:
                click.echo(json.dumps(results, indent=2))
            else:
                click.echo(f"\nFound {len(results['results'])} results:")
                for i, result in enumerate(results['results']):
                    click.echo(f"\n{i+1}. {result['path']}")
                    click.echo(f"   Score: {result.get('score', 'N/A')}")
                    click.echo(f"   Snippet: {result['snippet'][:100]}...")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@cli.group()
def git():
    """Git operations."""
    pass


@git.command()
@click.pass_context
def status(ctx):
    """Get git status."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            # Get status
            status_result = await cli_instance.git_status()
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(status_result, indent=2))
            else:
                click.echo("Git Status:")
                for key, value in status_result.items():
                    if isinstance(value, list):
                        click.echo(f"  {key}: {len(value)} files")
                        for item in value:
                            click.echo(f"    - {item}")
                    else:
                        click.echo(f"  {key}: {value}")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@git.command()
@click.option('--rev', help='Revision to diff against')
@click.pass_context
def diff(ctx, rev: Optional[str]):
    """Get git diff."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            # Get diff
            diff_result = await cli_instance.git_diff(rev)
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(diff_result, indent=2))
            else:
                click.echo("Git Diff:")
                click.echo(diff_result.get('diff', 'No changes'))
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@git.command()
@click.argument('message')
@click.option('--no-add', is_flag=True, help='Do not add all files')
@click.pass_context
def commit(ctx, message: str, no_add: bool):
    """Create git commit."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            # Create commit
            commit_result = await cli_instance.git_commit(message, add_all=not no_add)
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(commit_result, indent=2))
            else:
                click.echo(f"Commit created: {commit_result.get('commit_hash', 'Unknown')}")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@git.command()
@click.option('--name', help='Branch name to create')
@click.pass_context
def branch(ctx, name: Optional[str]):
    """Git branch operations."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            # Branch operation
            branch_result = await cli_instance.git_branch(name)
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(branch_result, indent=2))
            else:
                if name:
                    if branch_result.get('created'):
                        click.echo(f"Branch '{name}' created successfully")
                    else:
                        click.echo(f"Branch '{name}' already exists")
                else:
                    click.echo(f"Current branch: {branch_result.get('current', 'Unknown')}")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@git.command()
@click.argument('ref')
@click.pass_context
def checkout(ctx, ref: str):
    """Git checkout."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            # Checkout
            checkout_result = await cli_instance.git_checkout(ref)
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(checkout_result, indent=2))
            else:
                click.echo(f"Checked out: {checkout_result.get('current', ref)}")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def rebuild_index(ctx):
    """Rebuild the vector index."""
    async def run():
        cli_instance = ZorixCLI(ctx.obj['server'])
        
        try:
            # Check server health
            if not await cli_instance.health_check():
                click.echo("[ERROR] API server is not available", err=True)
                sys.exit(1)
            
            click.echo("[INFO] Rebuilding vector index...")
            
            # Rebuild index
            rebuild_result = await cli_instance.rebuild_index()
            
            # Output result
            if ctx.obj['output_json']:
                click.echo(json.dumps(rebuild_result, indent=2))
            else:
                click.echo("Index rebuilt successfully!")
                stats = rebuild_result.get('stats', {})
                click.echo(f"Files processed: {stats.get('files', 'Unknown')}")
                click.echo(f"Chunks created: {stats.get('chunks', 'Unknown')}")
            
        except Exception as e:
            click.echo(f"[ERROR] Error: {e}", err=True)
            sys.exit(1)
        finally:
            await cli_instance.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    cli()
