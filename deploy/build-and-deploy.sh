#!/bin/bash

# Hello Siling - Build and Deploy Script
# Builds all images locally and transfers to Alibaba Cloud server

set -e

# Configuration
SERVER_USER="developer"
SERVER_IP="47.98.154.221"
SERVER_PATH="/data/home/developer/deploy/feature_2_xiaogui_assistant/deploy"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors
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

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker Desktop first."
    exit 1
fi

log_info "Starting build and deploy process..."

# Step 1: Build application images for x86_64 architecture
log_info "Building application images for x86_64 architecture..."

log_info "Building backend image..."
docker build --platform linux/amd64 -t hello-siling-backend:latest "$PROJECT_ROOT/backend"

log_info "Building frontend image..."
docker build --platform linux/amd64 -t hello-siling-frontend:latest "$PROJECT_ROOT/frontend"

# Step 2: Pull base images for x86_64 architecture
log_info "Pulling base images for x86_64 architecture..."

log_info "Pulling postgres:15-alpine..."
docker pull --platform linux/amd64 postgres:15-alpine

log_info "Pulling minio/minio:latest..."
docker pull --platform linux/amd64 minio/minio:latest

log_info "Pulling redpandadata/redpanda:latest..."
docker pull --platform linux/amd64 redpandadata/redpanda:latest

# Step 3: Save all images as tar files
log_info "Saving images as tar files..."

# Create docker-images directory if it doesn't exist
mkdir -p docker-images

log_info "Saving application images..."
docker save hello-siling-backend:latest -o docker-images/hello-siling-backend.tar
docker save hello-siling-frontend:latest -o docker-images/hello-siling-frontend.tar

log_info "Saving base images..."
docker save postgres:15-alpine -o docker-images/postgres-15-alpine.tar
docker save minio/minio:latest -o docker-images/minio-latest.tar
docker save redpandadata/redpanda:latest -o docker-images/redpanda-latest.tar

# Step 4: Transfer images to server
log_info "Transferring images to server..."

log_info "Uploading all images..."
scp docker-images/*.tar "$SERVER_USER@$SERVER_IP:$SERVER_PATH/"

# Step 5: Clean up temporary files (keep docker-images folder)
log_info "Cleaning up temporary files..."
# No cleanup needed - keeping docker-images folder for future use

log_success "Build and transfer completed successfully!"
log_info ""
log_info "Next steps on your server:"
log_info "1. SSH into your server: ssh $SERVER_USER@$SERVER_IP"
log_info "2. Go to deploy directory: cd $SERVER_PATH"
log_info "3. Run startup script: ./startup.sh"
log_info ""
log_info "The startup script will load the pre-built images and start all services!"
