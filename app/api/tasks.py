from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import tempfile
import shutil
from datetime import datetime
import uuid

from app.models.database import get_db, Task, FileMetadata, FileClassification
from app.models.schemas import TaskCreate, TaskResponse, TaskStatus, FileUploadResponse, ProcessingResult, FileMetadataResponse, ClassificationResult
from app.services.file_service import file_service
# from app.services.kafka_service import kafka_service  # 暂时注释掉Kafka服务
from app.config import settings

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
        
        if task.status != "created":
            raise HTTPException(status_code=400, detail="任务状态不允许上传文件")
        
        # 验证文件类型
        if not file.filename.lower().endswith('.zip'):
            raise HTTPException(status_code=400, detail="只支持ZIP文件")
        
        # 验证文件大小
        if file.size > settings.max_zip_size:
            raise HTTPException(status_code=400, detail=f"文件大小超过限制: {settings.max_zip_size / (1024*1024):.1f}MB")
        
                # 保存文件到临时目录
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # 处理ZIP文件
            result = file_service.process_zip_upload(
                task_id=task_id,
                zip_file_path=temp_file_path,
                project_name=task.project_name,
                organize_date=task.organize_date or datetime.now().strftime("%Y-%m-%d"),
                db=db
            )
            
            # 更新任务状态
            task.status = "extracted"  # 改为extracted状态，允许后续process操作
            db.commit()
            
            # 暂时跳过Kafka消息发布
            # kafka_service.publish_message("file.organize.completed", {
            #     "type": "processing_completed",
            #     "task_id": task_id,
            #     "total_files": result["total_files"],
            #     "processed_files": result["processed_files"]
            # })
            
            return FileUploadResponse(
                task_id=task_id,
                upload_id=str(uuid.uuid4()),
                filename=file.filename,
                size=file.size,
                status="completed"
            )
            
        finally:
            # 清理临时文件
            shutil.rmtree(temp_dir)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

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

@router.get("/{task_id}/progress", response_model=Dict[str, Any])
async def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db)
):
    """获取任务进度"""
    try:
        # 获取任务基本信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取文件统计
        total_files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).count()
        classified_files = db.query(FileClassification).filter(FileClassification.task_id == task_id).count()
        
        # 按分类统计
        category_stats = {}
        classifications = db.query(FileClassification).filter(FileClassification.task_id == task_id).all()
        for cls in classifications:
            category = cls.category
            if category not in category_stats:
                category_stats[category] = 0
            category_stats[category] += 1
        
        progress_data = {
            "task_id": task_id,
            "status": task.status,
            "total_files": total_files,
            "processed_files": classified_files,
            "progress_percentage": (classified_files / total_files * 100) if total_files > 0 else 0,
            "category_stats": category_stats,
            "last_updated": task.updated_at or task.created_at
        }
        
        return progress_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务进度失败: {str(e)}")

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
    
    # 获取未识别文件
    unrecognized_files = db.query(FileMetadata).filter(
        FileMetadata.task_id == task_id,
        FileMetadata.content_reading_status == "failed"
    ).all()
    
    # 统计信息
    total_files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).count()
    classified_files = len(classifications)
    unrecognized_count = len(unrecognized_files)
    failed_count = db.query(FileMetadata).filter(
        FileMetadata.task_id == task_id,
        FileMetadata.content_reading_status == "failed"
    ).count()
    
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
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    tasks = db.query(Task).offset(skip).limit(limit).all()
    return tasks
