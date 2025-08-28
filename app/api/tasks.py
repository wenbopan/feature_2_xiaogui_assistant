from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import tempfile
import shutil
from datetime import datetime
import uuid

from app.models.database import get_db, Task, FileMetadata, FileClassification, ProcessingMessage, FileExtractionFailure
from app.models.schemas import TaskCreate, TaskResponse, TaskStatus, FileUploadResponse, ProcessingResult, FileMetadataResponse, ClassificationResult
from app.services.file_service import file_service
# from app.services.kafka_service import kafka_service  # 暂时注释掉Kafka服务
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])

@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    """创建新任务"""
    try:
        # 验证整理日期格式
        if task.organize_date:
            try:
                datetime.strptime(task.organize_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="整理日期格式错误，应为YYYY-MM-DD")
        
        # 创建任务记录
        db_task = Task(
            project_name=task.project_name,
            organize_date=task.organize_date,
            status="created",
            options=task.options or {}
        )
        
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        # 暂时跳过Kafka消息发布
        # kafka_service.publish_message("file.organize.uploaded", {
        #     "type": "task_created",
        #     "task_id": db_task.id,
        #     "project_name": db_task.project_name,
        #     "organize_date": db_task.organize_date
        # })
        
        return db_task
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

@router.post("/{task_id}/upload", response_model=FileUploadResponse)
async def upload_zip_file(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传ZIP文件"""
    try:
        # 验证任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # MVP版本：不做状态限制，允许用户在同一任务中多次上传ZIP
        # 每次上传都会覆盖之前的文件
        logger.info(f"Task {task_id} current status: {task.status}, allowing ZIP upload")
        
        # 验证文件类型
        if not file.filename.lower().endswith('.zip'):
            raise HTTPException(status_code=400, detail="只支持ZIP文件")
        
        # 验证文件大小（更健壮：部分环境下 UploadFile 无 size）
        if hasattr(file, "size") and file.size is not None:
            try:
                if int(file.size) > settings.max_zip_size:
                    raise HTTPException(status_code=400, detail=f"文件大小超过限制: {settings.max_zip_size / (5*1024):.1f}MB")
            except Exception:
                # 忽略 size 解析异常，改为落盘后再校验
                pass
        
        # 添加详细日志记录
        logger.info(f"开始处理文件上传: task_id={task_id}, filename={file.filename}, size={file.size}")
        
        # 保存文件到临时目录
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            # 落盘后再进行大小校验
            try:
                saved_size = os.path.getsize(temp_file_path)
                if saved_size > settings.max_zip_size:
                    raise HTTPException(status_code=400, detail=f"文件大小超过限制: {settings.max_zip_size / (1024*1024):.1f}MB")
            except HTTPException:
                raise
            except Exception:
                # 获取大小失败不致命，继续处理
                saved_size = None
            
            # 处理ZIP文件
            result = file_service.process_zip_upload(
                task_id=task_id,
                zip_file_path=temp_file_path,
                project_name=task.project_name,
                organize_date=task.organize_date or datetime.now().strftime("%Y-%m-%d"),
                db=db
            )
            
            # 根据提取结果确定状态
            extraction_status = result.get("status", "unknown")
            total_files = result.get("total_files", 0)
            extracted_files = result.get("extracted_files", 0)
            
            # 更新任务状态
            if extraction_status == "extraction_success":
                task.status = "extracted"
                response_status = "completed"
            elif extraction_status == "extraction_completed_with_errors":
                if extracted_files > 0:
                    task.status = "partially_extracted"
                    response_status = "partially_completed"
                else:
                    task.status = "extraction_failed"
                    response_status = "failed"
            else:
                task.status = "extraction_failed"
                response_status = "failed"
            
            db.commit()
            
            # 记录处理结果
            logger.info(f"Task {task_id} ZIP processing result: {extraction_status}, "
                       f"total_files={total_files}, extracted_files={extracted_files}")
            
            return FileUploadResponse(
                task_id=task_id,
                upload_id=str(uuid.uuid4()),
                filename=file.filename,
                size=(saved_size if saved_size is not None else (file.size if hasattr(file, "size") else None)),
                status=response_status,
                details={
                    "total_files": total_files,
                    "extracted_files": extracted_files,
                    "extraction_status": extraction_status
                }
            )
            
        finally:
            # 清理临时文件
            shutil.rmtree(temp_dir)
        
    except Exception as e:
        # 保留已有的 HTTPException 明细，不要覆盖为空字符串
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Upload failed for task {task_id}: {repr(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {repr(e)}")

@router.post("/{task_id}/process", response_model=Dict[str, Any])
async def create_content_processing_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """创建内容处理任务 - 异步处理AI内容提取、分类和重命名"""
    try:
        result = file_service.create_content_processing_task(task_id, db)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建内容处理任务失败: {str(e)}")

@router.get("/{task_id}/processing-progress", response_model=Dict[str, Any])
async def get_processing_progress(
    task_id: int,
    include_details: bool = False,
    db: Session = Depends(get_db)
):
    """获取内容处理任务的进度（分类+重命名）"""
    try:
        # 验证任务存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 查询ProcessingMessage表，topic为"file.processing"
        from app.models.database import ProcessingMessage
        from sqlalchemy import func
        
        # 按状态分组统计
        status_stats = db.query(
            ProcessingMessage.status,
            func.count(ProcessingMessage.id)
        ).filter(
            ProcessingMessage.task_id == task_id,
            ProcessingMessage.topic == "file.processing"
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
            "topic": "file.processing",
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
                ProcessingMessage.topic == "file.processing"
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
        logger.error(f"Failed to get processing progress for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取处理进度失败: {str(e)}")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    include_failures: bool = False,
    db: Session = Depends(get_db)
):
    """获取单个任务的详细信息"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if include_failures:
        # 获取失败文件信息
        failures = db.query(FileExtractionFailure).filter(
            FileExtractionFailure.task_id == task_id
        ).all()
        
        # 将失败信息添加到task对象中（动态属性）
        task.extraction_failures = [
            {
                "filename": failure.filename,
                "error": failure.error,
                "file_size": failure.file_size,
                "created_at": failure.created_at
            }
            for failure in failures
        ]
    
    return task

@router.get("/{task_id}/files", response_model=List[FileMetadataResponse])
async def get_task_files(
    task_id: int,
    db: Session = Depends(get_db)
):
    """获取任务的所有文件"""
    try:
        files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
        return files
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务文件失败: {str(e)}")

@router.get("/{task_id}/classifications", response_model=List[ClassificationResult])
async def get_task_classifications(
    task_id: int,
    db: Session = Depends(get_db)
):
    """获取任务的分类结果"""
    try:
        classifications = db.query(FileClassification).filter(FileClassification.task_id == task_id).all()
        return classifications
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类结果失败: {str(e)}")

@router.get("/{task_id}/results", response_model=ProcessingResult)
async def get_task_results(task_id: int, db: Session = Depends(get_db)):
    """获取任务处理结果"""
    # 验证任务存在
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 获取分类结果
    classifications = db.query(FileClassification).filter(FileClassification.task_id == task_id).all()
    
    # 获取未识别文件 - content_reading_status is no longer in FileMetadata
    # We'll identify unrecognized files as those without classifications
    total_files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).count()
    classified_files = len(classifications)
    
    # Get files that don't have classifications
    classified_file_ids = [cls.file_metadata_id for cls in classifications]
    unrecognized_files = db.query(FileMetadata).filter(
        FileMetadata.task_id == task_id,
        ~FileMetadata.id.in_(classified_file_ids)
    ).all()
    unrecognized_count = len(unrecognized_files)
    
    # Failed files are now tracked in ProcessingMessage table
    # For now, we'll use 0 as failed count since we need to join with ProcessingMessage
    failed_count = 0
    
    return ProcessingResult(
        task_id=task_id,
        status=task.status,
        total_files=total_files,
        classified_files=classified_files,
        unrecognized_files=unrecognized_count,
        failed_files=failed_count,
        classifications=classifications,
        unrecognized_files_list=unrecognized_files
    )

