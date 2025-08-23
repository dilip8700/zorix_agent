# Zorix Agent User Guide

A comprehensive guide to using the Zorix Agent system for AI-powered development assistance.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [Using the Web Interface](#using-the-web-interface)
4. [Using the CLI](#using-the-cli)
5. [Task Planning and Execution](#task-planning-and-execution)
6. [Chat Interface](#chat-interface)
7. [File Management](#file-management)
8. [Search and Discovery](#search-and-discovery)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- AWS account with Bedrock access
- Python 3.11 or higher
- Basic understanding of software development

### Quick Setup

1. **Install and Configure**
   ```bash
   git clone <repository-url>
   cd zorix-agent
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your AWS credentials
   ```

2. **Start the System**
   ```bash
   python run_web.py
   ```

3. **Access the Interface**
   - Web Interface: http://localhost:8000/static/index.html
   - API Documentation: http://localhost:8000/docs

### First Steps

1. **Check System Status**
   - Visit the web interface dashboard
   - Or use CLI: `python zorix_cli.py status`

2. **Try a Simple Task**
   ```bash
   python zorix_cli.py plan "Create a hello world Python script"
   ```

3. **Start a Chat**
   ```bash
   python zorix_cli.py chat "How do I use this system?"
   ```

## Core Concepts

### Agent Architecture

Zorix Agent consists of several key components:

- **Planning System**: Analyzes tasks and creates execution plans
- **Execution Engine**: Carries out planned actions safely
- **Memory System**: Stores and retrieves contextual information
- **Vector Search**: Enables semantic search across code and documentation
- **Chat Interface**: Provides conversational AI assistance

### Task Lifecycle

1. **Planning**: Agent analyzes your instruction and creates a plan
2. **Preview**: You can review what the agent will do
3. **Approval**: High-risk tasks require explicit approval
4. **Execution**: Agent carries out the planned actions
5. **Completion**: Results are presented and stored in memory

### Planning Modes

- **Quick**: Fast execution for simple tasks
- **Comprehensive**: Detailed analysis and planning
- **Exploratory**: Research and discovery focused
- **Maintenance**: Code maintenance and refactoring

### Risk Levels

- **Low**: Safe operations like reading files or simple code generation
- **Medium**: File modifications, running tests
- **High**: System commands, external API calls
- **Critical**: Destructive operations, security-sensitive changes

## Using the Web Interface

### Dashboard Overview

The main dashboard provides:

- **System Status**: Health of all components
- **Quick Task Execution**: Execute tasks with a simple form
- **Recent Tasks**: View and manage recent task executions
- **System Metrics**: Performance and usage statistics
- **Chat Interface**: Interactive conversation with the agent

### Task Execution

1. **Enter Task Description**
   - Use natural language to describe what you want
   - Be specific about requirements and constraints
   - Example: "Create a REST API endpoint for user authentication with JWT tokens"

2. **Configure Options**
   - **Preview**: See what the agent will do before execution
   - **Dry Run**: Test the plan without making changes
   - **Auto-approve**: Automatically approve low-risk tasks

3. **Monitor Progress**
   - Real-time updates on task execution
   - Step-by-step progress tracking
   - Error reporting and recovery

### Chat Interface

- **Ask Questions**: Get explanations about code, concepts, or best practices
- **Request Help**: Get assistance with debugging or implementation
- **Brainstorm**: Discuss architecture decisions and design patterns
- **Code Review**: Get feedback on your code

## Using the CLI

### Basic Commands

```bash
# Execute a task
python zorix_cli.py plan "Add error handling to the login function"

# Chat with the agent
python zorix_cli.py chat "Explain the difference between async and sync functions"

# Search for content
python zorix_cli.py search "authentication" --type code

# Check system status
python zorix_cli.py status
```

### Advanced Usage

```bash
# Preview a task without executing
python zorix_cli.py plan "Refactor the database connection code" --dry-run

# Auto-approve low-risk tasks
python zorix_cli.py plan "Fix typos in comments" --auto-approve

# Wait for task completion
python zorix_cli.py plan "Run the test suite" --wait

# Search with filters
python zorix_cli.py search "error handling" --type code --max-results 20
```

## Task Planning and Execution

### Writing Effective Task Instructions

**Good Examples:**
```
"Create a Python function to validate email addresses using regex"
"Add unit tests for the user authentication module with 90% coverage"
"Refactor the database connection code to use connection pooling"
"Fix the memory leak in the image processing pipeline"
```

**Tips for Better Instructions:**
- Be specific about requirements
- Mention target files or modules
- Specify testing requirements
- Include performance or quality criteria
- Mention any constraints or preferences

### Task Preview and Approval

Before execution, you can:

1. **Review the Plan**
   - See what files will be modified
   - Understand the execution steps
   - Check estimated time and complexity

2. **Assess Risks**
   - Review potential risks and side effects
   - Understand approval requirements
   - Consider impact on existing code

3. **Make Decisions**
   - Approve, reject, or modify the plan
   - Request modifications if needed

## Chat Interface

### Conversational AI

The chat interface provides natural language interaction with the agent:

**Question Types:**
- **Explanatory**: "How does async/await work in Python?"
- **Debugging**: "Why is my function returning None?"
- **Best Practices**: "What's the best way to handle database connections?"
- **Code Review**: "Can you review this function for potential issues?"

**Context Awareness:**
- Agent remembers conversation history
- Understands your current project context
- References previous tasks and decisions
- Maintains session continuity

## File Management

### Workspace Organization

The agent works within a designated workspace directory:

```
workspace/
├── projects/
│   ├── project-a/
│   └── project-b/
├── shared/
│   ├── templates/
│   └── utilities/
└── temp/
    └── scratch/
```

### File Operations

**Through Web Interface:**
- Browse directory structure
- View file contents with syntax highlighting
- Edit files with code completion
- Upload/download files
- Create/delete files and directories

**Through API:**
- Programmatic file access
- Batch operations
- File watching and notifications
- Version control integration

## Search and Discovery

### Semantic Search

The vector-based search system enables:

**Code Search:**
- Find functions by description
- Locate similar code patterns
- Search by functionality rather than exact text
- Cross-language code discovery

**Documentation Search:**
- Find relevant documentation sections
- Search across comments and docstrings
- Locate usage examples
- Find related concepts

### Search Types

1. **Exact Match**: Traditional text search
2. **Fuzzy Search**: Handles typos and variations
3. **Semantic Search**: Understands meaning and context
4. **Hybrid Search**: Combines multiple approaches

## Best Practices

### Writing Effective Instructions

**Do:**
```
✓ "Add input validation to the user registration function in auth.py"
✓ "Create unit tests for the payment processing module with edge cases"
✓ "Refactor the database query in get_user_orders() to improve performance"
```

**Don't:**
```
✗ "Fix the code"
✗ "Make it better"
✗ "Add some tests"
```

### Security Considerations

1. **Review High-Risk Tasks**
   - Always preview destructive operations
   - Verify file paths and commands
   - Check external API calls

2. **Protect Sensitive Data**
   - Avoid hardcoding credentials
   - Use environment variables
   - Review generated code for secrets

3. **Validate Outputs**
   - Test generated code thoroughly
   - Review security implications
   - Verify compliance requirements

## Troubleshooting

### Common Issues

**Task Execution Failures:**
```
Problem: Task fails with "Permission denied"
Solution: Check file permissions and workspace configuration

Problem: "Model not available" error
Solution: Verify AWS Bedrock access and model permissions

Problem: Task hangs or times out
Solution: Check system resources and network connectivity
```

**Chat Issues:**
```
Problem: Agent doesn't understand context
Solution: Provide more specific information and examples

Problem: Responses are too generic
Solution: Ask follow-up questions and request specific details
```

**Search Problems:**
```
Problem: No search results found
Solution: Try different keywords, check file indexing status

Problem: Irrelevant search results
Solution: Use more specific queries, apply filters
```

### Debugging Steps

1. **Check System Status**
   ```bash
   python zorix_cli.py status
   curl http://localhost:8000/api/v1/system/health
   ```

2. **Review Logs**
   ```bash
   tail -f logs/zorix-agent.log
   grep ERROR logs/zorix-agent.log
   ```

3. **Test Components**
   ```bash
   # Test Bedrock connection
   python -c "from agent.llm.bedrock_client import BedrockClient; client = BedrockClient(); print(client.test_connection())"
   
   # Test vector search
   python zorix_cli.py search "test query" --debug
   ```

### Getting Help

**Documentation:**
- API Documentation: `/docs`
- User Guide: This document
- Deployment Guide: `DEPLOYMENT.md`

**Support:**
- Check logs for error messages
- Review configuration settings
- Test individual components
- Consult troubleshooting section

This user guide provides comprehensive information for effectively using the Zorix Agent system. For technical details and API reference, see the API Documentation.