#!/bin/bash
# 服务器初始化脚本
# 在服务器上运行此脚本来设置部署环境

set -e

echo "🚀 开始设置服务器部署环境..."

# 更新系统包
echo "📦 更新系统包..."
sudo apt update && sudo apt upgrade -y

# 安装必要的系统依赖
echo "🔧 安装系统依赖..."
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    nginx \
    postgresql \
    postgresql-contrib \
    curl \
    wget \
    git \
    htop \
    unzip \
    systemd

# 安装 uv (Python 包管理器)
echo "🐍 安装 uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

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

# 配置 Nginx
echo "🌐 配置 Nginx..."
sudo tee /etc/nginx/sites-available/hello-siling << 'EOF'
server {
    listen 80;
    server_name _;
    
    # 前端静态文件 - 调试界面
    location / {
        root /var/www/html/hello-siling;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    # 后端 API 代理
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 健康检查
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# 启用站点
sudo ln -sf /etc/nginx/sites-available/hello-siling /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

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
echo "1. 复制 .env.template 到 .env 并配置实际的环境变量"
echo "2. 启动 PostgreSQL: sudo systemctl start postgresql"
echo "3. 启动 Nginx: sudo systemctl start nginx"
echo "4. 配置 GitLab CI/CD 变量"
echo "5. 运行首次部署"
echo ""
echo "🔧 服务管理命令："
echo "- 查看后端服务状态: sudo systemctl status hello-siling-backend"
echo "- 启动后端服务: sudo systemctl start hello-siling-backend"
echo "- 停止后端服务: sudo systemctl stop hello-siling-backend"
echo "- 重启后端服务: sudo systemctl restart hello-siling-backend"
echo "- 查看日志: sudo journalctl -u hello-siling-backend -f"
