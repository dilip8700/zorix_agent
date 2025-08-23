# Zorix Agent

An AI-powered development agent that helps with code generation, task planning, and project management using AWS Bedrock.

## 🚀 Features

- **🧠 Intelligent Task Planning**: Natural language task planning with comprehensive execution strategies
- **💻 Code Generation**: AI-powered code generation with deep context awareness
- **🧠 Memory System**: Persistent memory for conversations and project context
- **🔍 Vector Search**: Semantic search across code and documentation
- **🌐 Web Interface**: Modern web UI for task management and interactive chat
- **⌨️ CLI Interface**: Powerful command-line interface for automation and scripting
- **🔒 Security**: Sandboxed execution environment with configurable permissions
- **📊 Observability**: Comprehensive logging, metrics, and tracing
- **🐳 Container Ready**: Docker and Kubernetes deployment configurations

## 🏃‍♂️ Quick Start

### Prerequisites
- Python 3.11+
- AWS account with Bedrock access
- AWS credentials configured

### Automated Setup
```bash
git clone <repository-url>
cd zorix-agent
chmod +x scripts/setup-dev.sh
./scripts/setup-dev.sh
```

### Manual Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your AWS credentials

# 3. Create directories
mkdir -p data logs workspace

# 4. Start the system
python run_web.py
```

### First Steps
```bash
# Check system status
python zorix_cli.py status

# Try a simple task
python zorix_cli.py plan "Create a hello world Python script"

# Start a chat
python zorix_cli.py chat "How do I use this system?"
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [User Guide](USER_GUIDE.md) | Comprehensive user documentation and tutorials |
| [API Documentation](API_DOCUMENTATION.md) | Complete REST API reference with examples |
| [Deployment Guide](DEPLOYMENT.md) | Production deployment instructions for Docker/K8s |
| [CLI Guide](CLI_README.md) | Command-line interface documentation |

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Interface │    │   CLI Interface │    │   REST API      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │     Agent Orchestrator    │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼────────┐    ┌───────────▼──────────┐    ┌────────▼────────┐
│ Planning System│    │   Execution Engine   │    │  Memory System  │
└────────────────┘    └──────────────────────┘    └─────────────────┘
        │                         │                         │
        │              ┌──────────▼──────────┐              │
        │              │    Tool System      │              │
        │              │ ┌─────────────────┐ │              │
        │              │ │ Filesystem Tools│ │              │
        │              │ │ Command Tools   │ │              │
        │              │ │ Git Tools       │ │              │
        │              │ └─────────────────┘ │              │
        │              └─────────────────────┘              │
        │                                                   │
┌───────▼────────┐                                ┌─────────▼───────┐
│ Vector Search  │                                │ Conversation    │
│ & Code Index   │                                │ Management      │
└────────────────┘                                └─────────────────┘
        │                                                   │
        └─────────────────────┬─────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   AWS Bedrock     │
                    │   LLM Integration │
                    └───────────────────┘
```

### Core Components

- **🎯 Agent Orchestrator**: Main coordination and task management
- **📋 Planning System**: Intelligent task analysis and planning
- **⚡ Execution Engine**: Safe and monitored task execution
- **🧠 Memory System**: Persistent context and conversation storage
- **🔍 Vector Search**: Semantic code and documentation search
- **🛠️ Tool System**: Extensible tool framework for various operations
- **🔗 LLM Integration**: AWS Bedrock client for AI capabilities
- **🔒 Security Layer**: Sandboxed execution with permission controls

## 🚀 Deployment Options

### Development
```bash
# Quick development setup
./scripts/setup-dev.sh
python run_web.py
```

### Docker
```bash
# Build and run with Docker Compose
cd docker
docker-compose up -d
```

### Kubernetes
```bash
# Deploy to Kubernetes
./scripts/deploy-k8s.sh
```

### Production
See [Deployment Guide](DEPLOYMENT.md) for comprehensive production deployment instructions.

## 🎯 Usage Examples

### Web Interface
Visit `http://localhost:8000/static/index.html` for the interactive web interface.

### CLI Examples
```bash
# Execute a development task
python zorix_cli.py plan "Add input validation to the user registration function"

# Interactive chat
python zorix_cli.py chat "Explain the difference between async and sync in Python"

# Search codebase
python zorix_cli.py search "authentication" --type code

# System status
python zorix_cli.py status
```

### API Examples
```bash
# Execute a task via API
curl -X POST http://localhost:8000/api/v1/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Create a hello world function", "dry_run": true}'

# Chat with the agent
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I implement error handling?"}'
```

## 🔧 Configuration

### Environment Variables
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
ZORIX_BEDROCK_REGION=us-east-1

# Application Configuration
ZORIX_WORKSPACE_ROOT=./workspace
ZORIX_LOG_LEVEL=INFO
ZORIX_LOG_FORMAT=json

# Database Configuration
ZORIX_MEMORY_DB_PATH=./data/memory.db
ZORIX_VECTOR_INDEX_PATH=./data/vector_index
```

See `.env.example` for complete configuration options.

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_planning.py -v
python -m pytest tests/test_memory_system.py -v

# Run integration tests
python test_basic.py
python test_bedrock_integration.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📊 Monitoring and Observability

The system includes comprehensive observability features:

- **📈 Metrics**: System and application metrics collection
- **📝 Logging**: Structured logging with configurable levels
- **🔍 Tracing**: Distributed tracing for request flows
- **🏥 Health Checks**: Built-in health monitoring endpoints

Access metrics and monitoring:
- Health: `http://localhost:8000/api/v1/system/health`
- Status: `http://localhost:8000/api/v1/system/status`
- Metrics: `http://localhost:8000/api/v1/system/metrics`

## 🔒 Security

- **Sandboxed Execution**: All code execution happens in controlled environments
- **Permission Controls**: Configurable file and command permissions
- **Input Validation**: Comprehensive input sanitization
- **Audit Logging**: Complete audit trail of all operations
- **Secrets Management**: Secure handling of credentials and sensitive data

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the comprehensive guides in the documentation files
- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Join community discussions for questions and tips

## 🙏 Acknowledgments

- AWS Bedrock for providing the AI foundation models
- FastAPI for the excellent web framework
- The open-source community for the amazing tools and libraries

---

**Ready to supercharge your development workflow with AI?** 🚀

Get started with Zorix Agent today and experience the future of AI-assisted development!