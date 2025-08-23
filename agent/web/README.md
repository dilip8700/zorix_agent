# Zorix Agent Web Interface

A comprehensive web interface and REST API for the Zorix Agent system.

## Features

### REST API
- **Task Management**: Execute, monitor, and manage agent tasks
- **Chat Interface**: Interactive chat with the agent
- **File Operations**: Browse, edit, and manage workspace files
- **Project Management**: Organize work into projects
- **Search**: Search across code, memory, and files
- **System Monitoring**: Health checks, metrics, and configuration

### Web Interface
- **Dashboard**: System status and metrics overview
- **Task Execution**: Quick task execution with preview
- **Chat**: Real-time chat with the agent
- **File Browser**: Navigate and edit workspace files
- **Search**: Unified search across all content

## Quick Start

1. **Start the web server**:
   ```bash
   python run_web.py
   ```

2. **Access the interface**:
   - Web Interface: http://127.0.0.1:8000/static/index.html
   - API Documentation: http://127.0.0.1:8000/docs
   - Health Check: http://127.0.0.1:8000/api/v1/system/health

## API Endpoints

### System Management
- `GET /api/v1/system/health` - Health check
- `GET /api/v1/system/status` - Detailed system status
- `GET /api/v1/system/config` - Get configuration
- `POST /api/v1/system/config` - Update configuration
- `GET /api/v1/system/metrics` - System metrics

### Task Management
- `POST /api/v1/tasks/execute` - Execute a task
- `GET /api/v1/tasks/{task_id}/status` - Get task status
- `GET /api/v1/tasks/{task_id}/preview` - Get task preview
- `POST /api/v1/tasks/{task_id}/approve` - Approve/reject task
- `GET /api/v1/tasks/{task_id}/stream` - Stream task events
- `GET /api/v1/tasks/` - List tasks
- `DELETE /api/v1/tasks/{task_id}` - Cancel task

### Chat Interface
- `POST /api/v1/chat/message` - Send chat message
- `POST /api/v1/chat/stream` - Stream chat response
- `GET /api/v1/chat/sessions` - List chat sessions
- `GET /api/v1/chat/sessions/{session_id}` - Get session messages
- `DELETE /api/v1/chat/sessions/{session_id}` - Delete session

### File Management
- `GET /api/v1/files/list` - List directory contents
- `GET /api/v1/files/content` - Get file content
- `POST /api/v1/files/content` - Write file content
- `POST /api/v1/files/upload` - Upload file
- `GET /api/v1/files/download` - Download file
- `DELETE /api/v1/files/` - Delete file/directory
- `POST /api/v1/files/mkdir` - Create directory
- `POST /api/v1/files/move` - Move/rename file
- `POST /api/v1/files/copy` - Copy file

### Project Management
- `GET /api/v1/projects/` - List projects
- `POST /api/v1/projects/` - Create project
- `GET /api/v1/projects/{project_id}` - Get project details
- `PUT /api/v1/projects/{project_id}` - Update project
- `DELETE /api/v1/projects/{project_id}` - Delete project
- `POST /api/v1/projects/{project_id}/activate` - Activate project
- `GET /api/v1/projects/{project_id}/memories` - Get project memories
- `POST /api/v1/projects/{project_id}/index` - Index project files

### Search
- `POST /api/v1/search/` - Perform search
- `GET /api/v1/search/suggestions` - Get search suggestions
- `GET /api/v1/search/recent` - Get recent searches
- `POST /api/v1/search/index` - Reindex workspace
- `GET /api/v1/search/index/status` - Get index status
- `DELETE /api/v1/search/index` - Clear index

## Configuration

The web interface uses the same configuration as the main agent system. Key settings:

- `WORKSPACE_ROOT`: Root directory for file operations
- `BEDROCK_REGION`: AWS Bedrock region
- `BEDROCK_MODEL_ID`: Model to use for chat and tasks
- `VECTOR_INDEX_PATH`: Path to vector index storage
- `MEMORY_DB_PATH`: Path to memory database

## Security

- **Path Validation**: All file operations are validated against the workspace root
- **CORS**: Configurable CORS settings for web interface
- **Rate Limiting**: Built-in request rate limiting
- **Input Validation**: Comprehensive input validation using Pydantic

## Development

### Adding New Endpoints

1. Create route handler in `agent/web/routes/`
2. Add Pydantic models in `agent/web/models.py`
3. Register router in `agent/web/api.py`

### Extending the Web Interface

The web interface is a single-page application using vanilla JavaScript. Key files:

- `agent/web/static/index.html` - Main interface
- `agent/web/static/` - Static assets (CSS, JS, images)

### Testing

```bash
# Run API tests
pytest tests/test_web_api.py

# Test specific endpoints
curl http://127.0.0.1:8000/api/v1/system/health
```

## Architecture

The web interface is built using:

- **FastAPI**: Modern, fast web framework
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server
- **Vanilla JavaScript**: Simple, dependency-free frontend

The API provides a complete interface to all agent capabilities while maintaining security and performance.