@router.get("/{task_id}/download")
async def download_task_results(task_id: int, format: str = "json", db: Session = Depends(get_db)):
    """下载任务结果"""
    # 验证任务存在
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if format not in ["json", "csv", "xlsx"]:
        raise HTTPException(status_code=400, detail="不支持的格式，支持: json, csv, xlsx")
    
    # 获取任务结果
    result = await get_task_results(task_id, db)
    
    if format == "json":
        return result
    
    # TODO: 实现CSV和Excel格式的导出
    raise HTTPException(status_code=501, detail="CSV和Excel格式导出功能尚未实现")

@router.delete("/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """删除任务（谨慎使用）"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        # 删除相关记录
        db.query(FileClassification).filter(FileClassification.task_id == task_id).delete()
        db.query(FileMetadata).filter(FileMetadata.task_id == task_id).delete()
        db.delete(task)
        db.commit()
        
        return {"message": "任务删除成功"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")

@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    include_failures: bool = False,
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    tasks = db.query(Task).offset(skip).limit(limit).all()
    
    if include_failures:
        # 为每个任务添加失败文件信息
        for task in tasks:
            failures = db.query(FileExtractionFailure).filter(
                FileExtractionFailure.task_id == task.id
            ).all()
            
            # 将失败信息添加到task对象中（动态属性）
            task.extraction_failures = [
                {
                    "filename": failure.filename,
                    "error": failure.error,
                    "file_size": failure.file_size,
                    "created_at": failure.created_at
                }
                for failure in failures
            ]
    
    return tasks
