# Zorix Agent CLI

A powerful command-line interface for interacting with the Zorix Agent system.

## Installation

The CLI is included with the Zorix Agent installation. You can run it directly:

```bash
python zorix_cli.py --help
```

Or install it as a package and use the `zorix` command (if configured in setup.py).

## Quick Start

1. **Start the API server** (in another terminal):
   ```bash
   python run_web.py
   ```

2. **Check system status**:
   ```bash
   python zorix_cli.py status
   ```

3. **Execute a task**:
   ```bash
   python zorix_cli.py plan "Create a Python function to calculate fibonacci numbers"
   ```

4. **Search for content**:
   ```bash
   python zorix_cli.py search "fibonacci function"
   ```

5. **Chat with the agent**:
   ```bash
   python zorix_cli.py chat "How do I implement a binary search?"
   ```

## Commands

### Core Commands

#### `plan <instruction>`
Create and optionally execute a plan from natural language instruction.

```bash
# Create a plan (dry run)
python zorix_cli.py plan "Add error handling to the main function" --dry-run

# Execute a plan with auto-approval for low-risk tasks
python zorix_cli.py plan "Fix the typo in README.md" --auto-approve

# Execute and wait for completion
python zorix_cli.py plan "Run the test suite" --wait
```

**Options:**
- `--dry-run`: Show what would be done without executing
- `--auto-approve`: Auto-approve low-risk tasks
- `--wait`: Wait for task completion

#### `apply <task_id>`
Apply or manage a pending task.

```bash
# Show task status
python zorix_cli.py apply task-123

# Approve a task
python zorix_cli.py apply task-123 --approve

# Reject a task
python zorix_cli.py apply task-123 --reject
```

#### `search <query>`
Search through code, memory, and files.

```bash
# Search all content
python zorix_cli.py search "authentication function"

# Search only code
python zorix_cli.py search "login" --type code

# Limit results
python zorix_cli.py search "error handling" --max-results 5
```

**Options:**
- `--type, -t`: Search type (all, code, memory, files)
- `--max-results, -n`: Maximum results to return

#### `chat <message>`
Chat with the agent.

```bash
python zorix_cli.py chat "Explain how async/await works in Python"
python zorix_cli.py chat "What's the best way to handle database connections?"
```

#### `status`
Show system status.

```bash
python zorix_cli.py status
```

### Git Commands

#### `git status`
Show git status.

```bash
python zorix_cli.py git status
```

#### `git commit <message>`
Commit changes with a message.

```bash
python zorix_cli.py git commit "Add new feature implementation"
```

### Configuration Commands

#### `config show`
Show current configuration.

```bash
python zorix_cli.py config show
```

#### `config set <key> <value>`
Set a configuration value.

```bash
python zorix_cli.py config set api_url http://localhost:9000
python zorix_cli.py config set auto_approve_low_risk true
python zorix_cli.py config set max_search_results 20
```

#### `config get <key>`
Get a configuration value.

```bash
python zorix_cli.py config get api_url
```

#### `config reset`
Reset configuration to defaults.

```bash
python zorix_cli.py config reset
```

#### `config edit`
Edit configuration file in default editor.

```bash
python zorix_cli.py config edit
```

## Global Options

- `--api-url`: API server URL (default: http://127.0.0.1:8000)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--output, -o`: Output format (rich, json)

## Output Formats

### Rich Format (Default)
Provides colorized, formatted output with tables, panels, and progress indicators.

### JSON Format
Provides machine-readable JSON output for scripting and automation.

```bash
python zorix_cli.py search "test" --output json | jq '.results[].title'
```

## Configuration

The CLI stores configuration in `~/.zorix/config.json`. You can configure:

- `api_url`: API server URL
- `output_format`: Default output format (rich/json)
- `log_level`: Logging level
- `auto_approve_low_risk`: Auto-approve low-risk tasks
- `default_dry_run`: Default to dry-run mode
- `max_search_results`: Maximum search results
- `poll_interval`: Task polling interval (seconds)
- `request_timeout`: HTTP request timeout (seconds)

## Environment Variables

You can override configuration with environment variables:

- `ZORIX_API_URL`: API server URL
- `ZORIX_LOG_LEVEL`: Logging level
- `ZORIX_OUTPUT_FORMAT`: Output format

```bash
export ZORIX_API_URL=http://production-server:8000
python zorix_cli.py status
```

## Examples

### Development Workflow

```bash
# Check what needs to be done
python zorix_cli.py git status

# Plan and execute a task
python zorix_cli.py plan "Fix the failing tests in test_auth.py" --wait

# Search for related code
python zorix_cli.py search "authentication tests" --type code

# Chat about the implementation
python zorix_cli.py chat "What's the best practice for testing authentication?"

# Commit the changes
python zorix_cli.py git commit "Fix authentication tests"
```

### Automation and Scripting

```bash
#!/bin/bash

# Get system status as JSON
STATUS=$(python zorix_cli.py status --output json)

# Check if API is healthy
if echo "$STATUS" | jq -e '.bedrock_status == "healthy"' > /dev/null; then
    echo "System is healthy, proceeding with tasks..."
    
    # Execute automated tasks
    python zorix_cli.py plan "Run code quality checks" --auto-approve --wait
    python zorix_cli.py plan "Update documentation" --auto-approve --wait
else
    echo "System is not healthy, aborting..."
    exit 1
fi
```

### Search and Analysis

```bash
# Find all TODO comments
python zorix_cli.py search "TODO" --type code --max-results 50

# Search for security-related code
python zorix_cli.py search "password OR authentication OR security" --type code

# Find recent memory about a topic
python zorix_cli.py search "database migration" --type memory
```

## Error Handling

The CLI provides clear error messages and exit codes:

- Exit code 0: Success
- Exit code 1: General error
- Exit code 2: API connection error

```bash
python zorix_cli.py plan "invalid task" || echo "Task failed with exit code $?"
```

## Troubleshooting

### API Connection Issues

1. **Check if the API server is running**:
   ```bash
   python zorix_cli.py status
   ```

2. **Verify the API URL**:
   ```bash
   python zorix_cli.py config get api_url
   ```

3. **Test with curl**:
   ```bash
   curl http://127.0.0.1:8000/api/v1/system/health
   ```

### Configuration Issues

1. **Reset configuration**:
   ```bash
   python zorix_cli.py config reset
   ```

2. **Check configuration file**:
   ```bash
   cat ~/.zorix/config.json
   ```

### Debugging

Enable debug logging:

```bash
python zorix_cli.py --log-level DEBUG plan "test task"
```

## Integration with Other Tools

### Shell Completion

Add to your shell profile for command completion:

```bash
# For bash
eval "$(_ZORIX_CLI_COMPLETE=bash_source python zorix_cli.py)"

# For zsh
eval "$(_ZORIX_CLI_COMPLETE=zsh_source python zorix_cli.py)"
```

### IDE Integration

You can integrate the CLI with your IDE or editor:

```json
{
  "tasks": [
    {
      "label": "Zorix: Plan Task",
      "type": "shell",
      "command": "python zorix_cli.py plan '${input:taskDescription}'"
    }
  ]
}
```

## Contributing

The CLI is built with:
- [Click](https://click.palletsprojects.com/) for command-line interface
- [Rich](https://rich.readthedocs.io/) for beautiful terminal output
- [httpx](https://www.python-httpx.org/) for HTTP client functionality

To add new commands:

1. Add the command function to `agent/cli/main.py`
2. Use the `@cli.command()` decorator
3. Add appropriate options and arguments
4. Include help text and examples
5. Add tests in `tests/test_cli.py`