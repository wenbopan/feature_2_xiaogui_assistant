#!/bin/bash

# shutdown.sh - 停止所有服务
# 使用方法: ./shutdown.sh

# 服务配置（必须与startup.sh保持一致）
SERVICE_NAME="feature_2_service"
SERVICE_PORT=8000

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

# 停止进程函数
stop_process() {
    local process_name=$1
    local signal=${2:-TERM}
    
    local pids=$(pgrep -f "$process_name" 2>/dev/null)
    if [ -n "$pids" ]; then
        log_info "Stopping $process_name (PIDs: $pids)..."
        echo $pids | xargs kill -$signal 2>/dev/null || true
        sleep 2
        
        # 检查是否还在运行
        local remaining_pids=$(pgrep -f "$process_name" 2>/dev/null)
        if [ -n "$remaining_pids" ]; then
            log_warn "Force killing $process_name (PIDs: $remaining_pids)..."
            echo $remaining_pids | xargs kill -KILL 2>/dev/null || true
        fi
    else
        log_info "$process_name is not running"
    fi
}

# 停止端口上的进程
stop_port() {
    local port=$1
    local service_name=$2
    
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pids" ]; then
        log_info "Stopping $service_name on port $port (PIDs: $pids)..."
        echo $pids | xargs kill -TERM 2>/dev/null || true
        sleep 2
        
        # 检查是否还在运行
        local remaining_pids=$(lsof -ti:$port 2>/dev/null)
        if [ -n "$remaining_pids" ]; then
            log_warn "Force killing processes on port $port (PIDs: $remaining_pids)..."
            echo $remaining_pids | xargs kill -KILL 2>/dev/null || true
        fi
    else
        log_info "No process running on port $port"
    fi
}

main() {
    echo "=========================================="
    log_info "🛑 Stopping Legal Docs MVP Application"
    echo "=========================================="
    
    # 停止FastAPI应用
    log_step "1. Stopping FastAPI application..."
    
    # 直接通过服务名和端口停止FastAPI应用
    log_info "Stopping FastAPI application..."
    
    # 通过PID文件停止我们的服务
    log_info "Stopping $SERVICE_NAME by PID file..."
    
    # 方式1：读取.env.pid文件中的PID
    if [ -f ".env.pid" ]; then
        source .env.pid
        if [ -n "$SERVICE_PID" ] && kill -0 "$SERVICE_PID" 2>/dev/null; then
            log_info "Found $SERVICE_NAME process (PID: $SERVICE_PID), stopping..."
            kill -TERM "$SERVICE_PID" 2>/dev/null || true
            sleep 3
            
            # 检查是否还在运行
            if kill -0 "$SERVICE_PID" 2>/dev/null; then
                log_warn "Force killing $SERVICE_NAME process (PID: $SERVICE_PID)..."
                kill -KILL "$SERVICE_PID" 2>/dev/null || true
            fi
        else
            log_info "PID $SERVICE_PID from .env.pid is not running"
        fi
        
        # 清除环境变量文件
        rm -f .env.pid
        log_info "Cleared .env.pid file"
    else
        log_info "No .env.pid file found"
    fi
    
    # 方式2：通过端口停止（确保没有进程占用端口）
    if lsof -ti:$SERVICE_PORT >/dev/null 2>&1; then
        log_info "Port $SERVICE_PORT still in use, stopping processes on port..."
        stop_port $SERVICE_PORT "FastAPI application"
    fi
    
    # 兼容性：停止可能的Python进程（旧版本）
    log_info "Stopping any remaining Python app.main processes..."
    stop_process "python.*app.main"
    
    # 最终验证所有相关进程已停止
    local final_check=$(pgrep -f "$SERVICE_NAME\|python.*app.main" 2>/dev/null)
    if [ -n "$final_check" ]; then
        log_warn "Some application processes still running (PIDs: $final_check), force killing..."
        echo $final_check | xargs kill -KILL 2>/dev/null || true
    else
        log_info "All application processes stopped"
    fi
    
    # 停止Redpanda (Docker容器)
    log_step "2. Stopping Redpanda..."
    if command -v docker &> /dev/null; then
        # 查找Redpanda容器
        local redpanda_container=$(docker ps --filter "name=redpanda" --format "{{.Names}}" 2>/dev/null | head -1)
        if [ -n "$redpanda_container" ]; then
            log_info "Stopping Redpanda container: $redpanda_container"
            docker stop "$redpanda_container" 2>/dev/null || true
            sleep 2
        else
            log_info "No Redpanda container found"
        fi
    elif command -v rpk &> /dev/null; then
        # 尝试使用rpk停止
        log_info "Attempting to stop Redpanda via rpk..."
        rpk container stop redpanda-1 2>/dev/null || true
    else
        log_warn "Neither docker nor rpk found, trying process-based stop"
        stop_process "redpanda"
        stop_port 9092 "Redpanda"
    fi
    
    # 停止MinIO
    log_step "3. Stopping MinIO..."
    stop_process "minio server"
    stop_port 9000 "MinIO"
    
    # 可选：停止PostgreSQL（通常保持运行）
    log_step "4. PostgreSQL status..."
    if lsof -Pi :5432 -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_info "PostgreSQL is still running (this is normal)"
        log_info "To stop PostgreSQL manually:"
        if command -v brew &> /dev/null; then
            log_info "  brew services stop postgresql"
        elif command -v systemctl &> /dev/null; then
            log_info "  sudo systemctl stop postgresql"
        fi
    else
        log_info "PostgreSQL is not running"
    fi
    
    # 清理日志文件
    log_step "5. Cleaning up..."
    if [ -f "app.log" ]; then
        log_info "Archiving application log..."
        mv app.log "app.log.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    fi
    
    # 检查剩余进程
    log_step "6. Checking for remaining processes..."
    local remaining_processes=$(pgrep -f "python.*app.main|minio|redpanda|rpk" 2>/dev/null || true)
    if [ -n "$remaining_processes" ]; then
        log_warn "Some processes are still running:"
        ps -p $remaining_processes -o pid,cmd 2>/dev/null || true
    else
        log_info "All application processes stopped"
    fi
    
    echo "=========================================="
    log_info "✅ Shutdown completed"
    echo "=========================================="
}

# 运行主函数
main "$@"
