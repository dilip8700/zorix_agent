# Zorix Agent API Documentation

Comprehensive API documentation for the Zorix Agent system.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API does not require authentication. In production, implement appropriate authentication mechanisms.

## Response Format

All API responses follow a consistent JSON format:

```json
{
  "status": "success|error",
  "data": {},
  "message": "Human readable message",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Error Handling

HTTP status codes:
- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

Error response format:
```json
{
  "error": "ErrorType",
  "message": "Error description",
  "details": {
    "field": "Additional error details"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## API Endpoints

### System Management

#### Health Check
```http
GET /api/v1/system/health
```

Returns system health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "services": {
    "bedrock": "healthy",
    "vector_index": "healthy",
    "memory": "healthy"
  },
  "version": "1.0.0"
}
```

#### System Status
```http
GET /api/v1/system/status
```

Returns detailed system status.

**Response:**
```json
{
  "status": "running",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "active_tasks": 2,
  "total_tasks_completed": 150,
  "memory_usage_mb": 512.5,
  "workspace_path": "/app/workspace",
  "bedrock_status": "healthy",
  "vector_index_status": "healthy"
}
```

### Task Management

#### Execute Task
```http
POST /api/v1/tasks/execute
```

Execute a task from natural language instruction.

**Request Body:**
```json
{
  "instruction": "Create a Python function to calculate fibonacci numbers",
  "context": {
    "project_id": "proj-123",
    "target_files": ["math_utils.py"]
  },
  "planning_mode": "comprehensive",
  "generate_preview": true,
  "dry_run": false,
  "auto_approve": false
}
```

**Response:**
```json
{
  "task_id": "task-abc123",
  "status": "started",
  "message": "Task created successfully",
  "requires_approval": false,
  "preview_url": "/api/v1/tasks/task-abc123/preview"
}
```

#### Task Status
```http
GET /api/v1/tasks/{task_id}/status
```

Get task execution status.

**Response:**
```json
{
  "task_id": "task-abc123",
  "instruction": "Create a Python function to calculate fibonacci numbers",
  "status": "executing",
  "progress": {
    "current_step": "Writing code",
    "completed_steps": 2,
    "total_steps": 5,
    "percentage": 40
  },
  "created_at": "2024-01-01T12:00:00Z",
  "started_at": "2024-01-01T12:00:05Z",
  "completed_at": null,
  "error_message": null
}
```

### Chat Interface

#### Send Message
```http
POST /api/v1/chat/message
```

Send a message to the agent.

**Request Body:**
```json
{
  "message": "How do I implement a binary search algorithm?",
  "session_id": "session-123",
  "context": {
    "project_id": "proj-456"
  },
  "stream": false
}
```

**Response:**
```json
{
  "message": "A binary search algorithm works by repeatedly dividing the search space in half...",
  "session_id": "session-123",
  "message_id": "msg-789",
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {
    "model_used": "claude-3-sonnet",
    "tokens_used": 150
  }
}
```

#### Stream Chat
```http
POST /api/v1/chat/stream
```

Stream chat response using Server-Sent Events.

**Request Body:**
```json
{
  "message": "Explain async/await in Python",
  "session_id": "session-123",
  "stream": true
}
```

### File Management

#### List Directory
```http
GET /api/v1/files/list
```

List directory contents.

**Query Parameters:**
- `path`: Directory path (default: workspace root)

**Response:**
```json
{
  "path": "src",
  "files": [
    {
      "path": "src/main.py",
      "size": 1024,
      "modified": "2024-01-01T12:00:00Z",
      "is_directory": false,
      "permissions": "644"
    }
  ],
  "directories": [
    {
      "path": "src/utils",
      "size": 0,
      "modified": "2024-01-01T11:00:00Z",
      "is_directory": true,
      "permissions": "755"
    }
  ],
  "total_files": 1,
  "total_directories": 1
}
```

#### Get File Content
```http
GET /api/v1/files/content
```

Get file content.

**Query Parameters:**
- `path`: File path
- `encoding`: File encoding (default: utf-8)

**Response:**
```json
{
  "path": "src/main.py",
  "content": "def main():\n    print('Hello, World!')\n",
  "encoding": "utf-8",
  "size": 35,
  "modified": "2024-01-01T12:00:00Z"
}
```

### Search

#### Search Content
```http
POST /api/v1/search/
```

Search across code, memory, and files.

**Request Body:**
```json
{
  "query": "authentication function",
  "search_type": "all",
  "max_results": 10,
  "project_id": "proj-123",
  "file_patterns": ["*.py", "*.js"]
}
```

**Response:**
```json
{
  "query": "authentication function",
  "results": [
    {
      "type": "code",
      "title": "auth.py",
      "content": "def authenticate_user(username, password):",
      "path": "src/auth.py",
      "score": 0.95,
      "metadata": {
        "line_number": 15,
        "function_name": "authenticate_user",
        "language": "python"
      }
    }
  ],
  "total_results": 1,
  "search_time_ms": 45.2
}
```

## SDK Examples

### Python
```python
import httpx

class ZorixClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.client = httpx.AsyncClient(base_url=base_url)
    
    async def execute_task(self, instruction, **kwargs):
        response = await self.client.post(
            "/api/v1/tasks/execute",
            json={"instruction": instruction, **kwargs}
        )
        return response.json()
    
    async def chat(self, message, session_id=None):
        response = await self.client.post(
            "/api/v1/chat/message",
            json={"message": message, "session_id": session_id}
        )
        return response.json()

# Usage
client = ZorixClient()
result = await client.execute_task("Create a hello world function")
response = await client.chat("How does this work?")
```

### JavaScript
```javascript
class ZorixClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async executeTask(instruction, options = {}) {
    const response = await fetch(`${this.baseUrl}/api/v1/tasks/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction, ...options })
    });
    return response.json();
  }

  async chat(message, sessionId = null) {
    const response = await fetch(`${this.baseUrl}/api/v1/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId })
    });
    return response.json();
  }
}

// Usage
const client = new ZorixClient();
const result = await client.executeTask('Create a hello world function');
const response = await client.chat('How does this work?');
```

### cURL Examples

```bash
# Execute a task
curl -X POST http://localhost:8000/api/v1/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Create a hello world function", "dry_run": true}'

# Chat with agent
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain recursion in Python"}'

# Search content
curl -X POST http://localhost:8000/api/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "fibonacci function", "search_type": "code"}'

# Get system status
curl http://localhost:8000/api/v1/system/status
```

## OpenAPI Specification

The complete OpenAPI specification is available at:
```
http://localhost:8000/docs
```

Alternative documentation:
```
http://localhost:8000/redoc
```

Download OpenAPI JSON:
```
http://localhost:8000/openapi.json
```