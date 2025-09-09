from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging
import tempfile
import os

from app.models.database import get_db, Task, FileMetadata, ProcessingMessage
from app.models.schemas import TaskResponse, FileUploadResponse, FileMetadataResponse
from app.services.file_service import file_service
from app.auth import get_current_active_user, User

router = APIRouter(prefix="/v1", tags=["batch"])
logger = logging.getLogger(__name__)

# ============================================================================
# TASK MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/tasks/upload", response_model=FileUploadResponse)
async def upload_files(
    organize_date: str = Form(...),
    project_name: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload files for a new task"""
    try:
        # Create new task
        task = Task(
            project_name=project_name,
            organize_date=organize_date,  # Frontend sends YYYY-MM-DD format which matches DB schema
            status="created",
            options={}
        )
        db.add(task)
        db.flush()  # Get the task ID
        
        # Process uploaded files
        uploaded_files = []
        failed_files = []
        
        for file in files:
            try:
                # Save uploaded file to temporary location
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                    # Write uploaded file content to temp file
                    content = await file.read()
                    temp_file.write(content)
                    temp_file_path = temp_file.name
                
                logger.info(f"Saved uploaded file to: {temp_file_path}")
                
                # Process the ZIP file using the correct method
                result = file_service.process_zip_upload(
                    task_id=task.id,
                    zip_file_path=temp_file_path,
                    project_name=project_name,
                    organize_date=organize_date,
                    db=db
                )
                
                if result["status"] in ["extraction_success", "extraction_completed_with_errors"]:
                    uploaded_files.append({
                        "filename": file.filename,
                        "total_files": result["total_files"],
                        "extracted_files": result["extracted_files"],
                        "failed_files": result["extraction_failures"]
                    })
                else:
                    failed_files.append({
                        "filename": file.filename,
                        "error": f"Extraction failed: {result['status']}"
                    })
                
                # Clean up temp file
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file_path}: {e}")
                    
            except Exception as e:
                logger.error(f"Failed to process file {file.filename}: {e}")
                failed_files.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        # Update task status based on processing results
        if failed_files and not uploaded_files:
            task.status = "failed"
        elif failed_files:
            task.status = "partial"
        else:
            task.status = "extracted"
        
        db.commit()
        
        # Calculate totals
        total_files = sum(upload.get("total_files", 0) for upload in uploaded_files)
        success_count = sum(upload.get("extracted_files", 0) for upload in uploaded_files)
        failure_count = sum(upload.get("failed_files", 0) for upload in uploaded_files)
        
        return FileUploadResponse(
            task_id=task.id,
            uploaded_files=uploaded_files,
            failed_files=failed_files,
            total_files=total_files,
            success_count=success_count,
            failure_count=failure_count
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get task details by ID"""
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(
            id=task.id,
            project_name=task.project_name,
            organize_date=task.organize_date,
            status=task.status,
            options=task.options,
            created_at=task.created_at,
            updated_at=task.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/tasks/{task_id}/files", response_model=List[FileMetadataResponse])
async def get_task_files(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get all files for a specific task"""
    try:
        files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
        
        file_responses = []
        for file in files:
            file_response = FileMetadataResponse(
                id=file.id,
                original_filename=file.original_filename,
                relative_path=file.relative_path,
                file_type=file.file_type,
                file_size=file.file_size,
                logical_filename=file.logical_filename,
                extracted_fields=file.extracted_fields
            )
            file_responses.append(file_response)
        
        return file_responses
        
    except Exception as e:
        logger.error(f"Failed to get files for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================================
# BATCH PROCESSING ENDPOINTS
# ============================================================================

@router.post("/{task_id}/file-classification", response_model=Dict[str, Any])
async def create_file_classification_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建文件分类任务 - 异步处理AI文件分类和逻辑重命名"""
    try:
        result = file_service.create_content_processing_task(task_id, db)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建文件分类任务失败: {str(e)}")

@router.get("/{task_id}/file-classification-progress", response_model=Dict[str, Any])
async def get_file_classification_progress(
    task_id: int,
    include_details: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取文件分类任务的进度（分类+重命名）"""
    try:
        # 验证任务存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 查询ProcessingMessage表，topic为"file.processing"
        from app.models.database import ProcessingMessage
        from sqlalchemy import func
        
        # Get all files for the task from FileMetadata
        files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
        total_files = len(files) if files else 0
        
        # Count files by status - only count files that have ProcessingMessage records
        completed_files = 0
        failed_files = 0
        pending_files = 0
        
        for file in files:
            # Check ProcessingMessage for this file
            processing_msg = db.query(ProcessingMessage).filter(
                ProcessingMessage.task_id == task_id,
                ProcessingMessage.file_metadata_id == file.id,
                ProcessingMessage.topic == "file.processing"
            ).order_by(ProcessingMessage.created_at.desc()).first()
            
            # Only count files that have ProcessingMessage records
            if processing_msg:
                if processing_msg.status == "completed":
                    completed_files += 1
                elif processing_msg.status == "failed":
                    failed_files += 1
                else:
                    pending_files += 1
            # Files without ProcessingMessage records are not counted (not in processing queue)
        
        # 构建基础响应 - 使用与extraction-progress相同的格式
        response_data = {
            "task_id": task_id,
            "topic": "file.processing",
            "total_files": total_files,
            "completed_files": completed_files,
            "failed_files": failed_files,
            "pending_files": pending_files
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"Failed to get processing progress for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件分类进度失败: {str(e)}")

@router.post("/{task_id}/field-extraction")
async def trigger_field_extraction(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Trigger field extraction for all files in a task"""
    try:
        # Validate task exists
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Get all files for the task
        files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
        
        if not files:
            raise HTTPException(status_code=400, detail="No files found for task")
        
        # Use the dedicated service function instead of inline logic
        from app.services.file_service import file_service
        
        result = file_service.create_field_extraction_task(task_id, db)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger field extraction for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger field extraction: {str(e)}")

@router.get("/tasks/{task_id}/extraction-progress")
async def get_extraction_progress(
    task_id: int, 
    include_details: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get field extraction progress for a task"""
    try:
        # Validate task exists
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Get all files for the task
        files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
        
        if not files:
            return {
                "task_id": task_id,
                "total_files": 0,
                "completed_files": 0,
                "failed_files": 0,
                "pending_files": 0
            }
        
        # Count files by status - only count files that have ProcessingMessage records
        completed_count = 0
        failed_count = 0
        pending_count = 0
        
        for file in files:
            # Check ProcessingMessage for this file
            processing_msg = db.query(ProcessingMessage).filter(
                ProcessingMessage.task_id == task_id,
                ProcessingMessage.file_metadata_id == file.id,
                ProcessingMessage.topic == "field.extraction"
            ).order_by(ProcessingMessage.created_at.desc()).first()
            
            # Only count files that have ProcessingMessage records
            if processing_msg:
                if processing_msg.status == "completed":
                    completed_count += 1
                elif processing_msg.status == "failed":
                    failed_count += 1
                else:
                    pending_count += 1
            # Files without ProcessingMessage records are not counted (not in processing queue)
        
        response_data = {
            "task_id": task_id,
            "total_files": len(files),
            "completed_files": completed_count,
            "failed_files": failed_count,
            "pending_files": pending_count
        }
        
        # Add file details if requested
        if include_details:
            file_details = []
            processing_messages = db.query(ProcessingMessage).filter(
                ProcessingMessage.task_id == task_id,
                ProcessingMessage.topic == "field.extraction"
            ).all()
            
            for msg in processing_messages:
                # Get filename
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
        raise HTTPException(status_code=500, detail=f"Failed to get extraction progress: {str(e)}")
