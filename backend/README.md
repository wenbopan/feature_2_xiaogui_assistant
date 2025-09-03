# 法律文档处理系统

一个基于FastAPI、Kafka、PostgreSQL和MinIO的法律文档处理系统，支持文件上传、内容提取和字段分类。

## 🏗️ 系统架构

### 技术栈
- **后端框架**: FastAPI (Python 3.11)
- **消息队列**: Apache Kafka (Redpanda)
- **数据库**: PostgreSQL
- **对象存储**: MinIO
- **AI服务**: Google Gemini API
- **数据验证**: Pydantic
- **gRPC协议**: 标准化文件类型枚举

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
- **回调服务**: 异步处理结果回调通知

## 🚀 快速开始

### 环境要求
- Python 3.11+
- uv (Python包管理器)
- Docker (用于PostgreSQL、MinIO、Redpanda)
- 或者本地安装PostgreSQL、MinIO、Redpanda

### 安装依赖
```bash
# 使用 uv 创建虚拟环境并安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
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

### 🔥 微服务核心API（单文件处理）

#### 单文件分类
- **端点**: `POST /api/v1/files/classify`
- **描述**: 对单个文件进行智能分类，支持异步回调
- **请求参数**:
  - `file`: 文件 (multipart/form-data)
  - `callback_url`: 回调URL (可选)
  - `file_id`: 文件ID (可选，用于关联回调)
  - `presigned_url`: 预签名URL (可选，用于文件上传)
- **响应**:
```json
{
  "message": "文件分类任务已发布",
  "file_id": "unique_file_id",
  "task_id": "task_uuid"
}
```
- **回调格式**:
```json
{
  "file_id": "unique_file_id",
  "file_type": 1,
  "is_recognized": 1
}
```

#### 单文件字段提取
- **端点**: `POST /api/v1/files/extract-fields`
- **描述**: 对单个文件进行字段提取，支持异步回调
- **请求参数**:
  - `file`: 文件 (multipart/form-data)
  - `callback_url`: 回调URL (可选)
  - `file_id`: 文件ID (可选，用于关联回调)
  - `presigned_url`: 预签名URL (可选，用于文件上传)
- **响应**:
```json
{
  "message": "字段提取任务已发布",
  "file_id": "unique_file_id",
  "task_id": "task_uuid"
}
```
- **回调格式**:
```json
{
  "file_id": "unique_file_id",
  "file_content": {
    "购买方名称": "张三",
    "开票日期": "2025-08-24",
    "含税金额": 1000.00
  },
  "is_extracted": 1
}
```

#### 回调结果查询 (自测用)
- **端点**: `GET /api/v1/callbacks/results/{file_id}`
- **描述**: 查询指定文件的所有回调结果
- **路径参数**: `file_id` (string)
- **响应**:
```json
{
  "results": [
    {
      "type": "classification",
      "timestamp": 1756809967.3720698,
      "data": {
        "file_id": "unique_file_id",
        "file_type": 1,
        "is_recognized": 1
      }
    },
    {
      "type": "extraction",
      "timestamp": 1756809968.1234567,
      "data": {
        "file_id": "unique_file_id",
        "file_content": {...},
        "is_extracted": 1
      }
    }
  ]
}
```

### 基础端点

#### 健康检查 (placeholder接口并没有实现真实health check)
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

### 批量处理API

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

### 提示词微调API

#### 获取指令配置
- **端点**: `GET /api/v1/config/instructions`
- **描述**: 获取当前指令配置（包含内存中的指令）
- **响应**:
```json
{
  "config": {
    "file_path": "config/instructions.yaml",
    "last_modified": "2025-08-24T20:00:00"
  },
  "memory_instructions": {
    "invoice": "发票分类指令...",
    "lease": "租赁合同分类指令...",
    "amendment": "合同修订分类指令...",
    "bill": "账单分类指令...",
    "bank_receipt": "银行回单分类指令..."
  }
}
```

#### 提示词in memory更新指令
- **端点**: `POST /api/v1/config/instructions/hot-swap`
- **描述**: 热交换指令（更新内存中的指令，无需重启服务）
- **请求参数**:
```json
{
  "invoice": "新的发票分类指令",
  "lease": "新的租赁合同分类指令",
  "amendment": "新的合同修订分类指令",
  "bill": "新的账单分类指令",
  "bank_receipt": "新的银行回单分类指令"
}
```
- **响应**:
```json
{
  "success": true,
  "message": "Instructions hot-swapped successfully",
  "config": {
    "file_path": "config/instructions.yaml",
    "last_modified": "2025-08-24T20:00:00"
  },
  "memory_instructions": {
    "invoice": "新的发票分类指令",
    "lease": "新的租赁合同分类指令",
    "amendment": "新的合同修订分类指令",
    "bill": "新的账单分类指令",
    "bank_receipt": "新的银行回单分类指令"
  },
  "last_modified": "2025-08-24T20:00:00"
}
```

#### 重置指令为原始配置
- **端点**: `POST /api/v1/config/instructions/reset`
- **描述**: 重置指令为原始配置文件中的内容
- **响应**:
```json
{
  "success": true,
  "message": "Instructions reset to original config successfully",
  "config": {
    "file_path": "config/instructions.yaml",
    "last_modified": "2025-08-24T20:00:00"
  },
  "memory_instructions": {
    "invoice": "原始发票分类指令",
    "lease": "原始租赁合同分类指令",
    "amendment": "原始合同修订分类指令",
    "bill": "原始账单分类指令",
    "bank_receipt": "原始银行回单分类指令"
  },
  "last_modified": "2025-08-24T20:00:00"
}
```

#### 获取指定分类的指令
- **端点**: `GET /api/v1/config/instructions/category/{category}`
- **描述**: 获取指定分类的指令内容
- **路径参数**: `category` (string) - 分类名称 (invoice, lease, amendment, bill, bank_receipt)
- **响应**:
```json
{
  "category": "invoice",
  "instruction": "发票分类指令内容..."
}
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
- `pyproject.toml`: 项目配置和依赖管理
- `uv.lock`: 依赖锁定文件
- `startup.sh`: 服务启动脚本
- `shutdown.sh`: 服务停止脚本

