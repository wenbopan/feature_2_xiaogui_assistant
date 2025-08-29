#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容处理服务
处理文件内容提取和分类
"""

import logging
import json
import asyncio
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from app.services.minio_service import minio_service
from app.services.gemini_service import gemini_service
from app.services.kafka_service import kafka_service
from app.models.database import FileMetadata, FileClassification, Task

logger = logging.getLogger(__name__)

class ContentProcessor:
    """内容处理服务类"""
    
    def __init__(self):
        self.supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    
    async def process_file(self, task_id: int, file_id: int) -> Dict[str, Any]:
        """异步处理单个文件（供消费者调用）"""
        try:
            from app.models.database import get_db
            from app.services.minio_service import minio_service
            
            db = next(get_db())
            try:
                # 获取任务信息
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.error(f"Task {task_id} not found")
                    return {"success": False, "error": "Task not found"}
                
                # 获取文件元数据
                file_metadata = db.query(FileMetadata).filter(FileMetadata.id == file_id).first()
                if not file_metadata:
                    logger.error(f"File metadata {file_id} not found")
                    return {"success": False, "error": "File metadata not found"}
                
                # 获取文件内容
                file_content = minio_service.get_file_content(file_metadata.s3_key)
                if not file_content:
                    logger.error(f"Failed to get file content for {file_metadata.s3_key}")
                    return {"success": False, "error": "Failed to get file content"}
                
                # 分类文件 - 使用真实的Gemini AI分类
                classification_result = await self._classify_file(file_metadata, file_content, db)
                
                # 生成逻辑重命名文件名
                if classification_result["category"] != "未识别":
                    logical_filename = self._generate_logical_filename(
                        task.organize_date, task.project_name, classification_result["category"], file_metadata.original_filename
                    )
                    
                    # 更新FileMetadata的逻辑文件名
                    file_metadata.logical_filename = logical_filename
                    
                    # 创建分类记录
                    classification = FileClassification(
                        task_id=task.id,
                        file_metadata_id=file_metadata.id,
                        category=classification_result["category"],
                        confidence=classification_result["confidence"],
                        final_filename=logical_filename,
                        classification_method=classification_result.get("method", "gemini"),
                        gemini_response=classification_result.get("raw_response")
                    )
                    
                    db.add(classification)
                    db.commit()
                    
                    logger.info(f"File logically renamed: {file_metadata.original_filename} -> {logical_filename}")
                    return {"success": True, "logical_filename": logical_filename}
                else:
                    # 未识别的文件
                    logger.info(f"File classified as unrecognized: {file_metadata.original_filename}")
                    return {"success": True, "category": "unrecognized"}
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing file {file_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _classify_file_sync(self, file_metadata: FileMetadata, file_content: bytes, db: Session) -> Dict[str, Any]:
        """同步分类文件"""
        try:
            # 这里实现同步的文件分类逻辑
            # 暂时返回一个默认分类
            logger.info(f"Classifying file: {file_metadata.original_filename}")
            
            # 基于文件扩展名的简单分类
            file_ext = file_metadata.file_type.lower()
            if file_ext in ['.jpg', '.jpeg', '.png']:
                # 图片文件 - 可能是回单、发票等
                if '回单' in file_metadata.original_filename or '银行' in file_metadata.original_filename:
                    category = "银行回单"
                elif '发票' in file_metadata.original_filename:
                    category = "发票"
                elif '账单' in file_metadata.original_filename:
                    category = "账单"
                else:
                    category = "其他图片"
            elif file_ext == '.pdf':
                # PDF文件 - 可能是合同
                if '合同' in file_metadata.original_filename or '协议' in file_metadata.original_filename:
                    category = "合同协议"
                else:
                    category = "其他文档"
            else:
                category = "未识别"
            
            return {
                "category": category,
                "confidence": 0.8,
                "method": "file_extension_analysis",
                "raw_response": {"analysis": "Based on filename and extension"}
            }
            
        except Exception as e:
            logger.error(f"Error classifying file: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "method": "error",
                "raw_response": {"error": str(e)}
            }

    async def process_content_job(self, message: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """处理内容处理任务"""
        try:
            # 从data字段中获取任务信息
            data = message.get("data", {})
            task_id = data.get("task_id")
            job_id = data.get("job_id")
            file_id = data.get("file_id")
            
            if not task_id or not job_id or not file_id:
                raise Exception(f"Missing required fields: task_id={task_id}, job_id={job_id}, file_id={file_id}")
            
            logger.info(f"Starting content processing job {job_id} for file {file_id} in task {task_id}")
            
            # 获取任务信息（用于组织信息），不存在也不阻断核心处理
            task = db.query(Task).filter(Task.id == task_id).first()
            
            # 获取特定的文件元数据
            file_metadata = db.query(FileMetadata).filter(FileMetadata.id == file_id).first()
            if not file_metadata:
                raise Exception(f"File metadata {file_id} not found")
            
            # 处理单个文件
            result = await self._process_single_file(file_metadata, task, db)
            
            if result["success"]:
                logger.info(f"File {file_id} processed successfully")
                return {
                    "status": "completed",
                    "task_id": task_id,
                    "job_id": job_id,
                    "file_id": file_id,
                    "result": result
                }
            else:
                logger.error(f"File {file_id} processing failed: {result.get('error', 'Unknown error')}")
                return {
                    "status": "failed",
                    "task_id": task_id,
                    "job_id": job_id,
                    "file_id": file_id,
                    "error": result.get('error', 'Unknown error')
                }
            
        except Exception as e:
            logger.error(f"Content processing job failed: {e}")
            # 发送失败通知
            self._send_failure_notification(task_id, job_id, str(e))
            raise
    
    async def _process_single_file(self, file_metadata: FileMetadata, task: Task, db: Session) -> Dict[str, Any]:
        """处理单个文件"""
        try:
            # 获取文件内容
            file_content = minio_service.get_file_content(file_metadata.s3_key)
            if not file_content:
                logger.error(f"Failed to get file content for {file_metadata.s3_key}")
                return {"success": False, "error": "Failed to get file content"}
            
            # 直接分类文件，内容处理在分类阶段进行
            classification_result = await self._classify_file(file_metadata, file_content, db)
            
            # 生成逻辑重命名文件名
            if classification_result["category"] != "未识别":
                logical_filename = self._generate_logical_filename(
                    task.organize_date, task.project_name, classification_result["category"], file_metadata.original_filename
                )
                
                # 更新FileMetadata的逻辑文件名
                file_metadata.logical_filename = logical_filename
                
                # 创建分类记录，同时保存final_filename
                classification = FileClassification(
                    task_id=task.id,
                    file_metadata_id=file_metadata.id,
                    category=classification_result["category"],
                    confidence=classification_result["confidence"],
                    final_filename=logical_filename,  # 保存到分类记录中
                    classification_method=classification_result.get("method", "gemini"),
                    gemini_response=classification_result.get("raw_response")
                )
                
                db.add(classification)
                db.commit()
                
                logger.info(f"File logically renamed: {file_metadata.original_filename} -> {logical_filename}")
                return {"success": True, "logical_filename": logical_filename}
            else:
                # 未识别的文件 - 不重命名，只记录状态
                logger.info(f"File classified as unrecognized: {file_metadata.original_filename}")
                return {"success": True, "category": "unrecognized"}
            
        except Exception as e:
            logger.error(f"Failed to process file {file_metadata.original_filename}: {e}")
            return {"success": False, "error": str(e)}
    
    # 移除不必要的_read_file_content函数，内容处理直接在分类阶段进行
    
    async def _classify_file(self, file_metadata: FileMetadata, file_content: bytes, db: Session) -> Dict[str, Any]:
        """分类文件 - 统一使用Gemini视觉模型"""
        try:
            # Content reading status is now tracked in ProcessingMessage table
            # No need to update FileMetadata for this
            
            # 所有文件类型都直接使用Gemini视觉模型进行分类
            # 传递原始二进制内容，让Gemini理解整个文件
            classification_result = await gemini_service.classify_file(
                file_content, 
                file_metadata.file_type, 
                file_metadata.original_filename
            )
            
            return classification_result
            
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # Error status is tracked in ProcessingMessage table
            # No need to update FileMetadata for this
            
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"分类失败: {str(e)}",
                "method": "failed"
            }
    
    # 旧的_generate_final_filename函数已移除，替换为_generate_logical_filename
    
    def _generate_logical_filename(self, organize_date: str, project_name: str, category: str, original_filename: str) -> str:
        """生成逻辑重命名文件名"""
        # 清理项目名称
        clean_project_name = project_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # 获取文件扩展名
        file_ext = os.path.splitext(original_filename)[1]
        
        # 生成新文件名：整理时间-项目名称-分类名.扩展名
        logical_filename = f"{organize_date}-{clean_project_name}-{category}{file_ext}"
        
        # 注意：不再检查MinIO中的文件冲突，因为我们现在使用逻辑重命名
        # 文件名冲突检查可以在数据库层面进行，或者通过添加时间戳/序号来避免
        
        return logical_filename
    
    def _update_progress(self, task_id: int, stage: str, current: int, total: int):
        """更新进度"""
        try:
            progress_message = {
                "task_id": task_id,
                "stage": stage,
                "current": current,
                "total": total,
                "percentage": (current / total) * 100 if total > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }
            kafka_service.publish_message("progress.update", progress_message)
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")
    
    def _send_completion_notification(self, task_id: int, job_id: str, processed_files: int, failed_files: int):
        """发送完成通知"""
        try:
            completion_message = {
                "task_id": task_id,
                "job_id": job_id,
                "status": "completed",
                "processed_files": processed_files,
                "failed_files": failed_files,
                "timestamp": datetime.now().isoformat()
            }
            kafka_service.publish_message("job.completed", completion_message)
        except Exception as e:
            logger.warning(f"Failed to send completion notification: {e}")
    
    def _send_failure_notification(self, task_id: int, job_id: str, error: str):
        """发送失败通知"""
        try:
            failure_message = {
                "task_id": task_id,
                "job_id": job_id,
                "status": "failed",
                "error": error,
                "timestamp": datetime.now().isoformat()
            }
            kafka_service.publish_message("job.failed", failure_message)
        except Exception as e:
            logger.warning(f"Failed to send failure notification: {e}")

# 全局内容处理服务实例
content_processor = ContentProcessor()
