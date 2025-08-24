from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# 任务相关模型
class TaskCreate(BaseModel):
    project_name: str = Field(..., description="项目名称")
    organize_date: Optional[str] = Field(None, description="整理日期 YYYY-MM-DD")
    options: Optional[Dict[str, Any]] = Field(None, description="任务选项")

class TaskResponse(BaseModel):
    id: int
    project_name: str
    organize_date: Optional[str]
    status: str
    options: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class TaskStatus(BaseModel):
    id: int
    status: str
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    progress_percentage: float = 0.0

# 文件上传相关模型
class FileUploadResponse(BaseModel):
    task_id: int
    upload_id: str
    filename: str
    size: int
    status: str
    details: Optional[Dict[str, Any]] = Field(None, description="处理详情")

class FileMetadataResponse(BaseModel):
    id: int
    original_filename: str
    relative_path: Optional[str]
    file_type: str
    file_size: int
    content_reading_status: str
    content_reading_error: Optional[str]
    
    class Config:
        from_attributes = True

# 分类结果模型
class ClassificationResult(BaseModel):
    id: int
    category: str
    confidence: float
    final_filename: str
    classification_method: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# 字段提取相关模型
class ExtractionTaskCreate(BaseModel):
    task_id: int
    options: Optional[Dict[str, Any]] = Field(None, description="提取选项")

class FieldExtractionResult(BaseModel):
    id: int
    extraction_data: Dict[str, Any]
    missing_fields: Optional[List[str]]
    extraction_method: str
    confidence: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True

# 处理结果模型
class ProcessingResult(BaseModel):
    task_id: int
    status: str
    total_files: int
    classified_files: int
    unrecognized_files: int
    failed_files: int
    classifications: List[ClassificationResult]
    unrecognized_files_list: List[FileMetadataResponse]

# 错误响应模型
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# 进度更新模型
class ProgressUpdate(BaseModel):
    task_id: int
    stage: str  # upload, unzip, classify, extract
    current: int
    total: int
    percentage: float
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

# 文件分类配置模型
class CategoryConfig(BaseModel):
    """文件分类配置"""
    name: str
    display_name: str
    description: str
    confidence_threshold: float = 0.6
    extraction_fields: List[str]

# 预定义的分类配置
CATEGORY_CONFIGS = {
    "发票": CategoryConfig(
        name="发票",
        display_name="发票",
        description="各类发票文档",
        confidence_threshold=0.6,
        extraction_fields=["购买方名称", "开票日期", "含税金额", "所属租期", "租赁(计费)面积", "楼栋&房号"]
    ),
    "租赁协议": CategoryConfig(
        name="租赁协议",
        display_name="租赁协议",
        description="物业租赁协议文档",
        confidence_threshold=0.6,
        extraction_fields=["承租人名称", "楼栋&房号", "租赁(计费)面积", "租赁期起止", "免租期条款"]
    ),
    "变更/解除协议": CategoryConfig(
        name="变更/解除协议",
        display_name="变更/解除协议",
        description="租赁变更或解除协议",
        confidence_threshold=0.6,
        extraction_fields=["承租人名称", "楼栋&房号", "租赁(计费)面积", "涉及租赁期、免租期、账期、押金条款的变更情况", "涉及租金条款的变更情况"]
    ),
    "账单": CategoryConfig(
        name="账单",
        display_name="账单",
        description="各类账单文档",
        confidence_threshold=0.6,
        extraction_fields=["承租人名称", "楼栋&房号", "含税金额", "所属租期"]
    ),
    "银行回单": CategoryConfig(
        name="银行回单",
        display_name="银行回单",
        description="银行转账回单",
        confidence_threshold=0.6,
        extraction_fields=["付款人名称", "流水日期", "转账金额", "所属租期", "楼栋&房号"]
    )
}

# Kafka消息相关模型
class KafkaMessageMetadata(BaseModel):
    """Kafka消息元数据"""
    id: str = Field(..., description="消息唯一标识")
    timestamp: float = Field(..., description="消息时间戳")
    key: Optional[str] = Field(None, description="消息键")
    source: str = Field(..., description="消息来源")

class KafkaJobData(BaseModel):
    """Kafka任务数据基类"""
    type: str = Field(..., description="任务类型")
    job_id: str = Field(..., description="任务ID")
    task_id: int = Field(..., description="任务ID")
    file_id: int = Field(..., description="文件ID")
    s3_key: str = Field(..., description="S3存储键")
    file_type: str = Field(..., description="文件类型")
    filename: str = Field(..., description="文件名")

class FieldExtractionJobMessage(KafkaJobData):
    """字段提取任务消息"""
    type: str = Field("field_extraction_job", description="消息类型")

class ContentExtractionJobMessage(KafkaJobData):
    """内容提取任务消息"""
    type: str = Field("content_extraction_job", description="消息类型")

class KafkaMessage(BaseModel):
    """Kafka消息包装器"""
    metadata: KafkaMessageMetadata
    data: KafkaJobData
