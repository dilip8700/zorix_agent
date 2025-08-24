# 🤖 Zorix CLI Complete Usage Guide

## 🚀 Prerequisites

1. **Start the Zorix Agent server first:**
   ```bash
   python start_zorix.py
   ```
   *(Keep this running in another terminal)*

2. **Make sure server is running:**
   - Check: http://127.0.0.1:8000/health

## 💬 **1. Chat with AI**

### Basic Chat
```bash
python zorix_cli.py chat "How do I create a Python function?"
```

### Advanced Chat Examples
```bash
# Code generation
python zorix_cli.py chat "Write a Python function to sort a list of dictionaries by a key"

# Code review
python zorix_cli.py chat "Review this code for bugs: def add(a, b): return a + b"

# Debugging help
python zorix_cli.py chat "Why is my Python function returning None instead of a value?"

# Architecture advice
python zorix_cli.py chat "How should I structure a REST API with authentication?"

# Learning
python zorix_cli.py chat "Explain async/await in Python with examples"
```

## 📋 **2. Plan and Execute Tasks**

### Create a Plan (Dry Run)
```bash
python zorix_cli.py plan "Create a hello world Python script" --dry-run
```

### Create and Execute Plan
```bash
python zorix_cli.py plan "Add error handling to my Python functions"
```

### Auto-approve Low-risk Tasks
```bash
python zorix_cli.py plan "Format my Python code" --auto-approve
```

### Wait for Completion
```bash
python zorix_cli.py plan "Run tests and fix any failures" --wait
```

### Complex Planning Examples
```bash
# Multi-file refactoring
python zorix_cli.py plan "Refactor my Python project to use proper error handling"

# Add new features
python zorix_cli.py plan "Add logging to all my Python functions"

# Code optimization
python zorix_cli.py plan "Optimize my code for better performance"

# Testing
python zorix_cli.py plan "Add unit tests for all my functions"
```

## 🔍 **3. Search Your Code**

### Search Everything
```bash
python zorix_cli.py search "function definition"
```

### Search Specific Types
```bash
# Search only code
python zorix_cli.py search "class MyClass" --type code

# Search files
python zorix_cli.py search "config.py" --type files

# Search memory/history
python zorix_cli.py search "previous conversation" --type memory
```

### Limit Results
```bash
python zorix_cli.py search "import" --max-results 5
```

### Advanced Search Examples
```bash
# Find specific patterns
python zorix_cli.py search "def.*main" --type code

# Find configuration files
python zorix_cli.py search "*.json" --type files

# Find error handling
python zorix_cli.py search "try.*except" --type code
```

## 🔧 **4. Apply Pending Tasks**

### List Pending Tasks
```bash
python zorix_cli.py apply
```

### Apply Specific Task
```bash
python zorix_cli.py apply --task-id "task-123"
```

### Apply with Confirmation
```bash
python zorix_cli.py apply --confirm
```

## 📊 **5. System Status**

### Check System Health
```bash
python zorix_cli.py status
```

### Get Detailed Status
```bash
python zorix_cli.py status --verbose
```

## 🔧 **6. Git Operations**

### Git Status
```bash
python zorix_cli.py git status
```

### Git Diff
```bash
python zorix_cli.py git diff
```

### Git Commit
```bash
python zorix_cli.py git commit -m "Add new feature"
```

### Git Branch Operations
```bash
python zorix_cli.py git branch
python zorix_cli.py git checkout main
```

## ⚙️ **7. Configuration Management**

### Show Current Config
```bash
python zorix_cli.py config show
```

### Set Configuration Values
```bash
python zorix_cli.py config set api-url http://127.0.0.1:8000
python zorix_cli.py config set output-format rich
python zorix_cli.py config set max-search-results 20
```

### Get Specific Config Value
```bash
python zorix_cli.py config get api-url
```

### Reset Configuration
```bash
python zorix_cli.py config reset
```

## 🎯 **8. Global Options**

