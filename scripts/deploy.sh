#!/bin/bash

# Zorix Agent Deployment Script
# This script handles deployment of the Zorix Agent system

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env.prod"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Zorix Agent Deployment Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    dev         Start development environment
    prod        Deploy production environment
    stop        Stop all services
    restart     Restart all services
    logs        Show logs
    status      Show service status
    backup      Create backup
    restore     Restore from backup
    update      Update services
    clean       Clean up resources
    help        Show this help message

Options:
    --env-file  Specify environment file (default: .env.prod)
    --no-build  Skip building images
    --force     Force operation without confirmation
    --verbose   Enable verbose output

Examples:
    $0 dev                          # Start development environment
    $0 prod --env-file .env.staging # Deploy to staging
    $0 logs zorix-agent             # Show logs for specific service
    $0 backup --force               # Create backup without confirmation
EOF
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Load environment variables
load_env() {
    if [[ -f "$ENV_FILE" ]]; then
        log_info "Loading environment from $ENV_FILE"
        set -a
        source "$ENV_FILE"
        set +a
    else
        log_warning "Environment file $ENV_FILE not found"
        if [[ "$1" == "prod" ]]; then
            log_error "Production deployment requires environment file"
            exit 1
        fi
    fi
}

# Generate environment file template
generate_env_template() {
    local env_file="$1"
    log_info "Generating environment template: $env_file"
    
    cat > "$env_file" << EOF
# Zorix Agent Production Environment Configuration

# Database Configuration
POSTGRES_PASSWORD=your_secure_postgres_password
REDIS_PASSWORD=your_secure_redis_password
GRAFANA_PASSWORD=your_secure_grafana_password
GRAFANA_SECRET_KEY=your_secure_grafana_secret_key
GRAFANA_DB_PASSWORD=your_secure_grafana_db_password

# AWS Configuration
BEDROCK_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# Application Configuration
LOG_LEVEL=INFO
ENABLE_TRACING=true
OTLP_ENDPOINT=http://jaeger:14268/api/traces

# Security Configuration
JWT_SECRET_KEY=your_jwt_secret_key
ENCRYPTION_KEY=your_encryption_key

# External Services
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_smtp_user
SMTP_PASSWORD=your_smtp_password

# Monitoring
SENTRY_DSN=your_sentry_dsn
EOF
    
    log_success "Environment template generated: $env_file"
    log_warning "Please edit the file and set appropriate values before deployment"
}

# Start development environment
start_dev() {
    log_info "Starting development environment..."
    
    cd "$PROJECT_DIR"
    
    # Build and start services
    if [[ "$NO_BUILD" != "true" ]]; then
        docker-compose build
    fi
    
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Check health
    check_health "dev"
    
    log_success "Development environment started"
    log_info "API available at: http://localhost:8000"
    log_info "Web interface at: http://localhost:8000/static/index.html"
    log_info "API docs at: http://localhost:8000/docs"
}

# Deploy production environment
deploy_prod() {
    log_info "Deploying production environment..."
    
    cd "$PROJECT_DIR"
    
    # Check if environment file exists
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Production environment file not found: $ENV_FILE"
        log_info "Generating template..."
        generate_env_template "$ENV_FILE"
        exit 1
    fi
    
    # Confirmation
    if [[ "$FORCE" != "true" ]]; then
        echo -n "Deploy to production? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled"
            exit 0
        fi
    fi
    
    # Build and deploy
    if [[ "$NO_BUILD" != "true" ]]; then
        docker-compose -f docker-compose.prod.yml build
    fi
    
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check health
    check_health "prod"
    
    log_success "Production environment deployed"
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    
    cd "$PROJECT_DIR"
    
    if [[ -f "docker-compose.prod.yml" ]] && docker-compose -f docker-compose.prod.yml ps -q &> /dev/null; then
        docker-compose -f docker-compose.prod.yml down
    fi
    
    if docker-compose ps -q &> /dev/null; then
        docker-compose down
    fi
    
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    stop_services
    sleep 5
    
    if [[ -f "$ENV_FILE" ]]; then
        deploy_prod
    else
        start_dev
    fi
}

# Show logs
show_logs() {
    local service="$1"
    cd "$PROJECT_DIR"
    
    if [[ -n "$service" ]]; then
        log_info "Showing logs for service: $service"
        if [[ -f "docker-compose.prod.yml" ]] && docker-compose -f docker-compose.prod.yml ps -q "$service" &> /dev/null; then
            docker-compose -f docker-compose.prod.yml logs -f "$service"
        else
            docker-compose logs -f "$service"
        fi
    else
        log_info "Showing logs for all services"
        if [[ -f "docker-compose.prod.yml" ]] && docker-compose -f docker-compose.prod.yml ps -q &> /dev/null; then
            docker-compose -f docker-compose.prod.yml logs -f
        else
            docker-compose logs -f
        fi
    fi
}

# Show service status
show_status() {
    log_info "Service status:"
    cd "$PROJECT_DIR"
    
    if [[ -f "docker-compose.prod.yml" ]] && docker-compose -f docker-compose.prod.yml ps -q &> /dev/null; then
        docker-compose -f docker-compose.prod.yml ps
    else
        docker-compose ps
    fi
}

# Check health
check_health() {
    local env="$1"
    local max_attempts=30
    local attempt=1
    
    log_info "Checking service health..."
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8000/api/v1/system/health > /dev/null; then
            log_success "Services are healthy"
            return 0
        fi
        
        log_info "Attempt $attempt/$max_attempts - waiting for services..."
        sleep 10
        ((attempt++))
    done
    
    log_error "Services failed to become healthy"
    return 1
}

