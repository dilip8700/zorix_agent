# Zorix Agent Deployment Guide

This guide covers various deployment options for the Zorix Agent system.

## Prerequisites

### System Requirements
- Python 3.11+
- 4GB+ RAM
- 10GB+ disk space
- AWS credentials with Bedrock access

### AWS Setup
1. **Enable AWS Bedrock**: Ensure Bedrock is available in your region
2. **Model Access**: Request access to required models:
   - `anthropic.claude-3-sonnet-20240229-v1:0` (or similar)
   - `amazon.titan-embed-text-v2:0`
3. **IAM Permissions**: Create IAM user/role with Bedrock permissions

## Local Development

### 1. Clone and Setup
```bash
git clone <repository-url>
cd zorix-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your settings
```

Required environment variables:
```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
ZORIX_BEDROCK_REGION=us-east-1
ZORIX_WORKSPACE_ROOT=./workspace
```

### 3. Run Development Server
```bash
# Start the web API
python run_web.py

# Or use the CLI
python zorix_cli.py --help
```

## Docker Deployment

### 1. Build Image
```bash
cd zorix-agent
docker build -f docker/Dockerfile -t zorix-agent:latest .
```

### 2. Run with Docker Compose
```bash
cd docker

# Edit docker-compose.yml with your AWS credentials
# Then start the services
docker-compose up -d
```

### 3. Verify Deployment
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f zorix-agent

# Test API
curl http://localhost:8000/api/v1/system/health
```

## Kubernetes Deployment

### 1. Prerequisites
- Kubernetes cluster (1.20+)
- kubectl configured
- Docker image built and pushed to registry

### 2. Update Configuration
```bash
# Edit k8s/secret.yaml with base64-encoded credentials
echo -n "your-access-key" | base64
echo -n "your-secret-key" | base64

# Update k8s/configmap.yaml with your settings
```

### 3. Deploy to Kubernetes
```bash
# Apply all configurations
kubectl apply -f k8s/

# Or apply individually
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 4. Verify Deployment
```bash
# Check pods
kubectl get pods -n zorix-agent

# Check services
kubectl get svc -n zorix-agent

# View logs
kubectl logs -f deployment/zorix-agent -n zorix-agent

# Port forward for testing
kubectl port-forward svc/zorix-agent-service 8000:8000 -n zorix-agent
```

## Production Considerations

### Security
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Enable HTTPS/TLS
- Configure proper firewall rules
- Use non-root containers
- Regular security updates

### Monitoring
- Enable metrics collection
- Set up log aggregation
- Configure health checks
- Monitor resource usage

### High Availability
- Multiple replicas
- Load balancing
- Database clustering
- Backup strategies

### Performance
- Resource limits and requests
- Horizontal pod autoscaling
- Connection pooling
- Caching strategies

## Troubleshooting

### Common Issues

1. **AWS Credentials**
   ```bash
   # Check credentials
   kubectl exec -n zorix-agent deployment/zorix-agent -- \
     aws sts get-caller-identity
   ```

2. **Bedrock Access**
   ```bash
   # Test Bedrock access
   kubectl exec -n zorix-agent deployment/zorix-agent -- \
     aws bedrock list-foundation-models --region us-east-1
   ```

3. **Storage Issues**
   ```bash
   # Check PVC status
   kubectl get pvc -n zorix-agent
   
   # Check disk usage
   kubectl exec -n zorix-agent deployment/zorix-agent -- df -h
   ```

### Log Analysis
```bash
# View application logs
kubectl logs -f deployment/zorix-agent -n zorix-agent

# Get recent events
kubectl get events -n zorix-agent --sort-by='.lastTimestamp'
```

### Health Checks
```bash
# Check health endpoint
curl http://localhost:8000/api/v1/system/health

# Check system status
curl http://localhost:8000/api/v1/system/status
```