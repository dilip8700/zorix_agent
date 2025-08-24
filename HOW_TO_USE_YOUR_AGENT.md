# 🤖 How to Use Your Zorix Agent - Complete Guide

## 🚀 Starting Your Agent

### Option 1: Full Web Server (Recommended)
```bash
cd zorix-agent
python run_web.py
```
**Access at**: http://127.0.0.1:8000

### Option 2: Simple Server
```bash
python simple_start.py
```
**Access at**: http://127.0.0.1:8001

### Option 3: With AI Chat Interface
```bash
python start_with_ai.py
```
**Access at**: http://127.0.0.1:8002

## 🌐 Web Interface Usage

### 1. Chat Interface
**URL**: http://127.0.0.1:8000/static/index.html

**What you can ask:**
- **Code Generation**: "Create a Python function to calculate fibonacci numbers"
- **Code Review**: "Review this code for bugs and improvements"
- **Debugging Help**: "Why is my function returning None?"
- **Architecture Advice**: "How should I structure a REST API?"
- **Learning**: "Explain decorators in Python with examples"
- **Refactoring**: "Refactor this code to be more efficient"

### 2. API Documentation
**URL**: http://127.0.0.1:8000/docs

Explore all available endpoints and test them directly in the browser.

## 💻 Command Line Usage

### Basic Commands

#### Chat with AI
```bash
python zorix_cli.py chat "How do I create a REST API in Python?"
```

#### Plan a Task
```bash
python zorix_cli.py plan "Add error handling to my Python script"
```

#### Search Code
```bash
python zorix_cli.py search "function definition"
```

#### Check System Status
```bash
python zorix_cli.py status
```

#### Git Operations
```bash
python zorix_cli.py git status
python zorix_cli.py git diff
```

## 🔧 API Usage Examples

### 1. Chat with AI via API
```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a Python function to sort a list",
    "session_id": "my-session"
  }'
```

### 2. Plan and Execute Tasks
```bash
# Create a plan
curl -X POST http://127.0.0.1:8000/api/v1/agent/plan \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Create a hello world Python script",
    "mode": "edit"
  }'

# Execute the plan
curl -X POST http://127.0.0.1:8000/api/v1/agent/apply \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "your-plan-id",
    "auto_apply": true
  }'
```

### 3. Search Your Code
```bash
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "function definition",
    "top_k": 10
  }'
```

### 4. File Operations
```bash
# Read a file
curl -X GET "http://127.0.0.1:8000/api/v1/files/read?path=example.py"

# Write a file
curl -X POST http://127.0.0.1:8000/api/v1/files/write \
  -H "Content-Type: application/json" \
  -d '{
    "path": "hello.py",
    "content": "print(\"Hello, World!\")"
  }'
```

## 🎯 Practical Use Cases

### 1. Code Generation
**Ask**: "Create a Python class for a simple calculator"
**Result**: Get a complete class with methods for basic operations

### 2. Code Review
**Ask**: "Review this code and suggest improvements"
**Result**: Get detailed feedback on code quality, performance, and best practices

### 3. Debugging Help
**Ask**: "My function returns None instead of the expected value. Here's the code..."
**Result**: Get specific debugging advice and fixes

### 4. Learning and Explanation
**Ask**: "Explain how decorators work in Python with examples"
**Result**: Get comprehensive explanations with code examples

### 5. Refactoring
**Ask**: "Refactor this code to use modern Python features"
**Result**: Get improved, more efficient code

### 6. Architecture Advice
**Ask**: "How should I structure a microservices architecture?"
**Result**: Get detailed architectural guidance

## 🔍 Advanced Features

### 1. Streaming Responses
For real-time responses, use the streaming endpoints:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain async programming"}' \
  --no-buffer
```

### 2. Context-Aware Conversations
The agent remembers your conversation context:
```bash
# First message
"Create a Python function to read a file"

# Follow-up message
"Now add error handling to that function"
```

### 3. Multi-File Operations
```bash
"Refactor my Python project to use proper error handling across all files"
```

### 4. Git Integration
```bash
python zorix_cli.py git status
python zorix_cli.py git commit -m "Add new feature"
```

## 🛠️ Configuration

### Environment Variables
Create a `.env` file:
```bash
# AWS Configuration (for AI features)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
BEDROCK_REGION=us-east-1

# Server Configuration
APP_PORT=8000
WORKSPACE_ROOT=./workspace

# AI Configuration
MAX_TOKENS=4000
TEMPERATURE=0.2
```

### CLI Configuration
```bash
python zorix_cli.py config set api-url http://127.0.0.1:8000
python zorix_cli.py config set output-format rich
```

## 🚨 Troubleshooting

### Server Won't Start
1. **Check port availability**: Try different ports (8001, 8002)
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Check Python version**: Requires Python 3.11+

### AI Features Not Working
1. **Check AWS credentials** in `.env` file
2. **Test connection**: `python test_aws.py`
3. **Request Bedrock access** in AWS Console

### CLI Connection Issues
1. **Ensure server is running**: Check http://127.0.0.1:8000/docs
2. **Check API URL**: `python zorix_cli.py config show`
3. **Test health**: `curl http://127.0.0.1:8000/health`

## 📚 Example Workflows

### 1. Create a New Python Project
```bash
# Chat with agent
python zorix_cli.py chat "Create a Python project structure for a web API"

# Plan the implementation
python zorix_cli.py plan "Set up FastAPI project with user authentication"

# Apply the plan
python zorix_cli.py apply --confirm
```

### 2. Debug Existing Code
```bash
# Search for problematic code
python zorix_cli.py search "error handling"

# Get debugging help
python zorix_cli.py chat "My API returns 500 errors. Here's the code..."
```

### 3. Code Review Workflow
```bash
# Get git status
python zorix_cli.py git status

# Review changes
python zorix_cli.py chat "Review my recent changes for code quality"

# Commit with AI-generated message
python zorix_cli.py git commit --ai-message
```

## 🎉 You're Ready!

Your Zorix Agent is now a powerful AI coding assistant that can:

✅ **Generate code** from natural language  
✅ **Review and improve** existing code  
✅ **Debug issues** and suggest fixes  
✅ **Explain concepts** with examples  
✅ **Refactor code** for better quality  
✅ **Plan complex tasks** step by step  
✅ **Search your codebase** intelligently  
✅ **Handle git operations** safely  
✅ **Remember conversation context**  
✅ **Stream real-time responses**  

**Start with**: `python run_web.py` then visit http://127.0.0.1:8000/static/index.html

**Happy coding with your AI assistant!** 🚀