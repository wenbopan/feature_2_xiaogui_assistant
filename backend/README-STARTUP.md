# Legal Docs MVP - Startup Guide

## 🚀 快速启动

这个项目包含了完整的startup和testing工具链，让你可以一键启动所有依赖服务并验证系统状态。

### 📋 系统要求

- Python 3.11+
- PostgreSQL
- Redpanda (Kafka兼容)
- MinIO
- 虚拟环境 (venv)

### 🛠️ 脚本说明

#### 1. `startup.sh` - 统一启动脚本
完整启动所有依赖服务和应用：

```bash
./startup.sh
```

**启动流程：**
1. ✅ 检查系统依赖 (Python, PostgreSQL, Redpanda, curl)
2. ✅ 验证虚拟环境和Python依赖
3. ✅ 启动PostgreSQL数据库
4. ✅ 启动MinIO对象存储
5. ✅ 启动Redpanda (Kafka集群)
6. ✅ 启动FastAPI应用
7. ✅ 执行Readiness检查
8. ✅ 显示服务状态和访问URL

#### 2. `shutdown.sh` - 统一停止脚本
停止所有服务：

```bash
./shutdown.sh
```

**停止流程：**
1. 🛑 停止FastAPI应用
2. 🛑 停止Redpanda集群
3. 🛑 停止MinIO服务
4. 📋 显示PostgreSQL状态
5. 🧹 清理日志和PID文件

#### 3. `test-integration.sh` - 集成测试脚本
验证所有服务功能：

```bash
./test-integration.sh
```

**测试内容：**
- 🔍 API端点测试
- 🔍 Readiness检查验证
- 🔍 服务连接性测试
- 🔍 数据库连接测试
- 🔍 Kafka集群健康检查
- 🔍 MinIO存储测试

### 📊 服务端口

| 服务 | 端口 | 访问地址 |
|------|------|----------|
| FastAPI | 8000 | http://localhost:8000 |
| API文档 | 8000 | http://localhost:8000/docs |
| Health | 8000 | http://localhost:8000/health |
| Readiness | 8000 | http://localhost:8000/ready |
| PostgreSQL | 5432 | localhost:5432 |
| Redpanda | 9092 | localhost:9092 |
| MinIO | 9000 | http://localhost:9000 |
| MinIO控制台 | 9001 | http://localhost:9001 |

### 🔧 使用流程

#### 首次启动
```bash
# 1. 启动所有服务
./startup.sh

# 2. 运行集成测试验证
./test-integration.sh

# 3. 开始开发/测试
# 访问 http://localhost:8000/docs 查看API文档
```

#### 日常开发
```bash
# 启动服务
./startup.sh

# 查看应用日志
tail -f app.log

# 停止服务
./shutdown.sh
```

### 📝 重要文件

- `app.log` - 应用运行日志
- `app.pid` - 应用进程ID
- `.env` - 环境配置文件

### 🔍 故障排除

#### 1. 启动失败
```bash
# 查看详细错误信息
./startup.sh

# 检查端口占用
lsof -i :8000
lsof -i :5432
lsof -i :9092
lsof -i :9000
```

#### 2. Readiness检查失败
```bash
# 查看详细readiness状态
curl -s http://localhost:8000/ready | python -m json.tool

# 检查各个服务状态
curl -s http://localhost:8000/kafka-status | python -m json.tool
```

#### 3. 数据库连接问题
```bash
# 测试数据库连接
psql -h localhost -p 5432 -U $USER -d legal_docs_dev -c "SELECT 1"

# 创建数据库（如果不存在）
createdb legal_docs_dev
```

#### 4. Kafka连接问题
```bash
# 检查Redpanda集群状态
rpk cluster health

# 查看Kafka配置
rpk cluster info
```

### 🎯 API测试示例

#### 基础健康检查
```bash
# 简单健康检查
curl http://localhost:8000/health

# 完整readiness检查
curl http://localhost:8000/ready

# Kafka服务状态
curl http://localhost:8000/kafka-status
```

#### 任务管理
```bash
# 获取任务列表
curl http://localhost:8000/api/v1/tasks

# 查看API文档
open http://localhost:8000/docs
```

### 🚧 开发模式

如果需要在开发模式下运行（自动重载）：

```bash
# 手动启动依赖服务
./startup.sh

# 停止自动启动的应用
kill $(cat app.pid)

# 以开发模式启动应用
source venv/bin/activate
python -m app.main
```

### 📈 监控和日志

- **应用日志**: `tail -f app.log`
- **系统状态**: `curl http://localhost:8000/ready`
- **Kafka状态**: `rpk cluster health`
- **数据库状态**: `psql -h localhost -p 5432 -U $USER -d legal_docs_dev -c "SELECT 1"`

---

## 🎉 快速开始

1. **一键启动**: `./startup.sh`
2. **验证服务**: `./test-integration.sh`  
3. **开始开发**: 访问 http://localhost:8000/docs

就这么简单！🚀
