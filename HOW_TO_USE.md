# 🚀 How to Use Zorix Agent - Complete Guide

## Current Status
Your Zorix Agent server is running! Here's how to use it effectively.

## 🌐 Access Points

With your server running on port 8001, you can access:

- **🏠 Main Interface**: http://127.0.0.1:8001/
- **📚 API Documentation**: http://127.0.0.1:8001/docs
- **❤️ Health Check**: http://127.0.0.1:8001/health
- **📊 System Status**: http://127.0.0.1:8001/status

## 🔧 Fix AWS Credentials First

Your AWS credentials need to be corrected. Here's how:

### Option 1: Update .env file
```bash
# Edit your .env file with correct credentials
AWS_ACCESS_KEY_ID=your_correct_access_key
AWS_SECRET_ACCESS_KEY=your_correct_secret_key
```

### Option 2: Use AWS CLI
```bash
# Configure AWS CLI (recommended)
aws configure
```

### Option 3: Test with Mock Mode
For now, you can test the system without AWS by using mock responses.

## 🎯 How to Use Zorix Agent

### 1. Web Interface Usage

Visit http://127.0.0.1:8001/docs for interactive API testing:

#### Test Basic Endpoints:
```bash
# Health check
curl http://127.0.0.1:8001/health

# System status  
curl http://127.0.0.1:8001/status
```

#### Chat with the Agent:
```bash
curl -X POST http://127.0.0.1:8001/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, can you help me write a Python function?",
    "session_id": "test-session"
  }'
```

#### Execute a Task:
```bash
curl -X POST http://127.0.0.1:8001/api/v1/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Create a hello world Python script",
    "dry_run": true
  }'
```

### 2. Command Line Usage

Once AWS is working, you can use the CLI:

```bash
# Check system status
python zorix_cli.py status

# Chat with the agent
python zorix_cli.py chat "How do I create a REST API?"

# Execute a task
python zorix_cli.py plan "Add error handling to my Python script"

# Search code
python zorix_cli.py search "function definition"
```

### 3. Web Browser Usage

1. **Open**: http://127.0.0.1:8001/docs
2. **Try the endpoints** using the interactive interface
3. **Test chat functionality** with the `/api/v1/chat/message` endpoint
4. **Execute tasks** with the `/api/v1/tasks/execute` endpoint

## 🛠️ What You Can Do Right Now

### Without AWS (Basic Mode):
- ✅ Test API endpoints
- ✅ Check system health
- ✅ Explore API documentation
- ✅ Test file operations
- ✅ Basic system monitoring

### With AWS (Full Mode):
- 🤖 AI-powered chat
- 📝 Code generation
- 🔍 Intelligent code search
- 📋 Task planning and execution
- 🧠 Memory and context management

## 📋 Example Usage Scenarios

### Scenario 1: Code Generation
```bash
curl -X POST http://127.0.0.1:8001/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a Python function to calculate fibonacci numbers with memoization"
  }'
```

### Scenario 2: Code Review
```bash
curl -X POST http://127.0.0.1:8001/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Review this code for potential issues: def divide(a, b): return a/b"
  }'
```

### Scenario 3: Task Execution
```bash
curl -X POST http://127.0.0.1:8001/api/v1/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Create a simple web server using FastAPI",
    "generate_preview": true,
    "dry_run": true
  }'
```

## 🔍 Testing Your Setup

### 1. Test Basic Functionality
```bash
# Test health
curl http://127.0.0.1:8001/health

# Should return: {"status": "healthy", ...}
```

### 2. Test API Documentation
- Visit: http://127.0.0.1:8001/docs
- Try the "GET /health" endpoint
- Explore other available endpoints

### 3. Test Chat (when AWS is fixed)
```bash
curl -X POST http://127.0.0.1:8001/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, test message"}'
```

## 🚨 Troubleshooting

### AWS Credentials Issues:
1. **Check your AWS console** for correct credentials
2. **Verify region** (us-east-1 is recommended)
3. **Request Bedrock access** in AWS console
4. **Test with AWS CLI**: `aws sts get-caller-identity`

### Server Issues:
1. **Port conflicts**: Try different port in the startup script
2. **Dependencies**: Run `pip install fastapi uvicorn boto3`
3. **Permissions**: Check file/folder permissions

### API Issues:
1. **Check server logs** in the terminal
2. **Verify endpoints** at http://127.0.0.1:8001/docs
3. **Test with curl** commands above

## 🎯 Next Steps

1. **Fix AWS credentials** to unlock AI features
2. **Create a workspace folder** with your code
3. **Test chat functionality** for code assistance
4. **Try task execution** for automated coding
5. **Explore the web interface** for easier interaction

## 💡 Pro Tips

- **Use the /docs endpoint** for interactive API testing
- **Start with simple chat messages** to test AI functionality
- **Use dry_run: true** for safe task testing
- **Check logs** in the terminal for debugging
- **Save your chat sessions** for context continuity

---

**🎉 You're ready to use Zorix Agent!** Start with the basic endpoints, fix your AWS credentials, and then explore the full AI-powered features.