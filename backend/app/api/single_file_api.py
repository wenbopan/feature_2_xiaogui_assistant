from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
import time

from app.models.database import get_db, Task, FileMetadata, ProcessingMessage
from app.models.schemas import FileContentResponse
from app.services.simple_file_service import simple_file_service
from app.services.minio_service import minio_service
from app.auth import get_current_active_user, User

router = APIRouter(prefix="/v1", tags=["single-file"])
logger = logging.getLogger(__name__)

# ============================================================================
# SINGLE FILE PROCESSING ENDPOINTS
# ============================================================================

async def _process_classification(
    file_content: Optional[UploadFile] = None,
    oss_url: Optional[str] = None,
    file_type: str = None,
    file_id: Optional[str] = None,
    update_file_callback: Optional[dict] = None,
    model_type: Optional[str] = None
):
    """classification logic"""
    try:
        # 验证至少提供一种文件传递方式
        if not file_content and not oss_url:
            raise HTTPException(
                status_code=400, 
                detail="Either file_content or oss_url must be provided"
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
                update_file_callback=update_file_callback,
                model_type=model_type
            )
        else:
            # OSS URL方式
            result = await simple_file_service.create_single_file_classification_task_from_url(
                oss_url=oss_url,
                file_type=file_type,
                file_id=file_id,
                update_file_callback=update_file_callback,
                model_type=model_type
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
    oss_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    update_file_callback: Optional[str] = Form(None),
    model_type: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """Classify a single file immediately - supports both direct upload and OSS URL
    
    Callback placeholders: ${file_category}, ${is_recognized}
    """
    import json
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 API received classification request - model_type: {model_type}, file_type: {file_type}")
    
    callback_dict = None
    if update_file_callback:
        try:
            callback_dict = json.loads(update_file_callback)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid update_file_callback JSON format")
    
    return await _process_classification(file_content, oss_url, file_type, file_id, callback_dict, model_type)

@router.post("/internal/files/classify")
async def classify_single_file_internal(
    file_content: Optional[UploadFile] = File(None),
    oss_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    update_file_callback: Optional[str] = Form(None),
    model_type: Optional[str] = Form(None)
):
    """Internal API for file classification - no authentication required"""
    import json
    callback_dict = None
    if update_file_callback:
        try:
            callback_dict = json.loads(update_file_callback)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid update_file_callback JSON format")
    
    return await _process_classification(file_content, oss_url, file_type, file_id, callback_dict, model_type)

async def _process_extraction(
    file_content: Optional[UploadFile] = None,
    oss_url: Optional[str] = None,
    file_type: str = None,
    file_id: Optional[str] = None,
    extract_file_callback: Optional[dict] = None,
    model_type: Optional[str] = None
):
    """Common extraction logic """
    try:
        # 验证至少提供一种文件传递方式
        if not file_content and not oss_url:
            raise HTTPException(
                status_code=400, 
                detail="Either file_content or oss_url must be provided"
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
                extract_file_callback=extract_file_callback,
                model_type=model_type
            )
        else:
            # OSS URL方式
            result = await simple_file_service.create_single_file_extraction_task_from_url(
                oss_url=oss_url,
                file_type=file_type,
                file_id=file_id,
                extract_file_callback=extract_file_callback,
                model_type=model_type
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
    oss_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    extract_file_callback: Optional[str] = Form(None),
    model_type: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """Extract fields from a single file immediately - supports both direct upload and OSS URL
    
    Callback placeholders: ${file_content}, ${is_extracted}
    """
    import json
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 API received extraction request - model_type: {model_type}, file_type: {file_type}")
    
    callback_dict = None
    if extract_file_callback:
        try:
            callback_dict = json.loads(extract_file_callback)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid extract_file_callback JSON format")
    
    return await _process_extraction(file_content, oss_url, file_type, file_id, callback_dict, model_type)

@router.post("/internal/files/extract-fields")
async def extract_fields_single_file_internal(
    file_content: Optional[UploadFile] = File(None),
    oss_url: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_id: Optional[str] = Form(None),
    extract_file_callback: Optional[str] = Form(None),
    model_type: Optional[str] = Form(None)
):
    """Internal API for field extraction - no authentication required"""
    import json
    callback_dict = None
    if extract_file_callback:
        try:
            callback_dict = json.loads(extract_file_callback)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid extract_file_callback JSON format")
    
    return await _process_extraction(file_content, oss_url, file_type, file_id, callback_dict, model_type)

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

# ============================================================================
# CALLBACK ENDPOINTS
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
