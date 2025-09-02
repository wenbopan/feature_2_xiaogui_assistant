#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容处理服务
处理文件内容提取和分类
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.gemini_service import gemini_service
from app.services.kafka_service import kafka_service

logger = logging.getLogger(__name__)

class FileClassificationProcessor:
    """文件分类处理服务类 - 纯业务逻辑，无数据库依赖"""
    
    def __init__(self):
        self.supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    
    def classify_file_content(self, file_content: bytes, file_type: str, original_filename: str) -> Dict[str, Any]:
        """
        核心文件分类方法 - 不依赖数据库，只处理文件内容分类
        
        Args:
            file_content: 文件二进制内容
            file_type: 文件类型/扩展名
            original_filename: 原始文件名
            
        Returns:
            分类结果字典
        """
        try:
            # 所有文件类型都直接使用Gemini视觉模型进行分类
            # 传递原始二进制内容，让Gemini理解整个文件
            classification_result = gemini_service.classify_file_sync(
                file_content, 
                file_type, 
                original_filename
            )
            return classification_result
            
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"分类失败: {str(e)}",
                "method": "failed"
            }
    
    def generate_logical_filename(self, organize_date: str, project_name: str, category: str, original_filename: str) -> str:
        """
        生成逻辑重命名文件名
        
        Args:
            organize_date: 整理日期
            project_name: 项目名称
            category: 分类结果
            original_filename: 原始文件名
            
        Returns:
            逻辑重命名后的文件名
        """
        # 清理项目名称
        clean_project_name = project_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # 获取文件扩展名
        file_ext = os.path.splitext(original_filename)[1]
        
        # 生成新文件名：整理时间-项目名称-分类名.扩展名
        logical_filename = f"{organize_date}-{clean_project_name}-{category}{file_ext}"
        
        return logical_filename
    
    def process_file_content(self, file_content: bytes, file_type: str, original_filename: str, 
                           organize_date: str = None, project_name: str = None) -> Dict[str, Any]:
        """
        处理文件内容并返回分类结果和逻辑文件名
        
        Args:
            file_content: 文件二进制内容
            file_type: 文件类型/扩展名
            original_filename: 原始文件名
            organize_date: 整理日期（可选，用于生成逻辑文件名）
            project_name: 项目名称（可选，用于生成逻辑文件名）
            
        Returns:
            处理结果字典，包含分类结果和逻辑文件名
        """
        try:
            # 分类文件
            classification_result = self.classify_file_content(file_content, file_type, original_filename)
            
            # 生成逻辑重命名文件名（如果提供了组织信息）
            logical_filename = None
            if organize_date and project_name and classification_result["category"] != "未识别":
                logical_filename = self.generate_logical_filename(
                    organize_date, project_name, classification_result["category"], original_filename
                )
            
            return {
                "success": True,
                "classification": classification_result,
                "logical_filename": logical_filename,
                "category": classification_result["category"],
                "confidence": classification_result["confidence"]
            }
            
        except Exception as e:
            logger.error(f"Failed to process file {original_filename}: {e}")
            return {
                "success": False,
                "error": str(e),
                "category": "未识别",
                "confidence": 0.0
            }
    
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

# 全局文件分类处理服务实例
content_processor = FileClassificationProcessor()