## 📁 项目结构

```
silicon_feature_2/
├── app/                    # 应用代码
│   ├── api/               # API路由
│   │   └── api.py        # 统一API路由
│   ├── models/            # 数据模型
│   │   ├── database.py    # 数据库模型
│   │   ├── schemas.py     # Pydantic模型
│   │   └── prompt_schemas.py # 提示词模型
│   ├── services/          # 业务服务
│   │   ├── file_service.py           # 文件处理服务
│   │   ├── simple_file_service.py   # 单文件处理服务
│   │   ├── gemini_service.py        # Gemini AI服务
│   │   ├── kafka_service.py         # Kafka服务
│   │   ├── callback_service.py      # 回调服务
│   │   ├── minio_service.py         # MinIO服务
│   │   └── processing_message_updater.py # 消息状态更新器
│   ├── consumers/         # Kafka消费者
│   │   ├── file_classification_consumer.py      # 批量文件分类消费者
│   │   ├── field_extraction_consumer.py         # 批量字段提取消费者
│   │   ├── simple_file_classification_consumer.py # 单文件分类消费者
│   │   └── simple_field_extraction_consumer.py   # 单文件字段提取消费者
│   ├── proto/             # gRPC协议文件
│   │   ├── common_pb2.py  # 生成的Python类
│   │   └── file_types.py  # 文件类型工具
│   └── main.py            # 应用入口
├── config/                # 配置文件
│   └── instructions.yaml  # 提示词配置
├── proto/                 # 原始proto文件
│   └── common.proto       # gRPC定义
├── logs/                  # 日志文件
├── utils/                 # 工具脚本
│   ├── clear_all_tables.sh # 数据库清理脚本
│   └── clean_restart_topic.sh # Kafka主题清理脚本
├── pyproject.toml         # 项目配置
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
6. **回调失败**: 检查回调URL是否可访问

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log
```