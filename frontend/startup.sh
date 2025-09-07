#!/bin/bash

# frontend/startup.sh - 启动前端开发服务器
# 使用方法: ./startup.sh [--dev|--prod]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_success() {
    echo -e "${PURPLE}[SUCCESS]${NC} $1"
}

# 检查依赖函数
check_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is not installed. Please install Node.js and npm first."
        exit 1
    fi
    log_info "$cmd is available"
}

# 设置环境配置
setup_environment() {
    if [ ! -f ".env" ]; then
        log_warn ".env file not found. Creating from template..."
        if [ -f "env.template" ]; then
            cp env.template .env
            log_success ".env file created from template"
        else
            log_error "env.template not found. Please create .env file manually."
            exit 1
        fi
    else
        log_info "Environment configuration found"
    fi
    
    # 显示当前配置
    log_info "Current frontend configuration:"
    if [ -f ".env" ]; then
        grep -E "^VITE_" .env | while read line; do
            echo "  $line"
        done
    fi
}

# 检查后端连接
check_backend() {
    local backend_host=$(grep VITE_BACKEND_HOST .env | cut -d'=' -f2 || echo "localhost")
    local backend_port=$(grep VITE_BACKEND_PORT .env | cut -d'=' -f2 || echo "8001")
    local backend_url="http://${backend_host}:${backend_port}"
    
    log_step "Checking backend connection..."
    if curl -s "${backend_url}/health" > /dev/null 2>&1; then
        log_success "Backend is running at ${backend_url}"
    else
        log_warn "Backend is not responding at ${backend_url}"
        log_info "Make sure the backend is running: cd ../backend && ./startup.sh --dev"
    fi
}

# 主函数
main() {
    echo "=========================================="
    log_info "🚀 Starting Legal Docs MVP Frontend"
    echo "=========================================="
    
    # 检查必要的命令
    log_step "1. Checking system dependencies..."
    check_command "node"
    check_command "npm"
    
    # 检查项目文件
    log_step "2. Checking project files..."
    if [ ! -f "package.json" ]; then
        log_error "package.json not found. Please ensure you're in the frontend directory."
        exit 1
    fi
    
    # 设置环境配置
    log_step "3. Setting up environment configuration..."
    setup_environment
    
    # 检查后端连接
    log_step "4. Checking backend connection..."
    check_backend
    
    # 安装依赖（如果需要）
    log_step "5. Checking dependencies..."
    if [ ! -d "node_modules" ]; then
        log_info "Installing dependencies..."
        npm install
    else
        log_info "Dependencies are already installed"
    fi
    
    # 启动开发服务器
    log_step "6. Starting development server..."
    
    if [ "$1" = "--prod" ]; then
        log_info "Starting in PRODUCTION mode..."
        log_info "Building and serving production build..."
        npm run build
        npm run preview
    else
        log_info "Starting in DEVELOPMENT mode..."
        log_info "Server will run in foreground with hot reload"
        log_info "Press Ctrl+C to stop the server"
        echo ""
        log_success "🚀 Frontend development server starting..."
        echo ""
        log_info "📋 Service URLs:"
        log_info "   • Frontend: http://localhost:5173"
        log_info "   • Backend:  http://localhost:8001"
        echo ""
        log_info "💡 Press Ctrl+C to stop the server"
        echo "=========================================="
        
        # 启动开发服务器
        npm run dev
    fi
}

# 运行主函数
main "$@"


