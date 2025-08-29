from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# 基础字段类型定义
class BaseExtractionFields(BaseModel):
    """基础提取字段"""
    pass

class InvoiceFields(BaseExtractionFields):
    """发票字段"""
    购买方名称: Optional[str] = Field(None, description="购买方名称")
    开票日期: Optional[str] = Field(None, description="开票日期，格式：YYYY-MM-DD")
    含税金额: Optional[float] = Field(None, description="含税金额，数字格式")
    所属租期: Optional[str] = Field(None, description="所属租期")
    楼栋房号: Optional[str] = Field(None, description="楼栋&房号")
    发票号码: Optional[str] = Field(None, description="发票号码")
    备注: Optional[str] = Field(None, description="备注信息")
    税率: Optional[float] = Field(None, description="税率，数字格式")

class LeaseAgreementFields(BaseExtractionFields):
    """租赁协议字段"""
    承租人名称: Optional[str] = Field(None, description="承租人名称")
    楼栋房号: Optional[str] = Field(None, description="楼栋&房号")
    租赁计费面积: Optional[float] = Field(None, description="租赁(计费)面积，数字格式")
    租赁期起止: Optional[str] = Field(None, description="租赁期起止")
    免租期条款: Optional[str] = Field(None, description="免租期条款")
    租金条款递增: Optional[str] = Field(None, description="租金条款(递增)")
    账期条款: Optional[str] = Field(None, description="账期条款")
    押金条款: Optional[str] = Field(None, description="押金条款")
    签署日期: Optional[str] = Field(None, description="签署日期，格式：YYYY-MM-DD")
    合同编号: Optional[str] = Field(None, description="合同编号")

class AmendmentTerminationFields(BaseExtractionFields):
    """变更/解除协议字段"""
    承租人名称: Optional[str] = Field(None, description="承租人名称")
    楼栋房号: Optional[str] = Field(None, description="楼栋&房号")
    租赁计费面积: Optional[float] = Field(None, description="租赁(计费)面积，数字格式")
    涉及租赁期免租期账期押金条款的变更情况: Optional[str] = Field(None, description="涉及租赁期、免租期、账期、押金条款的变更情况")
    涉及租金条款的变更情况: Optional[str] = Field(None, description="涉及租金条款的变更情况")
    签署日期: Optional[str] = Field(None, description="签署日期，格式：YYYY-MM-DD")
    合同编号: Optional[str] = Field(None, description="合同编号")

class BillFields(BaseExtractionFields):
    """账单字段"""
    承租人名称: Optional[str] = Field(None, description="承租人名称")
    楼栋房号: Optional[str] = Field(None, description="楼栋&房号")
    含税金额: Optional[float] = Field(None, description="含税金额，数字格式")
    所属租期: Optional[str] = Field(None, description="所属租期")
    租赁计费面积: Optional[float] = Field(None, description="租赁(计费)面积，数字格式")
    预收租金情况: Optional[str] = Field(None, description="预收租金情况")
    补缴上期租金情况: Optional[str] = Field(None, description="补缴上期租金情况")
    同时缴纳押金情况: Optional[str] = Field(None, description="同时缴纳押金情况")
    租金减免情况: Optional[str] = Field(None, description="租金减免情况")
    账单发出日期: Optional[str] = Field(None, description="账单发出日期，格式：YYYY-MM-DD")

class BankReceiptFields(BaseExtractionFields):
    """银行回单字段"""
    付款人名称: Optional[str] = Field(None, description="付款人名称")
    流水日期: Optional[str] = Field(None, description="流水日期，格式：YYYY-MM-DD")
    转账金额: Optional[float] = Field(None, description="转账金额，数字格式")
    所属租期: Optional[str] = Field(None, description="所属租期")
    楼栋房号: Optional[str] = Field(None, description="楼栋&房号")
    回单号码: Optional[str] = Field(None, description="回单号码")
    备注摘要: Optional[str] = Field(None, description="备注/摘要")
    付款账号: Optional[str] = Field(None, description="付款账号")

# 分类字段映射
CATEGORY_FIELD_MAPPING = {
    "发票": InvoiceFields,
    "租赁协议": LeaseAgreementFields,
    "变更/解除协议": AmendmentTerminationFields,
    "账单": BillFields,
    "银行回单": BankReceiptFields
}

# 分类字段名称映射（用于提示词）
CATEGORY_FIELD_NAMES = {
    "发票": ["购买方名称", "开票日期", "含税金额", "所属租期", "楼栋&房号", "发票号码", "备注", "税率"],
    "租赁协议": ["承租人名称", "楼栋&房号", "租赁(计费)面积", "租赁期起止", "免租期条款", "租金条款(递增)", "账期条款", "押金条款", "签署日期", "合同编号"],
    "变更/解除协议": ["承租人名称", "楼栋&房号", "租赁(计费)面积", "涉及租赁期、免租期、账期、押金条款的变更情况", "涉及租金条款的变更情况", "签署日期", "合同编号"],
    "账单": ["承租人名称", "楼栋&房号", "含税金额", "所属租期", "租赁(计费)面积", "预收租金情况", "补缴上期租金情况", "同时缴纳押金情况", "租金减免情况", "账单发出日期"],
    "银行回单": ["付款人名称", "流水日期", "转账金额", "所属租期", "楼栋&房号", "回单号码", "备注/摘要", "付款账号"]
}

# 原有的CategoryConfig保持不变，但现在可以引用新的字段定义
class CategoryConfig(BaseModel):
    """文件分类配置"""
    name: str
    display_name: str
    description: str
    confidence_threshold: float = 0.6
    extraction_fields: List[str]
    field_model: Optional[type] = Field(None, description="对应的Pydantic字段模型")

# 预定义的分类配置
CATEGORY_CONFIGS = {
    "发票": CategoryConfig(
        name="发票",
        display_name="发票",
        description="各类发票文档",
        confidence_threshold=0.6,
        extraction_fields=CATEGORY_FIELD_NAMES["发票"],
        field_model=InvoiceFields
    ),
    "租赁协议": CategoryConfig(
        name="租赁协议",
        display_name="租赁协议",
        description="物业租赁协议文档",
        confidence_threshold=0.6,
        extraction_fields=CATEGORY_FIELD_NAMES["租赁协议"],
        field_model=LeaseAgreementFields
    ),
    "变更/解除协议": CategoryConfig(
        name="变更/解除协议",
        display_name="变更/解除协议",
        description="租赁变更或解除协议",
        confidence_threshold=0.6,
        extraction_fields=CATEGORY_FIELD_NAMES["变更/解除协议"],
        field_model=AmendmentTerminationFields
    ),
    "账单": CategoryConfig(
        name="账单",
        display_name="账单",
        description="各类账单文档",
        confidence_threshold=0.6,
        extraction_fields=CATEGORY_FIELD_NAMES["账单"],
        field_model=BillFields
    ),
    "银行回单": CategoryConfig(
        name="银行回单",
        display_name="银行回单",
        description="银行转账回单",
        confidence_threshold=0.6,
        extraction_fields=CATEGORY_FIELD_NAMES["银行回单"],
        field_model=BankReceiptFields
    )
}

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
