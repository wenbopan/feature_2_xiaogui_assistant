#!/bin/bash

# Hello Siling - Legal Docs MVP 启动脚本
# 支持 Ctrl+C 时自动清理 Docker 服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
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

# 清理函数
cleanup() {
    log_info "收到中断信号，正在清理 Docker 服务..."
    
    # 停止所有服务
    log_info "停止 Docker Compose 服务..."
    docker-compose -f docker-compose.aliyun.yml down
    
    # 检查端口是否释放
    log_info "检查端口释放情况..."
    if lsof -i :5432 -i :9000 -i :9001 -i :9092 -i :8001 -i :3000 >/dev/null 2>&1; then
        log_warning "部分端口仍被占用，正在强制清理..."
        # 强制停止可能残留的进程
        pkill -f "postgres" 2>/dev/null || true
        pkill -f "minio" 2>/dev/null || true
        pkill -f "redpanda" 2>/dev/null || true
    fi
    
    log_success "清理完成！"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 检查 Docker 是否运行
if ! docker info >/dev/null 2>&1; then
    log_error "Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

# 检查端口占用
log_info "检查端口占用情况..."
if lsof -i :5432 -i :6379 -i :9000 -i :9001 -i :9092 -i :8001 -i :3000 >/dev/null 2>&1; then
    log_warning "检测到端口占用，正在清理..."
    
    # 停止本地服务
    brew services stop postgresql@14 2>/dev/null || true
    pkill -f "minio" 2>/dev/null || true
    
    # 等待端口释放
    sleep 3
    
    # 再次检查
    if lsof -i :5432 -i :9000 -i :9001 -i :9092 -i :8001 -i :3000 >/dev/null 2>&1; then
        log_error "端口仍被占用，请手动清理后重试"
        exit 1
    fi
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    log_warning "未找到 .env 文件，请先配置环境变量"
    log_info "可以复制 env.template 并填入实际值："
    log_info "cp env.template .env"
    exit 1
fi

# 检查 Gemini API Key
if ! grep -q "GEMINI_API_KEY=your_gemini_api_key_here" .env; then
    log_info "环境变量配置检查通过"
else
    log_error "请先在 .env 文件中配置 GEMINI_API_KEY"
    exit 1
fi

# 启动服务
log_info "启动 Hello Siling 服务..."

# 加载预保存的Docker镜像
log_info "加载预保存的Docker镜像..."
docker load -i postgres-15-alpine.tar &
docker load -i minio-latest.tar &
docker load -i redpanda-latest.tar &
wait

# 构建并启动所有服务（后台运行）
log_info "构建并启动服务..."
docker-compose -f docker-compose.aliyun.yml up --build -d

# 等待服务启动
log_info "等待服务启动..."
sleep 10

# 检查服务状态
log_info "检查服务状态..."
docker-compose -f docker-compose.aliyun.yml ps

# 显示服务访问信息
log_success "服务启动完成！"
log_info "前端访问地址: http://localhost:3000"
log_info "后端API地址: http://localhost:8001"
log_info "MinIO控制台: http://localhost:9001 (admin/password123)"
log_info ""
log_info "查看日志: docker-compose -f docker-compose.aliyun.yml logs -f"
log_info "停止服务: docker-compose -f docker-compose.aliyun.yml down"
log_info "按 Ctrl+C 停止监控并清理服务"

# 监控日志
log_info "开始监控服务日志（按 Ctrl+C 停止）..."
docker-compose -f docker-compose.aliyun.yml logs -f
