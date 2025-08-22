# Legal Docs MVP Application

一个基于FastAPI、Kafka、PostgreSQL和MinIO的法律文档处理系统，支持文件上传、内容提取和字段分类。

## 🏗️ 系统架构

### 技术栈
- **后端框架**: FastAPI (Python 3.11)
- **消息队列**: Apache Kafka (Redpanda)
- **数据库**: PostgreSQL
- **对象存储**: MinIO
- **AI服务**: Google Gemini API
- **数据验证**: Pydantic

### 架构组件
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App  │    │   Kafka/Redpanda│    │   PostgreSQL    │
│   (Port 8000)  │◄──►│   (Port 9092)   │    │   (Port 5432)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MinIO        │    │   Consumers     │    │   File Service  │
│   (Port 9000)  │    │   (Async)       │    │   (ZIP处理)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 核心服务
- **API服务**: FastAPI应用，提供RESTful接口
- **Kafka服务**: 消息发布和消费管理
- **字段提取服务**: 基于Gemini API的智能字段提取
- **内容处理服务**: 文件内容读取和分类
- **文件服务**: ZIP文件上传、解压和处理
- **存储服务**: MinIO对象存储管理

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Docker (用于PostgreSQL、MinIO、Redpanda)
- 或者本地安装PostgreSQL、MinIO、Redpanda

### 安装依赖
```bash
# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 启动服务
```bash
# 使用启动脚本（推荐）
./startup.sh

# 或手动启动
# 1. 启动PostgreSQL
# 2. 启动MinIO
# 3. 启动Redpanda
# 4. 启动FastAPI应用
python -m app.main
```

### 停止服务
```bash
./shutdown.sh
```

## 📚 API文档

### 基础端点
- **健康检查**: `GET /health`
- **就绪检查**: `GET /ready`
- **API文档**: `GET /docs` (Swagger UI)

### 任务管理
- **创建任务**: `POST /api/v1/tasks/`
- **获取任务**: `GET /api/v1/tasks/{task_id}`
- **任务列表**: `GET /api/v1/tasks/`

### 文件处理
- **上传文件**: `POST /api/v1/tasks/upload`
- **触发字段提取**: `POST /api/v1/tasks/{task_id}/extract-fields`
- **获取提取结果**: `GET /api/v1/tasks/{task_id}/extracted-fields`

### 请求示例

#### 创建任务
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "测试项目",
    "organize_date": "2025-08-22"
  }'
```

#### 上传文件
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/upload" \
  -F "file=@document.zip" \
  -F "task_id=1"
```

#### 触发字段提取
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/1/extract-fields" \
  -H "Content-Type: application/json"
```

## 🔄 消息队列

### Kafka Topics
- **field.extraction**: 字段提取任务
- **file.processing**: 文件处理任务

### 消息格式
```json
{
  "metadata": {
    "id": "uuid",
    "timestamp": 1234567890.123,
    "key": "optional_key",
    "source": "service_name"
  },
  "data": {
    "type": "field_extraction_job",
    "job_id": "uuid",
    "task_id": 1,
    "file_id": 1,
    "s3_key": "path/to/file",
    "file_type": "pdf",
    "filename": "document.pdf"
  }
}
```

## 🗄️ 数据库设计

### 核心表
- **tasks**: 任务信息
- **file_metadata**: 文件元数据
- **file_classifications**: 文件分类结果
- **field_extractions**: 字段提取结果
- **processing_messages**: 消息处理状态

### 关系模型
```
Task (1) ── (N) FileMetadata (1) ── (N) FileClassification
                                    (1) ── (N) FieldExtraction
```

## 🔧 配置

### 环境变量
```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/legal_docs_dev

# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Kafka配置
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Gemini API配置
GEMINI_API_KEY=your_api_key_here
```

### 配置文件
- `app/config.py`: 应用配置
- `requirements.txt`: Python依赖
- `startup.sh`: 服务启动脚本
- `shutdown.sh`: 服务停止脚本

## 📁 项目结构

```
silicon_feature_2/
├── app/                    # 应用代码
│   ├── api/               # API路由
│   ├── models/            # 数据模型
│   ├── services/          # 业务服务
│   └── main.py            # 应用入口
├── design/                 # 设计文档
├── logs/                   # 日志文件
├── scripts/                # 脚本文件
├── requirements.txt        # Python依赖
├── startup.sh             # 启动脚本
├── shutdown.sh            # 停止脚本
└── README.md              # 项目文档
```

## 🚀 部署

### 开发环境
```bash
# 克隆仓库
git clone https://github.com/wenbopan/feature_2_xiaogui_assistant.git
cd feature_2_xiaogui_assistant

# 启动服务
./startup.sh

# 访问应用
# http://localhost:8000/docs
```

### 生产环境
- 使用Docker Compose部署
- 配置环境变量
- 设置日志轮转
- 配置监控和告警

## 🐛 故障排除

### 常见问题
1. **端口冲突**: 检查8000、9000、9092、5432端口是否被占用
2. **数据库连接失败**: 确认PostgreSQL服务状态
3. **MinIO连接失败**: 检查MinIO服务状态和配置
4. **Kafka连接失败**: 确认Redpanda服务状态

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看启动日志
./startup.sh
```

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用MIT许可证。

## 📞 联系方式

- GitHub: [@wenbopan](https://github.com/wenbopan)
- 项目地址: [feature_2_xiaogui_assistant](https://github.com/wenbopan/feature_2_xiaogui_assistant)
