from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import timedelta
import logging
import time

from app.models.database import get_db, Task, FileMetadata, ProcessingMessage
from app.models.schemas import ( TaskResponse, FileUploadResponse, FileMetadataResponse, FileContentResponse
)
from app.services.file_service import file_service
from app.services.simple_file_service import simple_file_service
from app.services.kafka_service import kafka_service
from app.services.minio_service import minio_service
from app.config import settings
from app.auth import (
    authenticate_user, create_access_token, get_current_active_user, 
    Token, User, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/v1", tags=["api"])
logger = logging.getLogger(__name__)

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录接口"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user

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
                import tempfile
                import os
                
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
# FILE CONTENT & EXTRACTION ENDPOINTS
# ============================================================================

# ============================================================================
# SINGLE FILE PROCESSING ENDPOINTS
# ============================================================================

async def _process_classification(
    file_content: Optional[UploadFile] = None,
    presigned_url: Optional[str] = None,
    file_type: str = None,
    file_id: Optional[str] = None,
    callback_url: Optional[str] = None
):
    """classification logic"""
    try:
        # 验证至少提供一种文件传递方式
        if not file_content and not presigned_url:
            raise HTTPException(
                status_code=400, 
                detail="Either file_content or presigned_url must be provided"
            )
        
        # 验证文件类型
        if not file_type.startswith('.'):
            file_type = '.' + file_type
        
        # 调用简单文件服务
        if file_content:
            # 直接上传方式
            content = await file_content.read()
            result = await simple_file_service.create_single_file_classification_task(
                file_content=content,
                file_type=file_type,
                file_id=file_id,
                callback_url=callback_url
            )
        else:
            # 预签名URL方式
            result = await simple_file_service.create_single_file_classification_task_from_url(
                presigned_url=presigned_url,
                file_type=file_type,
                file_id=file_id,
                callback_url=callback_url
            )
        
        # Return 200 OK for successful task publication
        return JSONResponse(
            status_code=200,
            content={"message": "File classification task published successfully"}
        )
        
    except Exception as e:
        logger.error(f"Failed to create single file classification task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create classification task: {str(e)}")

@router.post("/files/classify")
async def classify_single_file(
    file_content: Optional[UploadFile] = File(None),
    presigned_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    callback_url: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """Classify a single file immediately - supports both direct upload and presigned URL"""
    return await _process_classification(file_content, presigned_url, file_type, file_id, callback_url)

@router.post("/internal/files/classify")
async def classify_single_file_internal(
    file_content: Optional[UploadFile] = File(None),
    presigned_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    callback_url: Optional[str] = Form(None)
):
    """Internal API for file classification - no authentication required"""
    return await _process_classification(file_content, presigned_url, file_type, file_id, callback_url)

async def _process_extraction(
    file_content: Optional[UploadFile] = None,
    presigned_url: Optional[str] = None,
    file_type: str = None,
    file_id: Optional[str] = None,
    callback_url: Optional[str] = None
):
    """Common extraction logic """
    try:
        # 验证至少提供一种文件传递方式
        if not file_content and not presigned_url:
            raise HTTPException(
                status_code=400, 
                detail="Either file_content or presigned_url must be provided"
            )
        
        # 验证文件类型
        if not file_type.startswith('.'):
            file_type = '.' + file_type
        
        # 调用简单文件服务
        if file_content:
            # 直接上传方式
            content = await file_content.read()
            result = await simple_file_service.create_single_file_extraction_task(
                file_content=content,
                file_type=file_type,
                file_id=file_id,
                callback_url=callback_url
            )
        else:
            # 预签名URL方式
            result = await simple_file_service.create_single_file_extraction_task_from_url(
                presigned_url=presigned_url,
                file_type=file_type,
                file_id=file_id,
                callback_url=callback_url
            )
        
        # Return 200 OK for successful task publication
        return JSONResponse(
            status_code=200,
            content={"message": "File field extraction task published successfully"}
        )
        
    except Exception as e:
        logger.error(f"Failed to create single file extraction task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create extraction task: {str(e)}")

@router.post("/files/extract-fields")
async def extract_fields_single_file(
    file_content: Optional[UploadFile] = File(None),
    presigned_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    callback_url: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """Extract fields from a single file immediately - supports both direct upload and presigned URL"""
    return await _process_extraction(file_content, presigned_url, file_type, file_id, callback_url)

@router.post("/internal/files/extract-fields")
async def extract_fields_single_file_internal(
    file_content: Optional[UploadFile] = File(None),
    presigned_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    callback_url: Optional[str] = Form(None)
):
    """Internal API for field extraction - no authentication required"""
    return await _process_extraction(file_content, presigned_url, file_type, file_id, callback_url)

@router.post("/files/view-content", response_model=FileContentResponse)
async def get_file_content(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get file content and extraction results by task ID and relative path"""
    task_id = request.get("task_id")
    relative_path = request.get("relative_path")
    
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required in request body")
    if not relative_path:
        raise HTTPException(status_code=400, detail="relative_path is required in request body")
    
    try:
        # 1. Get file metadata
        file_metadata = db.query(FileMetadata).filter(
            FileMetadata.task_id == task_id,
            FileMetadata.relative_path == relative_path
        ).first()
        
        if not file_metadata:
            # Check if task exists first
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Task {task_id} does not exist"
                )
            
            # Check if any files exist for this task
            task_files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
            if not task_files:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Task {task_id} exists but contains no files"
                )
            
            # Check if the relative path is close to any existing paths (for better UX)
            existing_paths = [f.relative_path for f in task_files if f.relative_path]
            if existing_paths:
                # Find the closest matching path for better error message
                import difflib
                closest_match = difflib.get_close_matches(relative_path, existing_paths, n=1, cutoff=0.6)
                if closest_match:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"File not found. Did you mean: '{closest_match[0]}'? Available files: {', '.join(existing_paths[:5])}"
                    )
                else:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"File not found. Available files: {', '.join(existing_paths[:5])}"
                    )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail=f"File not found for task {task_id} and path '{relative_path}'"
                )
        
        # 2. Get extraction status from ProcessingMessage
        processing_msg = db.query(ProcessingMessage).filter(
            ProcessingMessage.task_id == task_id,
            ProcessingMessage.file_metadata_id == file_metadata.id,
            ProcessingMessage.topic == "field.extraction"
        ).order_by(ProcessingMessage.created_at.desc()).first()
        
        # 3. Determine extraction status
        extraction_status = "pending"
        extraction_error = None
        
        if processing_msg:
            if processing_msg.status == "completed":
                extraction_status = "completed"
            elif processing_msg.status == "failed":
                extraction_status = "failed"
                extraction_error = processing_msg.error
            elif processing_msg.status in ["created", "consumed", "processing"]:
                extraction_status = "pending"
        
        # 4. Get the latest successful field extraction
        from app.models.database import FieldExtraction
        latest_extraction = db.query(FieldExtraction).filter(
            FieldExtraction.file_metadata_id == file_metadata.id,
            FieldExtraction.confidence > 0  # Only successful extractions
        ).order_by(FieldExtraction.created_at.desc()).first()
        
        # Use extracted fields from the latest successful extraction, fallback to file_metadata
        extracted_fields = file_metadata.extracted_fields
        if latest_extraction and latest_extraction.extraction_data:
            extracted_fields = latest_extraction.extraction_data
            logger.info(f"Using extracted fields from field_extractions table for file {file_metadata.id}")
        else:
            logger.info(f"No successful field extraction found for file {file_metadata.id}, using file_metadata.extracted_fields")
        
        # 5. Generate download URL from MinIO
        try:
            logger.info(f"Generating download URL for file {file_metadata.id}, s3_key: {file_metadata.s3_key}")
            
            # For PDF files, generate inline URL to display in browser instead of downloading
            is_pdf = file_metadata.file_type and (file_metadata.file_type.lower().endswith('.pdf') or 'pdf' in file_metadata.file_type.lower())
            download_url = minio_service.generate_download_url(
                file_metadata.s3_key, 
                inline=is_pdf
            )
            logger.info(f"Generated {'inline' if is_pdf else 'download'} URL: {download_url}")
        except Exception as e:
            logger.error(f"Failed to generate download URL for file {file_metadata.id}: {e}")
            download_url = None
        
        # 6. Assemble response
        response = FileContentResponse(
            task_id=task_id,
            original_filename=file_metadata.original_filename,
            relative_path=file_metadata.relative_path,
            file_download_url=download_url,
            content_type=file_metadata.file_type,
            file_size=file_metadata.file_size,
            extracted_fields=extracted_fields,
            final_filename=file_metadata.logical_filename,
            extraction_status=extraction_status,
            extraction_error=extraction_error
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content for task {task_id}, path {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-02-18T00:00:00Z",
        "version": "1.0.0"
    }

@router.get("/ready")
async def readiness_check():
    """Readiness检查 - 检查所有依赖服务是否就绪"""
    from datetime import datetime
    import time
    from app.models.database import engine
    from app.services.minio_service import minio_service
    from app.services.kafka_service import kafka_service
    from app.consumers import kafka_consumer_service, simple_file_classification_consumer, simple_field_extraction_consumer
    
    start_time = time.time()
    checks = {}
    all_ready = True
    
    # 检查数据库连接
    """
    try:
        # 测试数据库连接
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "ready",
            "message": "Database connection successful"
        }
    except Exception as e:
        checks["database"] = {
            "status": "not_ready",
            "message": f"Database connection failed: {str(e)}"
        }
        all_ready = False
    """
    # 检查Kafka连接
    try:
        kafka_status = kafka_service.get_connection_status()
        if kafka_status["connected"] and kafka_status["producer_connected"]:
            checks["kafka"] = {
                "status": "ready",
                "message": "Kafka producer connected",
                "details": kafka_status
            }
        else:
            checks["kafka"] = {
                "status": "not_ready",
                "message": "Kafka not fully connected",
                "details": kafka_status
            }
            all_ready = False
    except Exception as e:
        checks["kafka"] = {
            "status": "not_ready",
            "message": f"Kafka check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查Kafka Consumer
    try:
        consumer_status = kafka_consumer_service.running and kafka_consumer_service.consumer is not None
        if consumer_status:
            checks["kafka_consumer"] = {
                "status": "ready",
                "message": "Kafka consumer running"
            }
        else:
            checks["kafka_consumer"] = {
                "status": "not_ready",
                "message": "Kafka consumer not running"
            }
            all_ready = False
    except Exception as e:
        checks["kafka_consumer"] = {
            "status": "not_ready",
            "message": f"Kafka consumer check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查简单文件分类消费者
    try:
        simple_classification_status = simple_file_classification_consumer.running
        if simple_classification_status:
            checks["simple_classification_consumer"] = {
                "status": "ready",
                "message": "Simple file classification consumer running"
            }
        else:
            checks["simple_classification_consumer"] = {
                "status": "not_ready",
                "message": "Simple file classification consumer not running"
            }
            all_ready = False
    except Exception as e:
        checks["simple_classification_consumer"] = {
            "status": "not_ready",
            "message": f"Simple file classification consumer check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查简单字段提取消费者
    try:
        simple_extraction_status = simple_field_extraction_consumer.running
        if simple_extraction_status:
            checks["simple_extraction_consumer"] = {
                "status": "ready",
                "message": "Simple field extraction consumer running"
            }
        else:
            checks["simple_extraction_consumer"] = {
                "status": "not_ready",
                "message": "Simple field extraction consumer not running"
            }
            all_ready = False
    except Exception as e:
        checks["simple_extraction_consumer"] = {
            "status": "not_ready",
            "message": f"Simple field extraction consumer check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查MinIO连接
    """
    try:
        # 检查MinIO连接状态
        minio_status = minio_service.is_connected and minio_service.client is not None
        if minio_status:
            # 尝试列举bucket来验证连接
            buckets = minio_service.client.list_buckets()
            checks["minio"] = {
                "status": "ready",
                "message": "MinIO connection successful",
                "bucket_count": len(buckets)
            }
        else:
            checks["minio"] = {
                "status": "not_ready",
                "message": "MinIO service not connected"
            }
            all_ready = False
    except Exception as e:
        checks["minio"] = {
            "status": "not_ready",
            "message": f"MinIO check failed: {str(e)}"
        }
        all_ready = False
     """
    
    # 计算检查耗时
    check_duration = time.time() - start_time
    
    response_data = {
        "status": "ready" if all_ready else "not_ready",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "check_duration_seconds": round(check_duration, 3),
        "services": checks
    }
    
    # 根据readiness状态返回适当的HTTP状态码
    status_code = 200 if all_ready else 503
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )

# ============================================================================
# CONSUMER MANAGEMENT ENDPOINTS
# ============================================================================



# ============================================================================
# CALLBACK TESTING ENDPOINTS
# ============================================================================

# Simple in-memory storage for callback results (for E2E testing)
# Key: file_id, Value: array of callback responses
callback_results = {}

@router.post("/callbacks/classify-file")
async def classify_file_callback(callback_data: dict):
    """测试用：文件分类回调接口"""
    file_id = callback_data.get("file_id")
    if file_id:
        # Initialize array if file_id doesn't exist
        if file_id not in callback_results:
            callback_results[file_id] = []
        
        # Append new callback result
        callback_results[file_id].append({
            "type": "classification",
            "timestamp": time.time(),
            "data": callback_data
        })
        logger.info(f"Classification callback received for file {file_id}: {callback_data}")
    return callback_data

@router.post("/callbacks/extract-file")
async def extract_file_callback(callback_data: dict):
    """测试用：文件提取回调接口"""
    file_id = callback_data.get("file_id")
    if file_id:
        # Initialize array if file_id doesn't exist
        if file_id not in callback_results:
            callback_results[file_id] = []
        
        # Append new callback result
        callback_results[file_id].append({
            "type": "extraction", 
            "timestamp": time.time(),
            "data": callback_data
        })
        logger.info(f"Extraction callback received for file {file_id}: {callback_data}")
    return callback_data

@router.get("/callbacks/results/{file_id}")
async def get_callback_result(file_id: str):
    """Get all callback results for specific file_id"""
    if file_id in callback_results:
        # Sort by timestamp to get chronological order
        results = sorted(callback_results[file_id], key=lambda x: x["timestamp"])
        return {"results": results}
    return {"message": "No callback results found for this file_id", "results": []}

@router.get("/callbacks/results")
async def get_all_callback_results():
    """Get all callback results for E2E testing"""
    return {"results": callback_results}

@router.delete("/callbacks/results")
async def clear_callback_results():
    """Clear callback results for E2E testing"""
    global callback_results
    callback_results.clear()
    return {"message": "Callback results cleared"}

# ============================================================================
# CONFIGURATION MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/config/instructions")
async def get_instructions_config(current_user: User = Depends(get_current_active_user)):
    """获取当前指令配置（包含内存中的指令）"""
    from app.config import instructions_manager
    try:
        config = instructions_manager.get_config()
        memory_instructions = instructions_manager.get_memory_instructions()
        return {
            "success": True,
            "config": config,
            "memory_instructions": memory_instructions,
            "last_modified": instructions_manager._last_modified,
            "config_path": instructions_manager.config_path
        }
    except Exception as e:
        logger.error(f"Failed to get instructions config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

@router.post("/config/instructions/hot-swap")
async def hot_swap_instructions(instructions_data: dict, current_user: User = Depends(get_current_active_user)):
    """热交换指令（更新内存中的指令）"""
    from app.config import instructions_manager
    try:
        # 验证输入数据 - 使用中文分类名
        required_categories = ['发票', '租赁协议', '变更/解除协议', '账单', '银行回单']
        for category in required_categories:
            if category not in instructions_data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required category: {category}"
                )
        
        # 执行热交换
        instructions_manager.hot_swap_instructions(instructions_data)
        
        # 获取更新后的配置
        config = instructions_manager.get_config()
        memory_instructions = instructions_manager.get_memory_instructions()
        
        return {
            "success": True,
            "message": "Instructions hot-swapped successfully",
            "config": config,
            "memory_instructions": memory_instructions,
            "last_modified": instructions_manager._last_modified
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to hot-swap instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to hot-swap instructions: {str(e)}")

@router.post("/config/instructions/reset")
async def reset_instructions_to_original(current_user: User = Depends(get_current_active_user)):
    """重置指令为原始配置"""
    from app.config import instructions_manager
    try:
        instructions_manager.reset_to_original()
        config = instructions_manager.get_config()
        memory_instructions = instructions_manager.get_memory_instructions()
        
        return {
            "success": True,
            "message": "Instructions reset to original config successfully",
            "config": config,
            "memory_instructions": memory_instructions,
            "last_modified": instructions_manager._last_modified
        }
    except Exception as e:
        logger.error(f"Failed to reset instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset instructions: {str(e)}")

@router.get("/config/instructions/category/{category}")
async def get_instruction_for_category(category: str, current_user: User = Depends(get_current_active_user)):
    """获取指定分类的指令"""
    from app.config import instructions_manager
    try:
        instruction = instructions_manager.get_instruction_for_category(category)
        return {
            "success": True,
            "category": category,
            "instruction": instruction
        }
    except Exception as e:
        logger.error(f"Failed to get instruction for category {category}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get instruction: {str(e)}")


