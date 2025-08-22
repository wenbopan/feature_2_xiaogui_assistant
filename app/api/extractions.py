from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging
import uuid

from app.models.database import get_db, Task, FileClassification, FieldExtraction, ProcessingMessage, FileMetadata
from app.models.schemas import FieldExtractionResult
from app.services.kafka_service import kafka_service

router = APIRouter(prefix="/v1", tags=["extractions"])
logger = logging.getLogger(__name__)

@router.post("/tasks/{task_id}/extract-fields")
async def trigger_field_extraction(task_id: int, db: Session = Depends(get_db)):
    """触发字段提取 - 基于原始文件，不依赖分类结果"""
    try:
        # 验证任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取原始文件（不依赖分类结果）
        files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
        
        if not files:
            raise HTTPException(status_code=400, detail="没有找到文件")
        
        # 为每个文件生成一个Kafka消息
        total_jobs = 0
        for file_metadata in files:
            try:
                # 生成唯一的job_id
                job_id = str(uuid.uuid4())
                
                # 构建消息内容
                message = {
                    "type": "field_extraction_job",
                    "job_id": job_id,
                    "task_id": task_id,
                    "file_id": file_metadata.id,
                    "s3_key": file_metadata.s3_key,
                    "file_type": file_metadata.file_type,
                    "filename": file_metadata.original_filename
                }
                
                # 发送到Kafka
                kafka_service.publish_message("field.extraction", message)
                total_jobs += 1
                
                logger.info(f"Created field extraction job {job_id} for file {file_metadata.original_filename}")
                
            except Exception as e:
                logger.error(f"Failed to create field extraction job for file {file_metadata.id}: {e}")
                continue
        
        return {
            "task_id": task_id,
            "total_jobs": total_jobs,
            "status": "jobs_created",
            "message": f"Successfully created {total_jobs} field extraction jobs"
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger field extraction: {e}")
        raise HTTPException(status_code=500, detail=f"触发字段提取失败: {str(e)}")

@router.get("/tasks/{task_id}/extracted-fields")
async def get_extracted_fields(task_id: int, db: Session = Depends(get_db)):
    """获取字段提取结果 - 原文件+提取字段的join结果"""
    try:
        # 验证任务存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 查询原文件信息和提取结果
        results = db.query(
            FileClassification,
            FieldExtraction
        ).outerjoin(
            FieldExtraction, 
            FileClassification.id == FieldExtraction.file_classification_id
        ).filter(
            FileClassification.task_id == task_id
        ).all()
        
        # 按分类组织结果
        results_by_category = {}
        for classification, extraction in results:
            category = classification.category
            if category not in results_by_category:
                results_by_category[category] = []
            
            # 构建结果对象
            result_item = {
                "file_id": classification.file_metadata_id,
                "original_filename": classification.file_metadata.original_filename,
                "final_filename": classification.final_filename,
                "category": category,
                "classification_confidence": classification.confidence,
                "extraction_status": "completed" if extraction else "pending",
                "extraction_data": extraction.extraction_data if extraction else {},
                "missing_fields": extraction.missing_fields if extraction else [],
                "extraction_confidence": extraction.confidence if extraction else None,
                "extraction_method": extraction.extraction_method if extraction else None
            }
            
            results_by_category[category].append(result_item)
        
        return {
            "task_id": task_id,
            "total_files": len(results),
            "results_by_category": results_by_category
        }
        
    except Exception as e:
        logger.error(f"Failed to get extracted fields: {e}")
        raise HTTPException(status_code=500, detail=f"获取字段提取结果失败: {str(e)}")

@router.get("/tasks/{task_id}/extraction-progress")
async def get_extraction_progress(task_id: int, db: Session = Depends(get_db)):
    """获取字段提取进度"""
    try:
        # 验证任务存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取总文件数（原始文件）
        total_files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).count()
        
        # 获取已完成的提取数
        completed_extractions = db.query(FieldExtraction).filter(
            FieldExtraction.file_classification_id.is_(None)  # 基于原始文件的提取
        ).join(FileMetadata, FieldExtraction.file_classification_id.is_(None)).filter(
            FileMetadata.task_id == task_id
        ).count()
        
        # 获取处理中的消息数
        processing_messages = db.query(ProcessingMessage).filter(
            ProcessingMessage.task_id == task_id,
            ProcessingMessage.topic == "field.extraction",
            ProcessingMessage.status.in_(["consumed", "processing"])
        ).count()
        
        # 获取失败的消息数
        failed_messages = db.query(ProcessingMessage).filter(
            ProcessingMessage.task_id == task_id,
            ProcessingMessage.topic == "field.extraction",
            ProcessingMessage.status == "failed"
        ).count()
        
        progress_percentage = (completed_extractions / total_files * 100) if total_files > 0 else 0
        
        return {
            "task_id": task_id,
            "total_files": total_files,
            "completed_extractions": completed_extractions,
            "processing_files": processing_messages,
            "failed_files": failed_messages,
            "progress_percentage": round(progress_percentage, 2)
        }
        
    except Exception as e:
        logger.error(f"Failed to get extraction progress: {e}")
        raise HTTPException(status_code=500, detail=f"获取提取进度失败: {str(e)}")
