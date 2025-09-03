# Hello Siling Classify and Extract 部署指南

## 📋 部署方式

本项目使用简单的服务器部署方式：
- **传统服务器部署** - 使用 systemd 和 nginx

## 🖥️ 传统服务器部署

### 1. 服务器初始化

在服务器 `47.98.154.221` 上运行初始化脚本：

```bash
# 登录服务器
ssh developer@47.98.154.221

# 运行初始化脚本
chmod +x deploy/setup_server.sh
./deploy/setup_server.sh
```

### 2. 配置环境变量

复制并编辑环境变量文件：

```bash
cp ~/deploy/.env.template ~/deploy/.env
nano ~/deploy/.env
```

更新以下配置：
- `DATABASE_URL` - PostgreSQL 连接字符串
- `GEMINI_API_KEY` - Google Gemini API 密钥
- 其他服务配置

### 3. GitLab CI/CD 配置

在 GitLab 项目中设置以下 CI/CD 变量：

#### 必需变量
- `SSH_PRIVATE_KEY` - 服务器 SSH 私钥
- `DATABASE_URL` - 数据库连接字符串
- `GEMINI_API_KEY` - Gemini API 密钥

#### 可选变量
- `MINIO_ENDPOINT` - MinIO 服务地址
- `MINIO_ACCESS_KEY` - MinIO 访问密钥
- `MINIO_SECRET_KEY` - MinIO 秘密密钥
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka 服务地址

### 4. 部署流程

1. **推送代码到 main 分支**
2. **在 GitLab CI/CD 页面手动触发部署**：
   - `deploy_backend` - 部署后端服务
   - `deploy_frontend` - 部署前端调试界面
   - `rollback_backend` - 回滚后端
   - `rollback_frontend` - 回滚前端

### 5. 服务管理

```bash
# 查看后端服务状态
sudo systemctl status hello-siling-backend

# 重启后端服务
sudo systemctl restart hello-siling-backend

# 查看日志
sudo journalctl -u hello-siling-backend -f

# 查看 Nginx 状态
sudo systemctl status nginx
```



## 🔧 部署架构

### 服务器部署架构
```
┌─────────────────┐    ┌─────────────────┐
│     Nginx       │    │   Backend       │
│   (Port 80)     │◄──►│  (Port 8000)    │
│  Frontend +     │    │  FastAPI        │
│  API Proxy      │    │  Python 3.11    │
└─────────────────┘    └─────────────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  Static Files   │    │  PostgreSQL     │
│ /var/www/html/  │    │  MinIO          │
│ hello-siling-   │    │  Kafka/Redpanda │
│ classify-and-   │    │                 │
│ extract/        │    │                 │
└─────────────────┘    └─────────────────┘
```

## 🚀 部署特性

### 独立部署
- **后端独立部署** - API 服务，供其他服务调用
- **前端独立部署** - 调试界面，独立于后端

### 高可用性
- **自动重启** - systemd 自动重启失败的服务
- **健康检查** - 定期检查服务状态
- **服务监控** - 通过 systemd 监控服务状态

### 回滚支持
- **自动备份** - 每次部署前自动备份
- **一键回滚** - 支持快速回滚到上一版本
- **独立回滚** - 前端和后端可独立回滚

## 📊 监控和日志

### 服务器部署
```bash
# 查看服务状态
sudo systemctl status hello-siling-classify-and-extract-backend

# 查看实时日志
sudo journalctl -u hello-siling-classify-and-extract-backend -f

# 查看 Nginx 访问日志
sudo tail -f /var/log/nginx/access.log
```

## 🔒 安全注意事项

1. **SSH 密钥管理** - 使用专用部署密钥
2. **环境变量** - 敏感信息使用 GitLab CI/CD 变量
3. **网络访问** - 限制不必要的端口访问
4. **定期更新** - 保持系统和依赖更新

## 🆘 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 检查日志
   sudo journalctl -u hello-siling-backend -n 50
   
   # 检查端口占用
   sudo netstat -tlnp | grep :8000
   ```

2. **数据库连接失败**
   ```bash
   # 检查 PostgreSQL 状态
   sudo systemctl status postgresql
   
   # 测试连接
   psql -h localhost -U legal_user -d legal_docs_dev
   ```

3. **前端无法访问**
   ```bash
   # 检查 Nginx 配置
   sudo nginx -t
   
   # 检查文件权限
   ls -la /var/www/html/hello-siling/
   ```

### 联系支持

如果遇到问题，请检查：
1. 服务日志
2. 系统资源使用情况
3. 网络连接状态
4. 配置文件语法