# Create backup
create_backup() {
    local backup_dir="$PROJECT_DIR/backups/$(date +%Y%m%d_%H%M%S)"
    
    log_info "Creating backup in: $backup_dir"
    mkdir -p "$backup_dir"
    
    cd "$PROJECT_DIR"
    
    # Backup database
    if docker-compose ps postgres | grep -q "Up"; then
        log_info "Backing up PostgreSQL database..."
        docker-compose exec -T postgres pg_dump -U zorix zorix > "$backup_dir/postgres_backup.sql"
    fi
    
    # Backup Redis
    if docker-compose ps redis | grep -q "Up"; then
        log_info "Backing up Redis data..."
        docker-compose exec -T redis redis-cli BGSAVE
        docker cp "$(docker-compose ps -q redis):/data/dump.rdb" "$backup_dir/redis_backup.rdb"
    fi
    
    # Backup volumes
    log_info "Backing up application data..."
    docker run --rm -v zorix-agent_zorix_data:/data -v "$backup_dir:/backup" alpine tar czf /backup/zorix_data.tar.gz -C /data .
    docker run --rm -v zorix-agent_zorix_logs:/data -v "$backup_dir:/backup" alpine tar czf /backup/zorix_logs.tar.gz -C /data .
    
    log_success "Backup created: $backup_dir"
}

# Restore from backup
restore_backup() {
    local backup_dir="$1"
    
    if [[ -z "$backup_dir" ]]; then
        log_error "Backup directory not specified"
        exit 1
    fi
    
    if [[ ! -d "$backup_dir" ]]; then
        log_error "Backup directory not found: $backup_dir"
        exit 1
    fi
    
    log_info "Restoring from backup: $backup_dir"
    
    # Confirmation
    if [[ "$FORCE" != "true" ]]; then
        echo -n "This will overwrite current data. Continue? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Restore cancelled"
            exit 0
        fi
    fi
    
    cd "$PROJECT_DIR"
    
    # Stop services
    stop_services
    
    # Restore database
    if [[ -f "$backup_dir/postgres_backup.sql" ]]; then
        log_info "Restoring PostgreSQL database..."
        docker-compose up -d postgres
        sleep 10
        docker-compose exec -T postgres psql -U zorix -d zorix < "$backup_dir/postgres_backup.sql"
    fi
    
    # Restore Redis
    if [[ -f "$backup_dir/redis_backup.rdb" ]]; then
        log_info "Restoring Redis data..."
        docker cp "$backup_dir/redis_backup.rdb" "$(docker-compose ps -q redis):/data/dump.rdb"
    fi
    
    # Restore volumes
    if [[ -f "$backup_dir/zorix_data.tar.gz" ]]; then
        log_info "Restoring application data..."
        docker run --rm -v zorix-agent_zorix_data:/data -v "$backup_dir:/backup" alpine tar xzf /backup/zorix_data.tar.gz -C /data
    fi
    
    if [[ -f "$backup_dir/zorix_logs.tar.gz" ]]; then
        log_info "Restoring logs..."
        docker run --rm -v zorix-agent_zorix_logs:/data -v "$backup_dir:/backup" alpine tar xzf /backup/zorix_logs.tar.gz -C /data
    fi
    
    log_success "Restore completed"
}

# Update services
update_services() {
    log_info "Updating services..."
    
    cd "$PROJECT_DIR"
    
    # Pull latest images
    if [[ -f "docker-compose.prod.yml" ]] && docker-compose -f docker-compose.prod.yml ps -q &> /dev/null; then
        docker-compose -f docker-compose.prod.yml pull
        docker-compose -f docker-compose.prod.yml up -d
    else
        docker-compose pull
        docker-compose up -d
    fi
    
    log_success "Services updated"
}

# Clean up resources
clean_resources() {
    log_info "Cleaning up resources..."
    
    if [[ "$FORCE" != "true" ]]; then
        echo -n "This will remove all containers, images, and volumes. Continue? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Cleanup cancelled"
            exit 0
        fi
    fi
    
    cd "$PROJECT_DIR"
    
    # Stop and remove containers
    docker-compose down -v --remove-orphans
    if [[ -f "docker-compose.prod.yml" ]]; then
        docker-compose -f docker-compose.prod.yml down -v --remove-orphans
    fi
    
    # Remove images
    docker images | grep zorix | awk '{print $3}' | xargs -r docker rmi -f
    
    # Clean up unused resources
    docker system prune -f
    
    log_success "Cleanup completed"
}

# Parse command line arguments
COMMAND=""
NO_BUILD="false"
FORCE="false"
VERBOSE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        dev|prod|stop|restart|logs|status|backup|restore|update|clean|help)
            COMMAND="$1"
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --no-build)
            NO_BUILD="true"
            shift
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --verbose)
            VERBOSE="true"
            set -x
            shift
            ;;
        *)
            if [[ -z "$COMMAND" ]]; then
                COMMAND="$1"
            fi
            shift
            ;;
    esac
done

# Main execution
main() {
    check_prerequisites
    
    case "$COMMAND" in
        dev)
            load_env "dev"
            start_dev
            ;;
        prod)
            load_env "prod"
            deploy_prod
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs "$2"
            ;;
        status)
            show_status
            ;;
        backup)
            create_backup
            ;;
        restore)
            restore_backup "$2"
            ;;
        update)
            update_services
            ;;
        clean)
            clean_resources
            ;;
        help|"")
            show_help
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"