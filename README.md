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

## 📚 完整API文档

### 基础端点

#### 健康检查
- **端点**: `GET /health`
- **描述**: 简单健康检查接口
- **响应**:
```json
{
  "status": "healthy",
  "timestamp": "2025-02-18T00:00:00Z",
  "version": "1.0.0"
}
```

#### API文档
- **端点**: `GET /docs`
- **描述**: Swagger UI交互式API文档

### 任务管理API

#### 创建任务
- **端点**: `POST /api/v1/tasks/`
- **描述**: 创建新的文档处理任务
- **请求参数**:
```json
{
  "project_name": "项目名称",
  "organize_date": "2025-08-22",  // 可选，格式：YYYY-MM-DD
  "options": {}  // 可选，任务选项
}
```
- **响应模型**: `TaskResponse`
```json
{
  "id": 1,
  "project_name": "项目名称",
  "organize_date": "2025-08-22",
  "status": "created",
  "options": {},
  "created_at": "2025-08-24T20:00:00",
  "updated_at": null
}
```

#### 获取任务列表
- **端点**: `GET /api/v1/tasks/`
- **描述**: 获取所有任务的列表
- **响应**: `List[TaskResponse]`

#### 获取单个任务
- **端点**: `GET /api/v1/tasks/{task_id}`
- **描述**: 根据任务ID获取任务详情
- **路径参数**: `task_id` (int)
- **响应**: `TaskResponse`

#### 删除任务
- **端点**: `DELETE /api/v1/tasks/{task_id}`
- **描述**: 删除指定任务及其相关数据
- **路径参数**: `task_id` (int)
- **响应**: 成功消息

### 文件处理API

#### 上传ZIP文件
- **端点**: `POST /api/v1/tasks/{task_id}/upload`
- **描述**: 上传ZIP文件到指定任务
- **路径参数**: `task_id` (int)
- **表单参数**: 
  - `file`: ZIP文件 (UploadFile)
- **响应模型**: `FileUploadResponse`
```json
{
  "task_id": 1,
  "upload_id": "uuid",
  "filename": "document.zip",
  "size": 1024000,
  "status": "uploaded",
  "details": {
    "extracted_files": 159,
    "extraction_failures": 0,
    "extraction_status": "extraction_success"
  }
}
```

#### 触发内容处理
- **端点**: `POST /api/v1/tasks/{task_id}/process`
- **描述**: 触发AI内容提取、分类和重命名
- **路径参数**: `task_id` (int)
- **响应**: 处理任务创建结果
```json
{
  "task_id": 1,
  "total_files": 159,
  "status": "processing_started",
  "message": "Successfully created 159 content processing jobs"
}
```

#### 获取处理进度
- **端点**: `GET /api/v1/tasks/{task_id}/processing-progress`
- **描述**: 获取内容处理任务的进度
- **路径参数**: `task_id` (int)
- **查询参数**: `include_details` (bool, 可选)
- **响应**:
```json
{
  "task_id": 1,
  "topic": "file.processing",
  "total_jobs": 159,
  "status_breakdown": {
    "created": 0,
    "consumed": 0,
    "processing": 0,
    "completed": 159,
    "failed": 0
  },
  "progress_percentage": 100.0,
  "completed_jobs": 159,
  "failed_jobs": 0,
  "last_updated": "2025-08-24T20:03:20.050771"
}
```

#### 获取任务文件列表
- **端点**: `GET /api/v1/tasks/{task_id}/files`
- **描述**: 获取任务中的所有文件
- **路径参数**: `task_id` (int)
- **响应**: `List[FileMetadataResponse]`

#### 获取分类结果
- **端点**: `GET /api/v1/tasks/{task_id}/classifications`
- **描述**: 获取任务的文件分类结果
- **路径参数**: `task_id` (int)
- **响应**: `List[ClassificationResult]`

#### 获取处理结果
- **端点**: `GET /api/v1/tasks/{task_id}/results`
- **描述**: 获取任务的完整处理结果
- **路径参数**: `task_id` (int)
- **响应**: `ProcessingResult`

### 字段提取API

#### 触发字段提取
- **端点**: `POST /api/v1/tasks/{task_id}/extract-fields`
- **描述**: 触发基于原始文件的字段提取
- **路径参数**: `task_id` (int)
- **响应**:
```json
{
  "task_id": 1,
  "total_jobs": 159,
  "failed_jobs": 0,
  "failed_files": [],
  "status": "jobs_created",
  "message": "Successfully created 159 field extraction jobs"
}
```

#### 获取字段提取结果
- **端点**: `GET /api/v1/tasks/{task_id}/extracted-fields`
- **描述**: 获取字段提取的完整结果
- **路径参数**: `task_id` (int)
- **响应**:
```json
{
  "task_id": 1,
  "total_files": 159,
  "results_by_category": {
    "发票": [
      {
        "file_id": 1,
        "original_filename": "发票.pdf",
        "final_filename": "发票_001.pdf",
        "category": "发票",
        "classification_confidence": 0.95,
        "extraction_status": "completed",
        "extraction_data": {
          "购买方名称": "张三",
          "开票日期": "2025-08-24",
          "含税金额": 1000.00
        },
        "missing_fields": [],
        "extraction_confidence": 0.9,
        "extraction_method": "gemini"
      }
    ]
  }
}
```

#### 获取字段提取进度
- **端点**: `GET /api/v1/tasks/{task_id}/extraction-progress`
- **描述**: 获取字段提取任务的进度
- **路径参数**: `task_id` (int)
- **查询参数**: `include_details` (bool, 可选)
- **响应**: 与处理进度格式相同，但topic为"field.extraction"

### 文件下载API

#### 下载处理结果
- **端点**: `GET /api/v1/tasks/{task_id}/download`
- **描述**: 下载任务的处理结果ZIP文件
- **路径参数**: `task_id` (int)
- **响应**: ZIP文件流

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
- **file_extraction_failures**: 字段提取失败记录

### 关系模型
```
Task (1) ── (N) FileMetadata (1) ── (N) FileClassification
                                    (1) ── (N) FieldExtraction
                                    (1) ── (N) FileExtractionFailure
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
│   │   ├── tasks.py       # 任务管理API
│   │   └── extractions.py # 字段提取API
│   ├── models/            # 数据模型
│   │   ├── database.py    # 数据库模型
│   │   └── schemas.py     # Pydantic模型
│   ├── services/          # 业务服务
│   │   ├── file_service.py           # 文件处理服务
│   │   ├── gemini_service.py        # Gemini AI服务
│   │   ├── kafka_service.py         # Kafka服务
│   │   ├── kafka_consumer.py        # Kafka消费者
│   │   ├── field_extraction_consumer.py # 字段提取消费者
│   │   ├── content_processor.py     # 内容处理器
│   │   ├── minio_service.py         # MinIO服务
│   │   └── processing_message_updater.py # 消息状态更新器
│   └── main.py            # 应用入口
├── design/                 # 设计文档
├── logs/                   # 日志文件
├── utils/                  # 工具脚本
│   └── clear_all_tables.sh # 数据库清理脚本
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
5. **API阻塞**: 检查Kafka消费者是否阻塞事件循环

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
