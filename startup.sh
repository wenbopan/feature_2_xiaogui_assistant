#!/bin/bash

# startup.sh - 统一启动所有依赖服务和应用
# 使用方法: ./startup.sh

set -e  # 遇到错误立即退出

# 颜色输出
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

log_check() {
    echo -e "${CYAN}[CHECK]${NC} $1"
}

# 错误处理函数
cleanup() {
    log_error "Startup failed, cleaning up..."
    # 可以在这里添加清理逻辑
    exit 1
}

trap cleanup ERR

# 检查依赖函数
check_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is not installed"
        exit 1
    fi
    log_info "$cmd is available"
}

# 等待服务就绪函数
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    log_check "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if eval "$check_command" &>/dev/null; then
            log_success "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    log_error "$service_name failed to start within timeout"
    return 1
}

# 检查端口是否被占用
check_port() {
    local port=$1
    local service_name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "Port $port is already in use by another process"
        log_info "Checking if it's $service_name..."
        return 0
    else
        return 1
    fi
}

# 服务配置
SERVICE_NAME="feature_2_service"
SERVICE_PORT=8000

# 主函数
main() {
    echo "=========================================="
    log_info "🚀 Starting Legal Docs MVP Application"
    echo "=========================================="
    
    # 检查必要的命令
    log_step "1. Checking system dependencies..."
    check_command "python3"
    check_command "psql"
    check_command "rpk"
    check_command "curl"
    
    # 检查虚拟环境
    log_step "2. Checking Python virtual environment..."
    if [ ! -d "venv" ]; then
        log_error "Virtual environment not found. Please create it first: python3 -m venv venv"
        exit 1
    fi
    log_info "Virtual environment found"
    
    # 激活虚拟环境
    source venv/bin/activate
    log_info "Virtual environment activated"
    
    # 检查Python依赖
    log_step "3. Checking Python dependencies..."
    if ! python -c "import fastapi, asyncpg, aiokafka" &>/dev/null; then
        log_warn "Some dependencies missing, installing..."
        pip install -r requirements.txt
    fi
    log_info "Python dependencies satisfied"
    
    # 启动PostgreSQL
    log_step "4. Starting PostgreSQL..."
    if check_port 5432 "PostgreSQL"; then
        log_info "PostgreSQL is already running"
    else
        log_info "Starting PostgreSQL service..."
        if command -v brew &> /dev/null; then
            brew services start postgresql@14 || brew services start postgresql
        elif command -v systemctl &> /dev/null; then
            sudo systemctl start postgresql
        else
            log_error "Cannot start PostgreSQL automatically. Please start it manually."
            exit 1
        fi
    fi
    
    # 等待PostgreSQL就绪
    wait_for_service "PostgreSQL" "psql -h localhost -p 5432 -U $USER -d postgres -c 'SELECT 1'" 15
    
    # 确保数据库存在
    log_info "Ensuring database exists..."
    createdb legal_docs_dev 2>/dev/null || log_info "Database legal_docs_dev already exists"
    
    # 启动MinIO
    log_step "5. Starting MinIO..."
    if check_port 9000 "MinIO"; then
        log_info "MinIO is already running"
    else
        log_info "Starting MinIO service..."
        mkdir -p ~/minio/data
        
        # 启动MinIO并保存进程ID
        nohup env MINIO_ROOT_USER=admin MINIO_ROOT_PASSWORD=password123 minio server ~/minio/data --address ":9000" --console-address ":9001" > ~/minio/minio.log 2>&1 &
        MINIO_PID=$!
        
        log_info "MinIO started with PID: $MINIO_PID"
        sleep 3
        
        # 检查MinIO进程是否仍在运行
        if ! kill -0 $MINIO_PID 2>/dev/null; then
            log_error "MinIO failed to start. Check ~/minio/minio.log for details:"
            tail -10 ~/minio/minio.log
            exit 1
        fi
        
        log_info "MinIO process is running (PID: $MINIO_PID)"
    fi
    
    # 等待MinIO就绪
    wait_for_service "MinIO" "curl -s http://localhost:9000/minio/health/live" 10
    
    # 启动Redpanda (Docker容器)
    log_step "6. Starting Redpanda (Kafka)..."
    if check_port 9092 "Redpanda"; then
        log_info "Redpanda is already running"
    else
        log_info "Starting Redpanda cluster via Docker..."
        mkdir -p ~/redpanda-data
        
        # 启动Redpanda Docker容器
        nohup rpk container start > ~/redpanda-data/redpanda.log 2>&1 &
        REDPANDA_PID=$!
        
        log_info "Redpanda container started with PID: $REDPANDA_PID"
        sleep 10
        
        # 检查Redpanda容器是否在运行
        if ! docker ps --filter "name=redpanda-1" --format "{{.Status}}" | grep -q "Up"; then
            log_error "Redpanda container failed to start. Check ~/redpanda-data/redpanda.log for details:"
            tail -10 ~/redpanda-data/redpanda.log
            exit 1
        fi
        
        log_info "Redpanda container is running"
    fi
    
    # 等待Redpanda就绪
    wait_for_service "Redpanda" "rpk cluster health" 20
    
    # 启动FastAPI应用
    log_step "7. Starting FastAPI application..."
    
    # 检查是否在开发模式
    if [ "$1" = "--dev" ]; then
        log_info "Starting application in DEVELOPMENT mode with uvicorn..."
        log_info "This will start uvicorn in the background with auto-reload enabled"
        echo ""
        
        # 在开发模式下，后台启动uvicorn并启用reload
        # 启动uvicorn服务
        nohup uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT --reload --log-level info --app-dir . > logs/app.log 2>&1 &
        APP_PID=$!
        
        # 保存进程ID到.env.pid文件
        echo "export SERVICE_PID=$APP_PID" > .env.pid
        echo "export SERVICE_NAME=feature_2_service" >> .env.pid
        echo "export MINIO_PID=$MINIO_PID" >> .env.pid
        echo "export APP_PID=$APP_PID" >> .env.pid
        
        log_info "Development server started with PID: $APP_PID"
        log_info "Service name: $SERVICE_NAME"
        log_info "PID saved to .env.pid file"
        log_info "Logs are being written to logs/app.log"
        log_info "Server will automatically reload when you modify code"
    else
        log_info "Starting application in PRODUCTION mode with uvicorn (background)..."
        # 启动uvicorn服务
        nohup uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT --log-level info --app-dir . > logs/app.log 2>&1 &
        APP_PID=$!
        
        # 保存进程ID到.env.pid文件
        echo "export SERVICE_PID=$APP_PID" > .env.pid
        echo "export SERVICE_NAME=feature_2_service" >> .env.pid
        echo "export MINIO_PID=$MINIO_PID" >> .env.pid
        echo "export APP_PID=$APP_PID" >> .env.pid
    fi
    
    # 等待应用启动
    log_check "Waiting for application to start..."
    sleep 5
    
    # 检查应用是否仍在运行
    if ! kill -0 $APP_PID 2>/dev/null; then
        log_error "Application failed to start. Check logs/app.log for details:"
        tail -20 logs/app.log
        exit 1
    fi
    
    # 简单的进程状态检查
    log_step "8. Application status check..."
    echo ""
    log_info "📊 Application status:"
    log_success "✅ Application process is running (PID: $APP_PID)"
    log_info "📝 Check logs/app.log for detailed application status"
    echo ""
    
    # 保存进程ID到文件
    log_info "Saving process IDs..."
    # 所有PID信息已经保存在.env.pid文件中，不需要创建分散的PID文件
    
    # 启动成功
    echo "=========================================="
    log_success "🎉 ALL SERVICES STARTED SUCCESSFULLY!"
    echo "=========================================="
    
    log_info "📋 Service URLs:"
    log_info "  • FastAPI Application: http://localhost:8000"
    log_info "  • API Documentation:   http://localhost:8000/docs"
    log_info "  • Health Check:        http://localhost:8000/health"
    log_info "  • Readiness Check:     http://localhost:8000/ready"
    log_info "  • MinIO Console:       http://localhost:9001"
    log_info "  • PostgreSQL:          localhost:5432"
    log_info "  • Redpanda:            localhost:9092"
    
    echo ""
    log_info "📝 Useful commands:"
    log_info "  • View app logs:       tail -f logs/app.log"
    log_info "  • Test upload:         curl -X POST http://localhost:8000/api/v1/tasks/upload"
    log_info "  • Stop services:       ./stop-local.sh"
    
    echo ""
    log_success "🚀 System is ready for testing!"
    
    log_info "💡 Application PID: $APP_PID (saved to .env.pid)"
    log_info "💡 Use 'kill $APP_PID' to stop the application"
}

# 运行主函数
main "$@"