### Change Output Format
```bash
# Rich formatted output (default)
python zorix_cli.py chat "Hello" --output rich

# JSON output (for scripting)
python zorix_cli.py chat "Hello" --output json
```

### Change API URL
```bash
python zorix_cli.py --api-url http://127.0.0.1:9000 status
```

### Change Log Level
```bash
python zorix_cli.py --log-level DEBUG chat "Hello"
```

## 🔄 **9. Practical Workflows**

### Development Workflow
```bash
# 1. Check system status
python zorix_cli.py status

# 2. Search for existing code
python zorix_cli.py search "authentication" --type code

# 3. Plan new feature
python zorix_cli.py plan "Add user authentication to my API" --dry-run

# 4. Execute the plan
python zorix_cli.py plan "Add user authentication to my API"

# 5. Check git status
python zorix_cli.py git status

# 6. Commit changes
python zorix_cli.py git commit -m "Add user authentication"
```

### Code Review Workflow
```bash
# 1. Get git diff
python zorix_cli.py git diff

# 2. Ask for code review
python zorix_cli.py chat "Review my recent changes for code quality and bugs"

# 3. Apply suggestions
python zorix_cli.py plan "Apply the code review suggestions"
```

### Debugging Workflow
```bash
# 1. Search for error patterns
python zorix_cli.py search "error.*handling" --type code

# 2. Get debugging help
python zorix_cli.py chat "My function is throwing a KeyError. Here's the code: [paste code]"

# 3. Apply fixes
python zorix_cli.py plan "Fix the KeyError in my function"
```

## 🚨 **10. Troubleshooting**

### CLI Not Connecting
```bash
# Check if server is running
curl http://127.0.0.1:8000/health

# Check CLI configuration
python zorix_cli.py config show

# Update API URL if needed
python zorix_cli.py config set api-url http://127.0.0.1:8000
```

### Server Connection Issues
```bash
# Test with different port
python zorix_cli.py --api-url http://127.0.0.1:8001 status

# Check server logs
python start_zorix.py  # Look for error messages
```

### Command Not Working
```bash
# Check command syntax
python zorix_cli.py COMMAND --help

# Use verbose logging
python zorix_cli.py --log-level DEBUG COMMAND
```

## 💡 **11. Pro Tips**

### Scripting with CLI
```bash
# Use JSON output for scripting
result=$(python zorix_cli.py search "function" --output json)
echo $result | jq '.results[0].content'

# Chain commands
python zorix_cli.py plan "Add tests" && python zorix_cli.py git commit -m "Add tests"
```

### Aliases for Common Commands
```bash
# Add to your .bashrc or .zshrc
alias zc="python zorix_cli.py chat"
alias zp="python zorix_cli.py plan"
alias zs="python zorix_cli.py search"
alias zg="python zorix_cli.py git"

# Then use:
zc "How do I optimize this code?"
zp "Add error handling" --dry-run
zs "function definition"
zg status
```

### Configuration Tips
```bash
# Set up for your environment
python zorix_cli.py config set auto-approve-low-risk true
python zorix_cli.py config set default-dry-run false
python zorix_cli.py config set max-search-results 10
```

## 🎉 **Quick Reference**

| Command | Purpose | Example |
|---------|---------|---------|
| `chat` | Ask AI questions | `chat "How do I...?"` |
| `plan` | Create/execute plans | `plan "Add feature X"` |
| `search` | Find code/files | `search "function name"` |
| `apply` | Execute pending tasks | `apply --confirm` |
| `status` | Check system health | `status` |
| `git` | Git operations | `git status` |
| `config` | Manage settings | `config show` |

## 🚀 **Getting Started**

1. **Start server**: `python start_zorix.py`
2. **Test CLI**: `python zorix_cli.py status`
3. **Chat with AI**: `python zorix_cli.py chat "Hello, help me code!"`
4. **Plan a task**: `python zorix_cli.py plan "Create a Python script" --dry-run`

**You're ready to use your AI coding assistant from the command line!** 🤖