#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单文件处理服务 - 处理单个文件的分类和字段提取请求
不涉及数据库操作，只负责创建Kafka消息
"""

import logging
import uuid
import tempfile
import os
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.kafka_service import kafka_service
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

class SimpleFileService:
    """简单文件处理服务"""
    
    def __init__(self):
        self.supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    
    async def create_single_file_classification_task(
        self,
        file_content: bytes,
        file_type: str,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建单个文件分类任务 - 上传到MinIO，发送S3 key到Kafka"""
        try:
            logger.info(f"Creating single file classification task for file type: {file_type}")
            
            # 验证文件类型
            if not self._validate_file_type(file_type):
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # 验证文件大小 (MinIO upload limit: 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if len(file_content) > max_size:
                raise ValueError(f"File too large: {len(file_content)} bytes. Maximum size: {max_size} bytes")
            
            # 生成唯一的任务ID
            task_id = str(uuid.uuid4())
            
            # 将文件内容上传到MinIO
            s3_key = f"single_files/classification/{task_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_type}"
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_type) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # 上传到MinIO
                if not minio_service.upload_file(temp_file_path, s3_key):
                    raise Exception("Failed to upload file to MinIO")
                
                logger.info(f"File uploaded to MinIO with key: {s3_key}")
                
                # 创建Kafka消息 - 包含S3 key
                message = {
                    "type": "single_file_classification_job",
                    "job_id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "s3_key": s3_key,  # MinIO S3 key
                    "file_type": file_type,
                    "callback_url": callback_url,
                    "created_at": datetime.now().isoformat(),
                    "delivery_method": "minio"
                }
                
                # 发送到Kafka
                kafka_service.publish_message("single.file.classification", message)
                logger.info(f"Kafka message sent for single file classification task: {task_id}")
                
                return {
                    "task_id": task_id,
                    "status": "created",
                    "message": "Single file classification task created successfully",
                    "s3_key": s3_key,
                    "callback_url": callback_url,
                    "delivery_method": "minio"
                }
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to create single file classification task: {e}")
            raise
    
    async def create_single_file_classification_task_from_url(
        self,
        presigned_url: str,
        file_type: str,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """从预签名URL创建单个文件分类任务"""
        try:
            logger.info(f"Creating single file classification task from URL for file type: {file_type}")
            
            # 验证文件类型
            if not self._validate_file_type(file_type):
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # 验证URL格式
            if not presigned_url.startswith(('http://', 'https://')):
                raise ValueError("Invalid presigned URL format")
            
            # 生成唯一的任务ID
            task_id = str(uuid.uuid4())
            
            # 创建Kafka消息 - 包含预签名URL
            message = {
                "type": "single_file_classification_job",
                "job_id": str(uuid.uuid4()),
                "task_id": task_id,
                "presigned_url": presigned_url,  # 预签名URL
                "file_type": file_type,
                "callback_url": callback_url,
                "created_at": datetime.now().isoformat(),
                "delivery_method": "presigned_url"
            }
            
            # 发送到Kafka
            kafka_service.publish_message("single.file.classification", message)
            logger.info(f"Kafka message sent for single file classification task from URL: {task_id}")
            
            return {
                "task_id": task_id,
                "status": "created",
                "message": "Single file classification task created successfully from URL",
                "presigned_url": presigned_url,
                "callback_url": callback_url,
                "delivery_method": "presigned_url"
            }
                    
        except Exception as e:
            logger.error(f"Failed to create single file classification task from URL: {e}")
            raise
    
    async def create_single_file_extraction_task(
        self,
        file_content: bytes,
        file_type: str,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建单个文件字段提取任务 - 上传到MinIO，发送S3 key到Kafka"""
        try:
            logger.info(f"Creating single file extraction task for file type: {file_type}")
            
            # 验证文件类型
            if not self._validate_file_type(file_type):
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # 验证文件大小 (MinIO upload limit: 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if len(file_content) > max_size:
                raise ValueError(f"File too large: {len(file_content)} bytes. Maximum size: {max_size} bytes")
            
            # 生成唯一的任务ID
            task_id = str(uuid.uuid4())
            
            # 将文件内容上传到MinIO
            s3_key = f"single_files/extraction/{task_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_type}"
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_type) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # 上传到MinIO
                if not minio_service.upload_file(temp_file_path, s3_key):
                    raise Exception("Failed to upload file to MinIO")
                
                logger.info(f"File uploaded to MinIO with key: {s3_key}")
                
                # 创建Kafka消息 - 包含S3 key
                message = {
                    "type": "single_file_extraction_job",
                    "job_id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "s3_key": s3_key,  # MinIO S3 key
                    "file_type": file_type,
                    "callback_url": callback_url,
                    "created_at": datetime.now().isoformat(),
                    "delivery_method": "minio"
                }
                
                # 发送到Kafka
                kafka_service.publish_message("single.file.extraction", message)
                logger.info(f"Kafka message sent for single file extraction task: {task_id}")
                
                return {
                    "task_id": task_id,
                    "status": "created",
                    "message": "Single file extraction task created successfully",
                    "s3_key": s3_key,
                    "callback_url": callback_url,
                    "delivery_method": "minio"
                }
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to create single file extraction task: {e}")
            raise
    
    async def create_single_file_extraction_task_from_url(
        self,
        presigned_url: str,
        file_type: str,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """从预签名URL创建单个文件字段提取任务"""
        try:
            logger.info(f"Creating single file extraction task from URL for file type: {file_type}")
            
            # 验证文件类型
            if not self._validate_file_type(file_type):
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # 验证URL格式
            if not presigned_url.startswith(('http://', 'https://')):
                raise ValueError("Invalid presigned URL format")
            
            # 生成唯一的任务ID
            task_id = str(uuid.uuid4())
            
            # 创建Kafka消息 - 包含预签名URL
            message = {
                "type": "single_file_extraction_job",
                "job_id": str(uuid.uuid4()),
                "task_id": task_id,
                "presigned_url": presigned_url,  # 预签名URL
                "file_type": file_type,
                "callback_url": callback_url,
                "created_at": datetime.now().isoformat(),
                "delivery_method": "presigned_url"
            }
            
            # 发送到Kafka
            kafka_service.publish_message("single.file.extraction", message)
            logger.info(f"Kafka message sent for single file extraction task from URL: {task_id}")
            
            return {
                "task_id": task_id,
                "status": "created",
                "message": "Single file extraction task created successfully from URL",
                "presigned_url": presigned_url,
                "callback_url": callback_url,
                "delivery_method": "presigned_url"
            }
                    
        except Exception as e:
            logger.error(f"Failed to create single file extraction task from URL: {e}")
            raise
    
    def _validate_file_type(self, file_type: str) -> bool:
        """验证文件类型是否支持"""
        return file_type.lower() in self.supported_extensions

# 创建全局实例
simple_file_service = SimpleFileService()
