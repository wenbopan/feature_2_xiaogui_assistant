from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging
import uuid
from datetime import datetime

from app.models.database import get_db, Task, FileClassification, FieldExtraction, ProcessingMessage, FileMetadata, FileExtractionFailure
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
        failed_files = []
        
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
                
                # 1. 创建ProcessingMessage记录
                processing_message = ProcessingMessage(
                    job_id=job_id,
                    task_id=task_id,
                    file_metadata_id=file_metadata.id,
                    topic="field.extraction",
                    payload=message,
                    status="created",
                    created_at=datetime.now()
                )
                
                # 2. 立即写入数据库
                db.add(processing_message)
                db.commit()
                logger.info(f"Successfully created ProcessingMessage record for field extraction job {job_id}")
                
                # 3. 立即发送Kafka消息
                kafka_service.publish_message("field.extraction", message)
                logger.info(f"Successfully sent Kafka message for field extraction job {job_id}")
                
                total_jobs += 1
                
            except Exception as e:
                # 4. 如果失败，回滚该文件的操作
                db.rollback()
                logger.error(f"Failed to create field extraction job for file {file_metadata.id} ({file_metadata.original_filename}): {e}")
                
                # 创建FileExtractionFailure记录
                failure_record = FileExtractionFailure(
                    task_id=task_id,
                    filename=file_metadata.original_filename,
                    error=f"Field extraction job creation failed: {str(e)}",
                    file_size=None  # 这里我们没有文件大小信息
                )
                db.add(failure_record)
                
                failed_files.append({
                    "file_id": file_metadata.id,
                    "filename": file_metadata.original_filename,
                    "error": str(e)
                })
                # 继续处理下一个文件，不中断整个流程
                continue
        
        if failed_files:
            logger.warning(f"Failed to create {len(failed_files)} field extraction jobs for task {task_id}")
        
        return {
            "task_id": task_id,
            "total_jobs": total_jobs,
            "failed_jobs": len(failed_files),
            "failed_files": failed_files,
            "status": "jobs_created" if not failed_files else "jobs_created_with_failures",
            "message": f"Successfully created {total_jobs} field extraction jobs" + 
                      (f", {len(failed_files)} failed" if failed_files else "")
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
async def get_extraction_progress(
    task_id: int,
    include_details: bool = False,
    db: Session = Depends(get_db)
):
    """获取字段提取任务的进度"""
    try:
        # 验证任务存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 查询ProcessingMessage表，topic为"field.extraction"
        from sqlalchemy import func
        
        # 按状态分组统计
        status_stats = db.query(
            ProcessingMessage.status,
            func.count(ProcessingMessage.id)
        ).filter(
            ProcessingMessage.task_id == task_id,
            ProcessingMessage.topic == "field.extraction"
        ).group_by(ProcessingMessage.status).all()
        
        # 构建状态统计字典
        status_breakdown = {
            "created": 0,
            "consumed": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        
        total_jobs = 0
        completed_jobs = 0
        failed_jobs = 0
        
        for status, count in status_stats:
            status_breakdown[status] = count
            total_jobs += count
            if status == "completed":
                completed_jobs += count
            elif status == "failed":
                failed_jobs += count
        
        # 计算进度百分比
        progress_percentage = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        # 构建基础响应
        response_data = {
            "task_id": task_id,
            "topic": "field.extraction",
            "total_jobs": total_jobs,
            "status_breakdown": status_breakdown,
            "progress_percentage": round(progress_percentage, 2),
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "last_updated": datetime.now().isoformat()
        }
        
        # 如果需要详细信息，添加文件详情
        if include_details:
            file_details = []
            processing_messages = db.query(ProcessingMessage).filter(
                ProcessingMessage.task_id == task_id,
                ProcessingMessage.topic == "field.extraction"
            ).all()
            
            for msg in processing_messages:
                # 获取文件名
                file_metadata = db.query(FileMetadata).filter(
                    FileMetadata.id == msg.file_metadata_id
                ).first()
                
                file_details.append({
                    "file_id": msg.file_metadata_id,
                    "filename": file_metadata.original_filename if file_metadata else "Unknown",
                    "status": msg.status,
                    "last_updated": msg.updated_at.isoformat() if msg.updated_at else msg.created_at.isoformat()
                })
            
            response_data["file_details"] = file_details
        
        return response_data
        
    except Exception as e:
        logger.error(f"Failed to get extraction progress for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取提取进度失败: {str(e)}")
