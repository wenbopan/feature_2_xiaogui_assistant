# Docker 架构设计文档

## 项目概述

本项目是一个基于 FastAPI 的法律文档智能整理与字段提取系统，使用 Docker 容器化部署，支持开发和生产两种环境。

## 目录结构设计

```
legal-docs-mvp/
├── docker/                          # Docker 相关配置
│   ├── Dockerfile                   # FastAPI 应用容器构建
│   ├── dev/                         # 开发环境配置
│   │   ├── docker-compose.yml      # 开发环境服务编排
│   │   └── .env                     # 开发环境变量
│   └── prod/                        # 生产环境配置
│       ├── docker-compose.yml      # 生产环境服务编排
│       └── .env                     # 生产环境变量
├── scripts/                         # 启动和管理脚本
│   ├── dev-e2e.sh                  # E2E 自动化启动脚本
│   └── lib/                         # 脚本共享库
│       ├── common.sh               # 通用函数库
│       ├── health-check.sh         # 健康检查逻辑
│       └── docker-utils.sh         # Docker 操作封装
├── app/                             # 应用代码
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # 配置管理
│   ├── models/                     # 数据模型
│   ├── api/                        # API 路由
│   └── services/                   # 业务服务
└── design/                          # 设计文档
    └── docker-architecture.md      # 本文档
```

## 服务架构设计

### 核心服务

1. **PostgreSQL** - 关系数据库
   - 存储任务、文件元数据、分类结果等
   - 支持连接池和性能优化
   - 数据持久化到宿主机

2. **MinIO** - 对象存储服务
   - S3 兼容的 API
   - 存储上传的 ZIP 文件和提取的文档
   - 支持版本控制和生命周期管理

3. **Redpanda** - 消息队列服务
   - Kafka 兼容的 API
   - 处理文件上传、分类、提取等异步任务
   - 支持消息持久化和重试机制

4. **FastAPI 应用** - 主应用服务
   - 提供 REST API 接口
   - 集成 Gemini AI 服务
   - 处理文件上传和业务逻辑

### 网络架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MinIO         │    │   Redpanda      │    │   PostgreSQL    │
│   Port: 9000    │    │   Port: 9092    │    │   Port: 5432    │
│   (对象存储)     │    │   (消息队列)     │    │   (关系数据库)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   FastAPI App   │
                    │   (主应用)      │
                    │   Port: 8000    │
                    └─────────────────┘
```

## 环境配置策略

### 开发环境 (dev)

**特点：**
- 端口映射到宿主机，便于本地访问和调试
- 详细日志输出
- 开发工具集成
- 数据持久化到本地目录

**配置：**
```yaml
# docker/dev/docker-compose.yml
services:
  postgres:
    ports:
      - "5432:5432"  # 本地可访问
  minio:
    ports:
      - "9000:9000"  # 本地可访问
  kafka:
    ports:
      - "9092:9092"  # 本地可访问
  app:
    ports:
      - "8000:8000"  # 本地可访问
```

### 生产环境 (prod)

**特点：**
- 内部网络，不暴露端口
- 优化的资源配置
- 最小化日志
- 数据备份和恢复策略

**配置：**
```yaml
# docker/prod/docker-compose.yml
services:
  postgres:
    # 无端口映射，只能内部访问
  minio:
    # 无端口映射，只能内部访问
  kafka:
    # 无端口映射，只能内部访问
  app:
    # 无端口映射，只能内部访问
```

## 脚本设计

### E2E 脚本 (dev-e2e.sh)

**功能：**
- 自动化启动/停止/重启环境
- 服务健康检查
- 错误处理和退出码管理
- 支持不同环境配置

**使用方式：**
```bash
# 启动开发环境
./scripts/dev-e2e.sh start --env=dev --log-level=info

# 启动生产环境
./scripts/dev-e2e.sh start --env=prod --log-level=warn

# 查看服务状态
./scripts/dev-e2e.sh status --env=dev

# 停止环境
./scripts/dev-e2e.sh stop --env=dev

# 重置环境
./scripts/dev-e2e.sh reset --env=dev
```

### 共享库设计

**common.sh**
- 配置加载和环境变量管理
- 统一日志格式和级别控制
- 错误处理和退出码管理
- 通用工具函数

**health-check.sh**
- 服务就绪检查逻辑
- 依赖服务状态监控
- 超时和重试机制
- 健康检查结果报告

**docker-utils.sh**
- Docker 操作封装
- 容器状态查询
- 日志收集和管理
- 网络配置管理

## 配置管理

### 环境变量分层

1. **基础配置** (.env.base)
   - 服务地址、端口等通用配置
   - 数据库连接参数
   - API 密钥配置

2. **环境特定配置** (.env.dev, .env.prod)
   - 环境特定的参数
   - 日志级别配置
   - 性能调优参数

3. **运行时配置**
   - 命令行参数覆盖
   - 动态配置更新
   - 配置验证和错误检查

### 配置加载顺序

```
1. 加载 .env.base (基础配置)
2. 加载 .env.{env} (环境特定配置)
3. 加载命令行参数 (最高优先级)
4. 验证配置完整性
5. 应用配置到 docker-compose
```

## 健康检查机制

### 服务级健康检查

**PostgreSQL**
- 数据库连接测试
- 查询响应时间检查
- 连接池状态监控

**MinIO**
- API 端点响应检查
- 存储桶访问测试
- 文件操作测试

**Redpanda**
- Broker 状态检查
- 主题创建测试
- 消息发送/接收测试

**FastAPI 应用**
- 健康检查端点
- 依赖服务连接状态
- 内部服务状态

### 应用级健康检查

**启动顺序控制**
```
1. 启动基础设施服务 (PostgreSQL, MinIO, Redpanda)
2. 等待服务健康检查通过
3. 启动应用服务
4. 验证应用就绪状态
```

**故障恢复策略**
- 服务启动失败时自动重试
- 依赖服务不可用时等待重试
- 配置错误时显示详细错误信息
- 资源不足时提供解决建议

## 数据持久化策略

### 开发环境
- PostgreSQL 数据：`./data/postgres/`
- MinIO 数据：`./data/minio/`
- Redpanda 数据：`./data/redpanda/`
- 应用日志：`./logs/`

### 生产环境
- 使用 Docker volumes 或外部存储
- 定期备份策略
- 数据恢复机制
- 监控和告警

## 扩展性考虑

### 后续功能扩展
- Interactive 脚本（用户交互界面）
- 多环境支持（staging, testing）
- 监控和指标收集
- CI/CD 集成
- Kubernetes 部署支持

### 性能优化
- 服务资源限制和优化
- 连接池配置
- 缓存策略
- 负载均衡

## 安全考虑

### 开发环境
- 本地网络访问
- 开发工具集成
- 调试信息输出

### 生产环境
- 网络隔离
- 访问控制
- 数据加密
- 审计日志

---

*本文档记录了 Docker 架构设计的核心内容，后续实施过程中可能会根据实际情况进行调整和完善。*
