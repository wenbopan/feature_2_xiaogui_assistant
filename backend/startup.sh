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

# 清理函数 - 停止所有服务
cleanup() {
    echo ""
    log_info "🛑 收到中断信号，正在清理服务..."
    
    # 停止FastAPI应用
    if [ -f ".env.pid" ]; then
        source .env.pid
        if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
            log_info "停止FastAPI应用 (PID: $APP_PID)..."
            kill -TERM "$APP_PID" 2>/dev/null || true
            sleep 2
        fi
        rm -f .env.pid
    fi
    
    # 停止MinIO
    if [ -n "$MINIO_PID" ] && kill -0 "$MINIO_PID" 2>/dev/null; then
        log_info "停止MinIO (PID: $MINIO_PID)..."
        kill -TERM "$MINIO_PID" 2>/dev/null || true
    fi
    
    # 停止Kafka进程
    if [ -n "$KAFKA_PID" ] && kill -0 "$KAFKA_PID" 2>/dev/null; then
        log_info "停止Kafka (PID: $KAFKA_PID)..."
        kill -TERM "$KAFKA_PID" 2>/dev/null || true
    fi
    
    # 停止Zookeeper进程
    if [ -n "$ZOOKEEPER_PID" ] && kill -0 "$ZOOKEEPER_PID" 2>/dev/null; then
        log_info "停止Zookeeper (PID: $ZOOKEEPER_PID)..."
        kill -TERM "$ZOOKEEPER_PID" 2>/dev/null || true
    fi
    
    # 停止任何残留的Kafka进程
    log_info "停止任何残留的Kafka进程..."
    pkill -f "kafka" 2>/dev/null || true
    pkill -f "zookeeper" 2>/dev/null || true
    
    # 停止Docker Compose服务（如果在deploy目录运行）
    if [ -f "../deploy/docker-compose.aliyun.yml" ]; then
        log_info "停止Docker Compose服务..."
        cd ../deploy
        docker-compose -f docker-compose.aliyun.yml down 2>/dev/null || true
        cd ../backend
    fi
    
    log_success "✅ 清理完成！"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 检查依赖函数
check_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd is not installed. Please run ./install-deps.sh first"
        exit 1
    fi
    log_info "$cmd is available"
}

# 检查环境变量配置
check_environment() {
    log_info "Checking required environment variables..."
    
    # 检查必需的API keys
    if [ -z "$GEMINI_API_KEY" ]; then
        log_error "GEMINI_API_KEY environment variable is required"
        log_info "Please set it using: export GEMINI_API_KEY='your-api-key'"
        log_info "Or add it to your ~/.zshrc file for persistence"
        exit 1
    fi
    
    if [ -z "$QWEN_API_KEY" ]; then
        log_error "QWEN_API_KEY environment variable is required"
        log_info "Please set it using: export QWEN_API_KEY='your-api-key'"
        log_info "Or add it to your ~/.zshrc file for persistence"
        exit 1
    fi
    
    # 设置默认的数据库配置（如果未设置）
    if [ -z "$DATABASE_URL" ]; then
        CURRENT_USER=$(whoami)
        export DATABASE_URL="postgresql://$CURRENT_USER@localhost:5432/legal_docs_dev"
        log_info "Using default DATABASE_URL: $DATABASE_URL"
    fi
    
    # 设置其他默认配置
    export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    export POSTGRES_PORT=${POSTGRES_PORT:-5432}
    export POSTGRES_USER=${POSTGRES_USER:-$CURRENT_USER}
    export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password}
    export POSTGRES_DB=${POSTGRES_DB:-legal_docs_dev}
    export MINIO_ENDPOINT=${MINIO_ENDPOINT:-localhost:9000}
    export MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-admin}
    export MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-password123}
    export MINIO_BUCKET=${MINIO_BUCKET:-legal-docs}
    export MINIO_SECURE=${MINIO_SECURE:-false}
    export KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}
    export APP_NAME=${APP_NAME:-feature_2_service}
    export LOG_LEVEL=${LOG_LEVEL:-INFO}
    
    log_success "Environment variables configured successfully"
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
SERVICE_PORT=8001

