#!/bin/bash

# Zorix Agent Kubernetes Deployment Script

set -e

# Configuration
NAMESPACE="zorix-agent"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-}"
CONTEXT="${CONTEXT:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check kubectl connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Build and push Docker image
build_and_push_image() {
    if [ -n "$REGISTRY" ]; then
        log_info "Building and pushing Docker image..."
        
        IMAGE_NAME="${REGISTRY}/zorix-agent:${IMAGE_TAG}"
        
        # Build image
        docker build -f docker/Dockerfile -t "$IMAGE_NAME" .
        
        # Push image
        docker push "$IMAGE_NAME"
        
        log_info "Image pushed: $IMAGE_NAME"
        
        # Update deployment with new image
        sed -i.bak "s|image: zorix-agent:latest|image: $IMAGE_NAME|g" k8s/deployment.yaml
    else
        log_warn "No registry specified, using local image"
    fi
}

# Create namespace
create_namespace() {
    log_info "Creating namespace..."
    kubectl apply -f k8s/namespace.yaml
}

# Deploy secrets
deploy_secrets() {
    log_info "Deploying secrets..."
    
    # Check if secrets are properly configured
    if grep -q "cGxhY2Vob2xkZXI=" k8s/secret.yaml; then
        log_warn "Secrets contain placeholder values!"
        log_warn "Please update k8s/secret.yaml with actual base64-encoded credentials"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    kubectl apply -f k8s/secret.yaml
}

# Deploy configuration
deploy_config() {
    log_info "Deploying configuration..."
    kubectl apply -f k8s/configmap.yaml
}

# Deploy storage
deploy_storage() {
    log_info "Deploying persistent volumes..."
    kubectl apply -f k8s/pvc.yaml
    
    # Wait for PVCs to be bound
    log_info "Waiting for PVCs to be bound..."
    kubectl wait --for=condition=Bound pvc/zorix-agent-data-pvc -n $NAMESPACE --timeout=300s
    kubectl wait --for=condition=Bound pvc/zorix-agent-logs-pvc -n $NAMESPACE --timeout=300s
    kubectl wait --for=condition=Bound pvc/zorix-agent-workspace-pvc -n $NAMESPACE --timeout=300s
}

# Deploy application
deploy_app() {
    log_info "Deploying application..."
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml
}

# Wait for deployment
wait_for_deployment() {
    log_info "Waiting for deployment to be ready..."
    kubectl wait --for=condition=available --timeout=600s deployment/zorix-agent -n $NAMESPACE
    
    # Check pod status
    kubectl get pods -n $NAMESPACE
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check if pods are running
    RUNNING_PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}')
    if [ -z "$RUNNING_PODS" ]; then
        log_error "No pods are running"
        kubectl describe pods -n $NAMESPACE
        exit 1
    fi
    
    # Test health endpoint
    log_info "Testing health endpoint..."
    kubectl port-forward svc/zorix-agent-service 8080:8000 -n $NAMESPACE &
    PORT_FORWARD_PID=$!
    
    sleep 5
    
    if curl -f http://localhost:8080/api/v1/system/health &> /dev/null; then
        log_info "Health check passed"
    else
        log_error "Health check failed"
        kill $PORT_FORWARD_PID 2>/dev/null || true
        exit 1
    fi
    
    kill $PORT_FORWARD_PID 2>/dev/null || true
    
    log_info "Deployment verification completed successfully"
}

# Show deployment info
show_info() {
    log_info "Deployment completed successfully!"
    echo
    echo "Namespace: $NAMESPACE"
    echo "Services:"
    kubectl get svc -n $NAMESPACE
    echo
    echo "Pods:"
    kubectl get pods -n $NAMESPACE
    echo
    echo "To access the application:"
    echo "  kubectl port-forward svc/zorix-agent-service 8000:8000 -n $NAMESPACE"
    echo "  Then visit: http://localhost:8000"
    echo
    echo "To view logs:"
    echo "  kubectl logs -f deployment/zorix-agent -n $NAMESPACE"
    echo
    echo "To delete the deployment:"
    echo "  kubectl delete namespace $NAMESPACE"
}

# Cleanup function
cleanup() {
    if [ -f k8s/deployment.yaml.bak ]; then
        mv k8s/deployment.yaml.bak k8s/deployment.yaml
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Main deployment flow
main() {
    log_info "Starting Zorix Agent Kubernetes deployment..."
    
    # Set kubectl context if specified
    if [ -n "$CONTEXT" ]; then
        log_info "Switching to kubectl context: $CONTEXT"
        kubectl config use-context "$CONTEXT"
    fi
    
    check_prerequisites
    build_and_push_image
    create_namespace
    deploy_secrets
    deploy_config
    deploy_storage
    deploy_app
    wait_for_deployment
    verify_deployment
    show_info
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "delete")
        log_info "Deleting Zorix Agent deployment..."
        kubectl delete namespace $NAMESPACE
        log_info "Deployment deleted"
        ;;
    "status")
        log_info "Checking deployment status..."
        kubectl get all -n $NAMESPACE
        ;;
    "logs")
        kubectl logs -f deployment/zorix-agent -n $NAMESPACE
        ;;
    "help")
        echo "Usage: $0 [deploy|delete|status|logs|help]"
        echo
        echo "Commands:"
        echo "  deploy  - Deploy Zorix Agent to Kubernetes (default)"
        echo "  delete  - Delete the deployment"
        echo "  status  - Show deployment status"
        echo "  logs    - Show application logs"
        echo "  help    - Show this help message"
        echo
        echo "Environment variables:"
        echo "  IMAGE_TAG - Docker image tag (default: latest)"
        echo "  REGISTRY  - Docker registry URL"
        echo "  CONTEXT   - Kubernetes context to use"
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac