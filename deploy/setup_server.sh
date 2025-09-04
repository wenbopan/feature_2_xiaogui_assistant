#!/bin/bash
# 服务器初始化脚本
# 在服务器上运行此脚本来设置部署环境

set -e

echo "🚀 开始设置服务器部署环境..."

# 更新系统包
echo "📦 更新系统包..."
# 配置阿里云 apt 镜像源
sudo cp /etc/apt/sources.list /etc/apt/sources.list.backup
sudo tee /etc/apt/sources.list > /dev/null << 'EOF'
deb https://mirrors.aliyun.com/ubuntu/ focal main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ focal-security main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ focal-updates main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ focal-backports main restricted universe multiverse
EOF

sudo apt update && sudo apt upgrade -y

# 安装必要的系统依赖
echo "🔧 安装系统依赖..."
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    postgresql \
    postgresql-contrib \
    curl \
    wget \
    git \
    htop \
    unzip \
    systemd

# 配置 pip 使用阿里云镜像
echo "🐍 配置 pip 使用阿里云镜像..."
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
[install]
trusted-host = mirrors.aliyun.com
EOF

# 安装 uv (Python 包管理器)
echo "🐍 使用阿里云镜像安装 uv..."
if pip3 install uv; then
    echo "✅ uv 安装成功"
else
    echo "❌ 阿里云镜像安装失败，尝试官方安装脚本..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        echo "✅ uv 安装成功"
        if [ -f "$HOME/.cargo/env" ]; then
            source $HOME/.cargo/env
        else
            export PATH="$HOME/.cargo/bin:$PATH"
            echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
        fi
    else
        echo "❌ uv 安装失败，请检查网络连接"
        exit 1
    fi
fi

# 验证 uv 安装
if command -v uv >/dev/null 2>&1; then
    echo "✅ uv 已正确安装: $(uv --version)"
else
    echo "❌ uv 安装验证失败"
    exit 1
fi

# 检查 Docker 是否已安装
echo "🐳 检查 Docker 安装状态..."
if command -v docker >/dev/null 2>&1; then
    echo "✅ Docker 已安装: $(docker --version)"
    # 确保用户在 docker 组中
    if ! groups $USER | grep -q docker; then
        echo "🔧 添加用户到 docker 组..."
        sudo usermod -aG docker $USER
        echo "⚠️  请重新登录或运行 'newgrp docker' 以使权限生效"
    fi
else
    echo "🐳 安装 Docker..."
    # 配置 Docker 使用阿里云镜像
    sudo mkdir -p /etc/docker
    sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.mirrors.ustc.edu.cn",
    "https://reg-mirror.qiniu.com"
  ]
}
EOF

    # 安装 Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh

    # 重启 Docker 服务
    sudo systemctl restart docker
    echo "✅ Docker 安装完成"
fi

# 创建部署目录
echo "📁 创建部署目录..."
mkdir -p ~/deploy
mkdir -p ~/logs

# 设置 PostgreSQL
echo "🗄️ 配置 PostgreSQL..."
sudo -u postgres psql << 'EOF'
CREATE DATABASE legal_docs_dev;
CREATE USER legal_user WITH PASSWORD 'legal_password_123';
GRANT ALL PRIVILEGES ON DATABASE legal_docs_dev TO legal_user;
\q
EOF

# 跳过 Nginx 配置 - 使用 Docker 容器直接提供服务
echo "🐳 使用 Docker 容器直接提供服务..."
echo "   - 前端: http://$(hostname -I | awk '{print $1}'):3000"
echo "   - 后端: http://$(hostname -I | awk '{print $1}'):8001"
echo "   - Webhook: http://$(hostname -I | awk '{print $1}'):8080"

# 创建 systemd 服务文件
echo "⚙️ 创建 systemd 服务..."
sudo tee /etc/systemd/system/hello-siling-backend.service << 'EOF'
[Unit]
Description=Hello Siling Backend Service
After=network.target postgresql.service

[Service]
Type=simple
User=developer
Group=developer
WorkingDirectory=/home/developer/deploy/hello-siling/backend/current
Environment=PATH=/home/developer/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=DATABASE_URL=postgresql://legal_user:legal_password_123@localhost:5432/legal_docs_dev
Environment=MINIO_ENDPOINT=localhost:9000
Environment=MINIO_ACCESS_KEY=minioadmin
Environment=MINIO_SECRET_KEY=minioadmin
Environment=KAFKA_BOOTSTRAP_SERVERS=localhost:9092
Environment=GEMINI_API_KEY=your_api_key_here
ExecStart=/home/developer/.local/bin/uv run python -m app.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
sudo systemctl daemon-reload

# 创建日志目录
sudo mkdir -p /var/log/silicon-feature
sudo chown developer:developer /var/log/silicon-feature

# 设置防火墙 (如果使用 ufw)
if command -v ufw >/dev/null 2>&1; then
    echo "🔥 配置防火墙..."
    sudo ufw allow 22/tcp
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable
fi

# 创建环境变量文件模板
echo "📝 创建环境变量模板..."
tee ~/deploy/.env.template << 'EOF'
# 数据库配置
DATABASE_URL=postgresql://legal_user:legal_password_123@localhost:5432/legal_docs_dev

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Kafka 配置
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Gemini API 配置
GEMINI_API_KEY=your_api_key_here

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
EOF

echo "✅ 服务器设置完成！"
echo ""
echo "📋 下一步操作："
echo "1. 复制 env.template 到 .env 并配置实际的环境变量"
echo "2. 启动 PostgreSQL: sudo systemctl start postgresql"
echo "3. 配置 GitLab CI/CD 变量"
echo "4. 运行首次部署"
echo ""
echo "🔧 服务管理命令："
echo "- 查看后端服务状态: sudo systemctl status hello-siling-backend"
echo "- 启动后端服务: sudo systemctl start hello-siling-backend"
echo "- 停止后端服务: sudo systemctl stop hello-siling-backend"
echo "- 重启后端服务: sudo systemctl restart hello-siling-backend"
echo "- 查看日志: sudo journalctl -u hello-siling-backend -f"
