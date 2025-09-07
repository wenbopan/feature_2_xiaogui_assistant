#!/bin/bash

# install-deps.sh - 安装所有必要的依赖
# 使用方法: ./install-deps.sh

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

# 检查并安装Homebrew
install_homebrew() {
    if ! command -v brew &> /dev/null; then
        log_warn "Homebrew is not installed, installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ $? -eq 0 ]; then
            log_success "Homebrew installed successfully"
            # Add Homebrew to PATH for current session
            eval "$(/opt/homebrew/bin/brew shellenv)"
        else
            log_error "Failed to install Homebrew"
            exit 1
        fi
    else
        log_info "Homebrew is already installed"
    fi
}

# 检查并安装依赖
install_dependency() {
    local cmd=$1
    local install_cmd=$2
    local package_name=$3
    
    if ! command -v "$cmd" &> /dev/null; then
        log_warn "$cmd is not installed, installing $package_name..."
        if eval "$install_cmd"; then
            log_success "$package_name installed successfully"
        else
            log_error "Failed to install $package_name"
            exit 1
        fi
    else
        log_info "$cmd is already installed"
    fi
}

# 主函数
main() {
    echo "=========================================="
    log_info "🔧 Installing Dependencies for Legal Docs MVP"
    echo "=========================================="
    
    # 安装Homebrew
    log_step "1. Installing Homebrew..."
    install_homebrew
    
    # 安装系统依赖
    log_step "2. Installing system dependencies..."
    install_dependency "python3" "brew install python@3.12" "Python 3.12"
    install_dependency "psql" "brew install postgresql@14" "PostgreSQL"
    install_dependency "kafka-server-start" "brew install kafka" "Apache Kafka"
    install_dependency "curl" "brew install curl" "curl"
    install_dependency "uv" "brew install uv" "uv (Python package manager)"
    
    # 启动PostgreSQL服务
    log_step "3. Starting PostgreSQL service..."
    if ! brew services list | grep postgresql@14 | grep started > /dev/null; then
        log_info "Starting PostgreSQL service..."
        brew services start postgresql@14
        sleep 5
    else
        log_info "PostgreSQL service is already running"
    fi
    
    # 创建数据库
    log_step "4. Creating database..."
    createdb legal_docs_dev 2>/dev/null || log_info "Database legal_docs_dev already exists"
    
    # 安装Python依赖
    log_step "5. Installing Python dependencies..."
    cd backend
    
    # 确保使用Python 3.12创建虚拟环境
    log_info "Creating fresh virtual environment with Python 3.12..."
    rm -rf .venv
    uv venv --python /opt/homebrew/bin/python3.12
    
    # 激活虚拟环境并安装依赖
    source .venv/bin/activate
    log_info "Installing Python packages..."
    # 使用uv直接安装
    uv pip install -e .
    
    echo "=========================================="
    log_success "🎉 All dependencies installed successfully!"
    echo "=========================================="
    
    log_info "📋 Next steps:"
    log_info "  1. Start the application: cd backend && ./startup.sh --dev"
    log_info "  2. Or start in production mode: cd backend && ./startup.sh"
    log_info ""
    log_info "📝 Available services:"
    log_info "  • PostgreSQL: localhost:5432"
    log_info "  • Kafka: localhost:9092 (will start with application)"
    log_info "  • MinIO: localhost:9000 (will start with application)"
    log_info "  • FastAPI: localhost:8000 (will start with application)"
}

# 运行主函数
main "$@"