# 主函数
main() {
    echo "=========================================="
    log_info "🚀 Starting Legal Docs MVP Application"
    echo "=========================================="
    
    # 显示环境变量设置说明
    if [ -z "$GEMINI_API_KEY" ] || [ -z "$QWEN_API_KEY" ]; then
        echo ""
        log_info "📋 Required Environment Variables:"
        log_info "   • GEMINI_API_KEY - Your Google Gemini API key"
        log_info "   • QWEN_API_KEY - Your Qwen API key"
        echo ""
        log_info "💡 To set them permanently, add to your ~/.zshrc:"
        log_info "   export GEMINI_API_KEY='your-gemini-key'"
        log_info "   export QWEN_API_KEY='your-qwen-key'"
        echo ""
        log_info "🔄 Or set them temporarily for this session:"
        log_info "   export GEMINI_API_KEY='your-gemini-key'"
        log_info "   export QWEN_API_KEY='your-qwen-key'"
        echo ""
    fi
    
    # 检查必要的命令
    log_step "1. Checking system dependencies..."
    check_command "python3"
    check_command "psql"
    check_command "kafka-server-start"
    check_command "curl"
    
    # 检查虚拟环境
    log_step "2. Checking Python virtual environment..."
    if [ ! -f "pyproject.toml" ]; then
        log_error "pyproject.toml not found. Please ensure the project is properly configured."
        exit 1
    fi
    
    # 检查uv
    check_command "uv"
    
    # 检查.venv目录是否存在，如果不存在则创建
    if [ ! -d ".venv" ]; then
        log_info "Creating virtual environment with uv..."
        uv venv
    fi
    
    # 激活虚拟环境
    source .venv/bin/activate
    log_info "Virtual environment activated"
    
    # 检查Python依赖，如果不存在则安装
    log_step "3. Checking Python dependencies..."
    if ! python -c "import fastapi, asyncpg, aiokafka" &>/dev/null; then
        log_info "Installing dependencies with uv..."
        uv pip install -e .
    fi
    log_info "Python dependencies satisfied"
    
    # 检查环境变量配置
    log_step "4. Checking environment configuration..."
    check_environment
    
    # 启动PostgreSQL
    log_step "5. Starting PostgreSQL..."
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
    log_step "6. Starting MinIO..."
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
    
    # 启动Kafka (本地服务)
    log_step "7. Starting Apache Kafka..."
    if check_port 9092 "Kafka"; then
        log_info "Kafka is already running"
    else
        log_info "Starting Kafka locally..."
        
        # Kafka should already be installed from dependency check
        
        # 创建Kafka数据目录
        mkdir -p ~/kafka-data/zookeeper
        mkdir -p ~/kafka-data/kafka-logs
        
        # 启动Zookeeper
        log_info "Starting Zookeeper..."
        nohup zookeeper-server-start /opt/homebrew/etc/kafka/zookeeper.properties > ~/kafka-data/zookeeper.log 2>&1 &
        ZOOKEEPER_PID=$!
        
        sleep 5
        
        # 启动Kafka
        log_info "Starting Kafka server..."
        nohup kafka-server-start /opt/homebrew/etc/kafka/server.properties > ~/kafka-data/kafka.log 2>&1 &
        KAFKA_PID=$!
        
        log_info "Kafka started with PIDs: Zookeeper=$ZOOKEEPER_PID, Kafka=$KAFKA_PID"
        sleep 10
        
        # 检查Kafka进程是否仍在运行
        if ! kill -0 $KAFKA_PID 2>/dev/null; then
            log_error "Kafka failed to start. Check ~/kafka-data/kafka.log for details:"
            tail -10 ~/kafka-data/kafka.log
            exit 1
        fi
        
        log_info "Kafka process is running (PID: $KAFKA_PID)"
    fi
    
    # 等待Kafka就绪
    wait_for_service "Kafka" "kafka-topics --bootstrap-server localhost:9092 --list" 20
    
    # 启动FastAPI应用
    log_step "8. Starting FastAPI application..."
    
    # 保存进程ID到.env.pid文件（用于清理）
    echo "export SERVICE_PID=$$" > .env.pid
    echo "export SERVICE_NAME=feature_2_service" >> .env.pid
    echo "export MINIO_PID=$MINIO_PID" >> .env.pid
    echo "export KAFKA_PID=$KAFKA_PID" >> .env.pid
    echo "export ZOOKEEPER_PID=$ZOOKEEPER_PID" >> .env.pid
    echo "export APP_PID=$$" >> .env.pid
    
    # 检查是否在开发模式
    if [ "$1" = "--dev" ]; then
        log_info "Starting application in DEVELOPMENT mode with uvicorn..."
        log_info "Server will run in foreground and show live logs"
        log_info "Press Ctrl+C to stop all services"
        echo ""
        
        # 在开发模式下，前台启动uvicorn并启用reload
        log_success "🚀 All services started! Starting FastAPI in development mode..."
        echo ""
        log_info "📋 Service URLs:"
        log_info "   • FastAPI Application: http://localhost:8001"
        log_info "   • API Documentation:   http://localhost:8001/docs"
        log_info "   • Health Check:        http://localhost:8001/health"
        log_info "   • MinIO Console:       http://localhost:9001"
        log_info "   • PostgreSQL:          localhost:5432"
        log_info "   • Kafka:               localhost:9092"
        echo ""
        log_info "💡 Press Ctrl+C to stop all services"
        echo "=========================================="
        
        # 前台启动uvicorn，这样trap可以正常工作
        # 使用reload但排除.venv目录以避免频繁重启
        uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT --reload --reload-exclude ".venv/*" --reload-exclude "logs/*" --log-level info --app-dir .
    else
        log_info "Starting application in PRODUCTION mode with uvicorn..."
        log_info "Server will run in foreground and show live logs"
        log_info "Press Ctrl+C to stop all services"
        echo ""
        
        log_success "🚀 All services started! Starting FastAPI in production mode..."
        echo ""
        log_info "📋 Service URLs:"
        log_info "   • FastAPI Application: http://localhost:8001"
        log_info "   • API Documentation:   http://localhost:8001/docs"
        log_info "   • Health Check:        http://localhost:8001/health"
        log_info "   • MinIO Console:       http://localhost:9001"
        log_info "   • PostgreSQL:          localhost:5432"
        log_info "   • Kafka:               localhost:9092"
        echo ""
        log_info "💡 Press Ctrl+C to stop all services"
        echo "=========================================="
        
        # 前台启动uvicorn
        uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT --log-level info --app-dir .
    fi
}

# 运行主函数
main "$@"
