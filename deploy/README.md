# Hello Siling - Legal Docs MVP 部署指南

## 快速启动

### 1. 配置环境变量

```bash
# 复制环境变量模板
cp env.template .env

# 编辑 .env 文件，填入你的 Gemini API Key
nano .env
```

**必须配置的变量：**
- `GEMINI_API_KEY`: 你的 Google Gemini API 密钥

### 2. 启动服务

```bash
# 使用启动脚本（推荐）
./startup.sh
```

**启动脚本功能：**
- ✅ 自动检查 Docker 是否运行
- ✅ 自动检查端口占用并清理
- ✅ 验证环境变量配置
- ✅ 支持 Ctrl+C 自动清理服务
- ✅ 彩色日志输出

### 3. 访问服务

启动成功后，可以通过以下地址访问：

- **前端界面**: http://localhost:3000
- **后端 API**: http://localhost:8001
- **API 文档**: http://localhost:8001/docs
- **健康检查**: http://localhost:8001/health
- **就绪检查**: http://localhost:8001/ready
- **MinIO 控制台**: http://localhost:9001 (admin/password123)

### 4. 停止服务

- **方式一**: 在启动脚本运行的控制台按 `Ctrl+C`
- **方式二**: 手动执行 `docker-compose -f docker-compose.aliyun.yml down`

## 服务说明

### 核心服务
- **backend**: FastAPI 后端服务 (端口 8001)
- **frontend**: React 前端应用 (端口 3000)

### 依赖服务
- **postgres**: PostgreSQL 数据库 (端口 5432)
- **minio**: MinIO 对象存储 (端口 9000/9001)
- **redis**: Redis 缓存 (端口 6379)
- **redpanda**: Kafka 兼容消息队列 (端口 9092)

## 故障排除

### 端口占用问题
```bash
# 检查端口占用
lsof -i :5432 -i :6379 -i :9000 -i :9001 -i :9092 -i :8001 -i :3000

# 停止本地服务
brew services stop postgresql@14
brew services stop redis
pkill -f minio
```

### Docker 问题
```bash
# 清理 Docker 缓存
docker builder prune -a

# 重新构建镜像
docker-compose -f docker-compose.aliyun.yml build --no-cache
```

### 查看日志
```bash
# 查看所有服务日志
docker-compose -f docker-compose.aliyun.yml logs

# 查看特定服务日志
docker-compose -f docker-compose.aliyun.yml logs backend
docker-compose -f docker-compose.aliyun.yml logs frontend
```

## 开发模式

如果需要开发模式（文件监控），可以设置环境变量：

```bash
export RELOAD_MODE=true
./startup.sh
```

**注意**: 开发模式会启用文件监控，可能导致容器频繁重启，建议仅在开发时使用。

## 生产部署

生产环境部署时，建议：

1. 使用生产级数据库和存储服务
2. 配置适当的资源限制
3. 设置日志轮转
4. 配置监控和告警
5. 使用 HTTPS 和域名

## 支持

如有问题，请检查：
1. Docker Desktop 是否正常运行
2. 端口是否被占用
3. 环境变量是否正确配置
4. 网络连接是否正常
