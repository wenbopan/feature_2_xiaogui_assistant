from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from app.config import settings
import os

# 创建数据库引擎
engine = create_engine(
    settings.database_url_final,
    # PostgreSQL不需要特殊的connect_args
    pool_pre_ping=True,  # 连接前ping一下，确保连接有效
    pool_recycle=300,    # 5分钟后回收连接
    echo=settings.log_level.upper() == "DEBUG"  # 调试模式下显示SQL
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, comment="项目名称")
    organize_date = Column(String(10), nullable=True, comment="整理日期 YYYY-MM-DD")
    status = Column(String(50), default="created", comment="任务状态")
    options = Column(JSON, nullable=True, comment="任务选项")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    files = relationship("FileMetadata", back_populates="task")
    classifications = relationship("FileClassification", back_populates="task")

class FileMetadata(Base):
    """文件元数据表"""
    __tablename__ = "file_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    s3_key = Column(String(500), nullable=False, comment="MinIO中的key")
    original_filename = Column(String(255), nullable=False, comment="原始文件名")
    logical_filename = Column(String(255), nullable=True, comment="逻辑重命名后的文件名")
    relative_path = Column(String(500), nullable=True, comment="相对路径")
    file_type = Column(String(50), nullable=False, comment="文件类型")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    sha256 = Column(String(64), nullable=False, comment="文件SHA256")
    extracted_fields = Column(JSON, nullable=True, comment="提取的字段数据（生产环境使用）")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    task = relationship("Task", back_populates="files")
    classifications = relationship("FileClassification", back_populates="file_metadata")
    field_extractions = relationship("FieldExtraction", back_populates="file_metadata")

class ProcessingMessage(Base):
    """文件处理消息表 - 跟踪消息生命周期（创建/消费/完成/失败）"""
    __tablename__ = "processing_messages"

    id = Column(Integer, primary_key=True, index=True)
    # 业务关联
    job_id = Column(String(64), index=True, nullable=False, comment="消息/作业ID (UUID)")
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    file_metadata_id = Column(Integer, ForeignKey("file_metadata.id"), nullable=False)
    topic = Column(String(200), nullable=False, comment="Kafka主题")
    payload = Column(JSON, nullable=True, comment="原始消息负载快照")

    # 消息状态
    status = Column(String(32), default="created", comment="created|consumed|processing|completed|failed")
    error = Column(Text, nullable=True, comment="失败错误详情")
    attempts = Column(Integer, default=0, comment="处理尝试次数")

    # 元信息
    partition = Column(Integer, nullable=True)
    offset = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

class FileClassification(Base):
    """文件分类结果表"""
    __tablename__ = "file_classifications"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    file_metadata_id = Column(Integer, ForeignKey("file_metadata.id"), nullable=False)
    category = Column(String(100), nullable=False, comment="分类结果")
    confidence = Column(Float, nullable=False, comment="置信度")
    final_filename = Column(String(255), nullable=False, comment="重命名后的文件名")
    classification_method = Column(String(50), nullable=False, comment="分类方法")
    gemini_response = Column(JSON, nullable=True, comment="Gemini AI的原始响应")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    task = relationship("Task", back_populates="classifications")
    file_metadata = relationship("FileMetadata", back_populates="classifications")

class FieldExtraction(Base):
    """字段提取结果表"""
    __tablename__ = "field_extractions"
    
    id = Column(Integer, primary_key=True, index=True)
    file_metadata_id = Column(Integer, ForeignKey("file_metadata.id"), nullable=False, comment="关联的原文件ID")
    field_category = Column(String(100), nullable=False, comment="字段提取的分类结果")
    extraction_data = Column(JSON, nullable=False, comment="提取的字段数据")
    missing_fields = Column(JSON, nullable=True, comment="缺失的字段列表")
    extraction_method = Column(String(50), nullable=False, comment="提取方法")
    confidence = Column(Float, nullable=True, comment="提取置信度")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    file_metadata = relationship("FileMetadata", back_populates="field_extractions")

class FileExtractionFailure(Base):
    """文件解压失败记录表"""
    __tablename__ = "file_extraction_failures"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, comment="关联的任务ID")
    filename = Column(String(255), nullable=False, comment="原始文件名")
    error = Column(Text, nullable=False, comment="失败原因")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    task = relationship("Task")

class ExtractionTask(Base):
    """字段提取任务表"""
    __tablename__ = "extraction_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    status = Column(String(50), default="created", comment="任务状态")
    total_files = Column(Integer, default=0, comment="总文件数")
    processed_files = Column(Integer, default=0, comment="已处理文件数")
    failed_files = Column(Integer, default=0, comment="失败文件数")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# 创建所有表
def create_tables():
    """创建所有数据库表"""
    Base.metadata.create_all(bind=engine)

# 获取数据库会话
def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
