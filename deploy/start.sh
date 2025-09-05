#!/bin/bash

# Hello Siling - 快速启动脚本（后台运行）
# 不监控日志，直接启动服务

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[INFO]${NC} 启动 Hello Siling 服务（后台模式）..."

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo -e "${RED}[ERROR]${NC} 未找到 .env 文件，请先配置环境变量"
    echo "可以复制 env.template 并填入实际值："
    echo "cp env.template .env"
    exit 1
fi

# 启动服务
docker-compose -f docker-compose.aliyun.yml up --build -d

# 等待服务启动
echo -e "${BLUE}[INFO]${NC} 等待服务启动..."
sleep 10

# 检查服务状态
echo -e "${BLUE}[INFO]${NC} 检查服务状态..."
docker-compose -f docker-compose.aliyun.yml ps

echo -e "${GREEN}[SUCCESS]${NC} 服务启动完成！"
echo "前端访问地址: http://localhost:3000"
echo "后端API地址: http://localhost:8001"
echo "MinIO控制台: http://localhost:9001 (admin/password123)"
echo ""
echo "查看日志: docker-compose -f docker-compose.aliyun.yml logs -f"
echo "停止服务: docker-compose -f docker-compose.aliyun.yml down"
