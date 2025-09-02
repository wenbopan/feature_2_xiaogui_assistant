from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
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

# 文件元数据模型
class FileMetadataResponse(BaseModel):
    id: int
    original_filename: str
    relative_path: Optional[str]
    file_type: str
    file_size: int
    logical_filename: Optional[str]
    extracted_fields: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True

# 文件上传相关模型
class FileUploadResponse(BaseModel):
    task_id: int
    uploaded_files: List[Dict[str, Any]]  # Simplified for ZIP processing results
    failed_files: List[Dict[str, Any]]
    total_files: int
    success_count: int
    failure_count: int

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

# Single file processing schemas
class SingleFileJobData(BaseModel):
    """单个文件任务数据基类"""
    type: str = Field(..., description="任务类型")
    job_id: str = Field(..., description="任务ID")
    task_id: str = Field(..., description="任务ID (UUID)")
    file_id: Optional[str] = Field(None, description="前端提供的文件ID")
    file_type: str = Field(..., description="文件类型")
    callback_url: Optional[str] = Field(None, description="回调URL")
    created_at: str = Field(..., description="创建时间")
    delivery_method: str = Field("minio", description="文件传递方式")

class SingleFileClassificationJobData(SingleFileJobData):
    """单个文件分类任务数据"""
    type: str = Field("single_file_classification_job", description="消息类型")
    s3_key: Optional[str] = Field(None, description="MinIO S3存储键")
    presigned_url: Optional[str] = Field(None, description="预签名URL")
    
    @field_validator('s3_key', 'presigned_url')
    @classmethod
    def validate_delivery_method(cls, v, values):
        """验证至少有一种文件传递方式"""
        if not v and not values.data.get('presigned_url') and not values.data.get('s3_key'):
            raise ValueError("Either s3_key or presigned_url must be provided")
        return v

class SingleFileExtractionJobData(SingleFileJobData):
    """单个文件字段提取任务数据"""
    type: str = Field("single_file_extraction_job", description="消息类型")
    s3_key: Optional[str] = Field(None, description="MinIO S3存储键")
    presigned_url: Optional[str] = Field(None, description="预签名URL")
    
    @field_validator('s3_key', 'presigned_url')
    @classmethod
    def validate_delivery_method(cls, v, values):
        """验证至少有一种文件传递方式"""
        if not v and not values.data.get('presigned_url') and not values.data.get('s3_key'):
            raise ValueError("Either s3_key or presigned_url must be provided")
        return v

class SingleFileKafkaMessage(BaseModel):
    """单个文件Kafka消息包装器"""
    id: str = Field(..., description="消息唯一标识")
    timestamp: float = Field(..., description="消息时间戳")
    key: Optional[str] = Field(None, description="消息键")
    data: Union[SingleFileClassificationJobData, SingleFileExtractionJobData]

# 文件内容查询响应模型
class FileContentResponse(BaseModel):
    """文件内容和提取结果响应模型"""
    task_id: int = Field(..., description="任务ID")
    original_filename: str = Field(..., description="原始文件名")
    relative_path: str = Field(..., description="相对路径")
    file_download_url: Optional[str] = Field(None, description="文件下载URL")
    content_type: str = Field(..., description="文件MIME类型")
    file_size: int = Field(..., description="文件大小（字节）")
    extracted_fields: Optional[Dict[str, Any]] = Field(None, description="提取的字段数据")
    final_filename: Optional[str] = Field(None, description="最终文件名")
    extraction_status: str = Field(..., description="提取状态：pending/completed/failed")
    extraction_error: Optional[str] = Field(None, description="提取错误信息（仅在失败时）")
    
    class Config:
        from_attributes = True


