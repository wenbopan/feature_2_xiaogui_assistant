#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinIO服务模块
使用MinIO Python客户端，支持无认证模式
"""

import os
import hashlib
import logging
from typing import List, Optional, BinaryIO
from minio import Minio
from minio.error import S3Error
from app.config import settings

logger = logging.getLogger(__name__)

class MinIOService:
    """MinIO服务类"""
    
    def __init__(self):
        """初始化MinIO服务"""
        self.client = None
        self.bucket_name = settings.minio_bucket
        self.is_connected = False
        logger.debug(f"MinIOService.__init__() - bucket_name: {self.bucket_name}")
    
    async def connect(self):
        """连接到MinIO服务"""
        try:
            return self._initialize_client()
        except Exception as e:
            logger.error(f"Failed to connect to MinIO: {e}")
            return False
    
    def disconnect(self):
        """断开MinIO连接"""
        try:
            if self.client:
                # MinIO Python客户端没有显式断开连接的方法
                logger.info("MinIO service disconnected")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error disconnecting from MinIO: {e}")
    
    def _initialize_client(self):
        """初始化MinIO客户端"""
        logger.debug(f"MinIOService._initialize_client() called - is_connected: {self.is_connected}")
        if self.is_connected:
            logger.debug("MinIO already connected, returning early")
            return True
            
        try:
            logger.debug(f"MinIO settings - endpoint: {settings.minio_endpoint}, access_key: {settings.minio_access_key}, secure: {settings.minio_secure}")
            # 检查是否为无认证模式
            if not settings.minio_access_key or not settings.minio_secret_key:
                # 无认证模式
                logger.debug("Using MinIO in anonymous mode (no credentials)")
                self.client = Minio(
                    settings.minio_endpoint,
                    access_key=None,
                    secret_key=None,
                    secure=settings.minio_secure
                )
            else:
                # 有认证模式
                logger.debug("Using MinIO with credentials")
                self.client = Minio(
                    settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_secure
                )
            
            # 确保bucket存在
            logger.debug("Calling _ensure_bucket_exists()")
            self._ensure_bucket_exists()
            self.is_connected = True
            logger.info("MinIO client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            logger.debug(f"Exception details: {type(e).__name__}: {e}")
            # 抛出异常，让应用启动失败
            raise
    
    def _ensure_bucket_exists(self):
        """确保bucket存在"""
        try:
            if self.client.bucket_exists(self.bucket_name):
                logger.info(f"Bucket {self.bucket_name} already exists")
            else:
                try:
                    self.client.make_bucket(self.bucket_name)
                    logger.info(f"Created bucket {self.bucket_name}")
                except S3Error as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    raise
        except S3Error as e:
            logger.error(f"Error checking bucket: {e}")
            raise
    
    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """上传文件到MinIO"""
        try:
            self.client.fput_object(self.bucket_name, s3_key, file_path)
            logger.info(f"Successfully uploaded {file_path} to {s3_key}")
            return True
        except S3Error as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            return False
    
    def upload_fileobj(self, file_obj: BinaryIO, s3_key: str, content_type: Optional[str] = None) -> bool:
        """上传文件对象到MinIO"""
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.client.put_object(self.bucket_name, s3_key, file_obj, extra_args)
            logger.info(f"Successfully uploaded file object to {s3_key}")
            return True
        except S3Error as e:
            logger.error(f"Failed to upload file object to {s3_key}: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """从MinIO下载文件"""
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.client.fget_object(self.bucket_name, s3_key, local_path)
            logger.info(f"Successfully downloaded {s3_key} to {local_path}")
            return True
        except S3Error as e:
            logger.error(f"Failed to download {s3_key}: {e}")
            return False
    
    def get_file_content(self, s3_key: str) -> Optional[bytes]:
        """获取文件内容"""
        try:
            if not self.client:
                logger.error("MinIO client not initialized")
                return None
                
            response = self.client.get_object(self.bucket_name, s3_key)
            content = response.read()
            logger.info(f"Successfully read content from {s3_key}")
            return content
        except S3Error as e:
            logger.error(f"Failed to read content from {s3_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading content from {s3_key}: {e}")
            return None
    
    def delete_file(self, s3_key: str) -> bool:
        """删除文件"""
        try:
            self.client.remove_object(self.bucket_name, s3_key)
            logger.info(f"Successfully deleted {s3_key}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete {s3_key}: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[str]:
        """列出指定前缀的文件"""
        try:
            response = self.client.list_objects(self.bucket_name, prefix, recursive=True)
            return [obj.object_name for obj in response]
        except S3Error as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []
    
    def file_exists(self, s3_key: str) -> bool:
        """检查文件是否存在"""
        try:
            self.client.stat_object(self.bucket_name, s3_key)
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            logger.error(f"Error checking file existence for {s3_key}: {e}")
            return False
    
    def get_file_size(self, s3_key: str) -> Optional[int]:
        """获取文件大小"""
        try:
            response = self.client.stat_object(self.bucket_name, s3_key)
            return response.size
        except S3Error as e:
            logger.error(f"Failed to get file size for {s3_key}: {e}")
            return None
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """复制文件"""
        try:
            # MinIO Python客户端使用CopySource对象
            from minio.commonconfig import CopySource
            copy_source = CopySource(self.bucket_name, source_key)
            self.client.copy_object(self.bucket_name, dest_key, copy_source)
            logger.info(f"Successfully copied {source_key} to {dest_key}")
            return True
        except S3Error as e:
            logger.error(f"Failed to copy {source_key} to {dest_key}: {e}")
            return False
    
    def calculate_sha256(self, file_content: bytes) -> str:
        """计算文件的SHA256哈希值"""
        return hashlib.sha256(file_content).hexdigest()
    
    def get_task_directory_structure(self, task_id: int) -> dict:
        """获取任务目录结构"""
        structure = {
            'uploads': [],
            'extracted': [],
            'renamed': [],
            'unrecognized': [],
            'reports': []
        }
        
        for prefix in structure.keys():
            prefix_path = f"tasks/{task_id}/{prefix}/"
            files = self.list_files(prefix_path)
            structure[prefix] = [f.replace(prefix_path, '') for f in files if f != prefix_path]
        
        return structure
    
    def get_connection_status(self):
        """获取连接状态信息"""
        return {
            'connected': self.is_connected,
            'endpoint': settings.minio_endpoint,
            'bucket_name': self.bucket_name,
            'client_initialized': self.client is not None
        }

# 全局MinIO服务实例
minio_service = MinIOService()
