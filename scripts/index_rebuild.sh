#!/bin/bash
# Vector index rebuild script for Zorix Agent

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL=${API_URL:-"http://127.0.0.1:8000"}
WORKSPACE_ROOT=${WORKSPACE_ROOT:-"./workspace"}
TIMEOUT=${TIMEOUT:-300}

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INDEX]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if API is running
check_api_health() {
    print_status "Checking API health..."
    
    if curl -f -s "$API_URL/health" >/dev/null 2>&1; then
        print_success "API is healthy"
        return 0
    else
        print_error "API is not responding at $API_URL"
        return 1
    fi
}

# Function to get current index status
get_index_status() {
    print_status "Getting current index status..."
    
    local response=$(curl -s "$API_URL/api/v1/system/status" 2>/dev/null)
    
    if [[ $? -eq 0 ]] && [[ -n "$response" ]]; then
        echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"Index status: {data.get('vector_index_status', 'unknown')}\")
    print(f\"Index size: {data.get('vector_index_size', 'unknown')}\")
    print(f\"Last updated: {data.get('vector_index_last_updated', 'unknown')}\")
except:
    print('Could not parse status response')
"
    else
        print_warning "Could not get index status"
    fi
}

# Function to backup current index
backup_index() {
    print_status "Backing up current index..."
    
    local backup_dir="./data/backups/$(date +%Y%m%d_%H%M%S)"
    local index_dir="./data/vector_index"
    
    if [[ -d "$index_dir" ]]; then
        mkdir -p "$backup_dir"
        cp -r "$index_dir" "$backup_dir/"
        print_success "Index backed up to $backup_dir"
    else
        print_warning "No existing index found to backup"
    fi
}

# Function to rebuild index
rebuild_index() {
    print_status "Starting index rebuild..."
    
    local start_time=$(date +%s)
    
    # Call the rebuild endpoint
    local response=$(curl -s -X POST "$API_URL/index/rebuild" \
                     -H "Content-Type: application/json" \
                     -d '{}' \
                     --max-time "$TIMEOUT")
    
    local curl_exit_code=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ $curl_exit_code -eq 0 ]]; then
        # Parse response
        echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        stats = data.get('stats', {})
        print(f\"✓ Index rebuilt successfully in ${duration}s\")
        print(f\"  Files processed: {stats.get('files', 'unknown')}\")
        print(f\"  Chunks created: {stats.get('chunks', 'unknown')}\")
        print(f\"  Time taken: {stats.get('time_taken', 'unknown')}s\")
    else:
        print(f\"✗ Index rebuild failed: {data.get('error', 'unknown error')}\")
        sys.exit(1)
except Exception as e:
    print(f\"✗ Failed to parse response: {e}\")
    print(f\"Raw response: {repr(sys.stdin.read())}\")
    sys.exit(1)
"
        local parse_exit_code=$?
        
        if [[ $parse_exit_code -eq 0 ]]; then
            print_success "Index rebuild completed successfully"
        else
            print_error "Index rebuild response parsing failed"
            return 1
        fi
    else
        print_error "Index rebuild request failed (timeout: ${TIMEOUT}s)"
        print_error "Raw response: $response"
        return 1
    fi
}

# Function to verify index
verify_index() {
    print_status "Verifying rebuilt index..."
    
    # Test search functionality
    local test_query="test"
    local response=$(curl -s -X POST "$API_URL/search" \
                     -H "Content-Type: application/json" \
                     -d "{\"query\": \"$test_query\", \"top_k\": 5}")
    
    if [[ $? -eq 0 ]]; then
        echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    print(f\"✓ Search test passed: {len(results)} results for '$test_query'\")
except:
    print('✗ Search test failed: could not parse response')
    sys.exit(1)
"
        if [[ $? -eq 0 ]]; then
            print_success "Index verification passed"
        else
            print_error "Index verification failed"
            return 1
        fi
    else
        print_error "Search test failed"
        return 1
    fi
}

# Function to show index statistics
show_index_stats() {
    print_status "Index Statistics"
    echo "=================="
    
    # Get system status
    local response=$(curl -s "$API_URL/api/v1/system/status")
    
    if [[ $? -eq 0 ]] && [[ -n "$response" ]]; then
        echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"Status: {data.get('vector_index_status', 'unknown')}\")
    print(f\"Size: {data.get('vector_index_size', 'unknown')}\")
    print(f\"Files indexed: {data.get('vector_index_files', 'unknown')}\")
    print(f\"Chunks: {data.get('vector_index_chunks', 'unknown')}\")
    print(f\"Last updated: {data.get('vector_index_last_updated', 'unknown')}\")
except:
    print('Could not parse status response')
"
    else
        print_warning "Could not get index statistics"
    fi
    
    echo
}

# Function to show help
show_help() {
    echo "Zorix Agent Index Rebuild Script"
    echo
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  rebuild        Rebuild the vector index"
    echo "  status         Show current index status" 
    echo "  verify         Verify index functionality"
    echo "  backup         Backup current index"
    echo "  stats          Show detailed index statistics"
    echo "  help           Show this help message"
    echo
    echo "Environment Variables:"
    echo "  API_URL        API server URL (default: http://127.0.0.1:8000)"
    echo "  WORKSPACE_ROOT Workspace directory (default: ./workspace)"
    echo "  TIMEOUT        Request timeout in seconds (default: 300)"
    echo
    echo "Examples:"
    echo "  $0 rebuild                    # Rebuild index"
    echo "  API_URL=http://localhost:8001 $0 status  # Check status on different port"
    echo
}

# Main script logic
case "${1:-rebuild}" in
    rebuild)
        check_api_health || exit 1
        get_index_status
        backup_index
        rebuild_index || exit 1
        verify_index || exit 1
        show_index_stats
        ;;
    status)
        check_api_health || exit 1
        get_index_status
        ;;
    verify)
        check_api_health || exit 1
        verify_index || exit 1
        ;;
    backup)
        backup_index
        ;;
    stats)
        check_api_health || exit 1
        show_index_stats
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac