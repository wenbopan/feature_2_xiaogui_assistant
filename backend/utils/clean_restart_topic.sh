#!/bin/bash

# ==========================================
# Clean and Restart Kafka Topics Script
# ==========================================
# This script cleans and recreates Kafka topics for testing purposes

set -e  # Exit on any error

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

# Check if rpk is available
check_rpk() {
    if ! command -v rpk &> /dev/null; then
        log_error "rpk command not found. Please install Redpanda CLI tools."
        exit 1
    fi
    log_success "rpk is available"
}

# Check if topics exist and delete them
delete_topics() {
    log_info "Checking existing topics..."
    
    # List current topics
    local topics=$(rpk topic list --format json | jq -r '.[] | select(.name | test("^(field\\.extraction|file\\.processing)$")) | .name' 2>/dev/null || echo "")
    
    if [ -n "$topics" ]; then
        log_info "Found existing topics: $topics"
        
        # Delete field.extraction topic
        if echo "$topics" | grep -q "field.extraction"; then
            log_info "Deleting field.extraction topic..."
            if rpk topic delete field.extraction 2>/dev/null; then
                log_success "field.extraction topic deleted"
            else
                log_warning "Failed to delete field.extraction topic (may not exist)"
            fi
        fi
        
        # Delete file.processing topic
        if echo "$topics" | grep -q "file.processing"; then
            log_info "Deleting file.processing topic..."
            if rpk topic delete file.processing 2>/dev/null; then
                log_success "file.processing topic deleted"
            else
                log_warning "Failed to delete file.processing topic (may not exist)"
            fi
        fi
    else
        log_info "No existing topics found"
    fi
}

# Create topics
create_topics() {
    log_info "Creating new topics..."
    
    # Create field.extraction topic
    log_info "Creating field.extraction topic..."
    if rpk topic create field.extraction --partitions 1 --replicas 1 2>/dev/null; then
        log_success "field.extraction topic created"
    else
        log_warning "field.extraction topic creation failed (may already exist)"
    fi
    
    # Create file.processing topic
    log_info "Creating file.processing topic..."
    if rpk topic create file.processing --partitions 1 --replicas 1 2>/dev/null; then
        log_success "file.processing topic created"
    else
        log_warning "file.processing topic creation failed (may already exist)"
    fi
}

# Verify topics
verify_topics() {
    log_info "Verifying topics..."
    
    local topics=$(rpk topic list --format json | jq -r '.[] | select(.name | test("^(field\\.extraction|file\\.processing)$")) | .name' 2>/dev/null || echo "")
    
    if echo "$topics" | grep -q "field.extraction" && echo "$topics" | grep -q "file.processing"; then
        log_success "Both topics created successfully:"
        echo "$topics" | while read topic; do
            echo "  ✅ $topic"
        done
    else
        log_error "Topic verification failed. Expected topics not found."
        log_info "Current topics:"
        rpk topic list
        exit 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "🔄 Clean and Restart Kafka Topics"
    echo "=========================================="
    
    # Check prerequisites
    check_rpk
    
    # Delete existing topics
    delete_topics
    
    # Wait a moment for cleanup
    log_info "Waiting for topic cleanup to complete..."
    sleep 2
    
    # Create new topics
    create_topics
    
    # Wait a moment for creation
    log_info "Waiting for topic creation to complete..."
    sleep 2
    
    # Verify topics
    verify_topics
    
    echo "=========================================="
    log_success "🎉 Topic cleanup and recreation completed!"
    echo "=========================================="
    log_info "You can now test with clean topics."
}

# Run main function
main "$@"
