#!/bin/bash
# install-deps.sh - 安装本地依赖服务
# 使用方法: ./install-deps.sh

echo "📦 开始安装本地依赖服务..."

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 检查brew
check_brew() {
    if ! command -v brew &> /dev/null; then
        log_error "brew未安装，请先安装Homebrew"
        log_info "安装Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    log_info "Homebrew已安装: $(brew --version)"
}

# 安装PostgreSQL
install_postgresql() {
    log_step "安装PostgreSQL..."
    
    if command -v psql &> /dev/null; then
        log_info "PostgreSQL已安装: $(psql --version)"
        return
    fi
    
    log_info "使用brew安装PostgreSQL..."
    brew install postgresql
    
    log_info "PostgreSQL安装完成"
    log_info "启动服务: brew services start postgresql"
}

# 安装MinIO
install_minio() {
    log_step "安装MinIO..."
    
    if command -v minio &> /dev/null; then
        log_info "MinIO已安装: $(minio --version)"
        return
    fi
    
    log_info "使用brew安装MinIO..."
    brew install minio/stable/minio
    
    log_info "MinIO安装完成"
    log_info "启动服务: minio server ~/minio/data --address \":9000\" --console-address \":9001\""
}

# 安装MinIO客户端
install_minio_client() {
    log_step "安装MinIO客户端..."
    
    if command -v mc &> /dev/null; then
        log_info "MinIO客户端已安装: $(mc --version)"
        return
    fi
    
    log_info "使用brew安装MinIO客户端..."
    brew install minio/stable/mc
    
    log_info "MinIO客户端安装完成"
}

# 安装Redpanda
install_redpanda() {
    log_step "安装Redpanda..."
    
    if command -v rpk &> /dev/null; then
        log_info "Redpanda已安装: $(rpk version)"
        return
    fi
    
    log_info "使用brew安装Redpanda..."
    brew install redpanda-data/tap/redpanda
    
    log_info "Redpanda安装完成"
    log_info "启动服务: rpk redpanda start --smp 1 --memory 1G"
}

# 创建数据目录
create_directories() {
    log_step "创建数据目录..."
    
    mkdir -p ~/minio/data
    mkdir -p ~/redpanda/data
    
    log_info "数据目录创建完成:"
    log_info "  - MinIO: ~/minio/data"
    log_info "  - Redpanda: ~/redpanda/data"
}

# 显示安装结果
show_installation() {
    echo ""
    echo "📊 安装结果:"
    echo "PostgreSQL: $(command -v psql > /dev/null && echo '✓ 已安装' || echo '✗ 未安装')"
    echo "MinIO: $(command -v minio > /dev/null && echo '✓ 已安装' || echo '✗ 未安装')"
    echo "MinIO客户端: $(command -v mc > /dev/null && echo '✓ 已安装' || echo '✗ 未安装')"
    echo "Redpanda: $(command -v rpk > /dev/null && echo '✓ 已安装' || echo '✗ 未安装')"
}

# 主函数
main() {
    log_info "开始安装本地依赖服务..."
    echo "=================================="
    
    check_brew
    install_postgresql
    install_minio
    install_minio_client
    install_redpanda
    create_directories
    show_installation
    
    echo ""
    log_info "安装完成！现在可以运行: ./startup.sh"
}

# 运行主函数
main "$@"
