#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段提取处理服务
处理文档字段提取的业务逻辑
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.database import FieldExtraction, FileMetadata
from app.services.minio_service import minio_service
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

class FieldExtractionProcessor:
    """字段提取处理服务类"""
    
    def __init__(self):
        self.supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    
    def process_field_extraction(self, extraction_job: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """执行字段提取处理（同步版本）"""
        try:
            logger.info(f"Processing field extraction for file {extraction_job['file_id']}")
            
            # 获取文件内容从MinIO
            file_content = minio_service.get_file_content(extraction_job['s3_key'])
            if not file_content:
                raise Exception(f"Failed to get file content from MinIO: {extraction_job['s3_key']}")
            
            # 调用Gemini服务进行实际的字段提取（同步方式）
            import asyncio
            
            # 创建新的事件循环来运行异步的Gemini调用
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                extraction_result = loop.run_until_complete(
                    gemini_service.extract_fields(
                        file_content=file_content,
                        file_type=extraction_job['file_type'],
                        filename=extraction_job['filename']
                    )
                )
            finally:
                loop.close()
            
            # 创建FieldExtraction记录 - 使用实际的提取结果
            field_extraction = FieldExtraction(
                file_metadata_id=extraction_job['file_id'],
                field_category=extraction_result.get("category", "未识别"),
                extraction_data=extraction_result.get("extraction_data", {}),
                missing_fields=extraction_result.get("missing_fields", []),
                extraction_method="gemini_vision",
                confidence=extraction_result.get("extraction_confidence", 0.0)
            )
            
            db.add(field_extraction)
            
            # 同时更新file_metadata表中的extracted_fields列
            file_metadata = db.query(FileMetadata).filter(FileMetadata.id == extraction_job['file_id']).first()
            if file_metadata:
                file_metadata.extracted_fields = extraction_result.get("extraction_data", {})
                logger.info(f"Updated file_metadata.extracted_fields for file {extraction_job['file_id']}")
            else:
                logger.warning(f"FileMetadata not found for file_id: {extraction_job['file_id']}")
            
            db.commit()
            
            logger.info(f"Field extraction completed for file {extraction_job['filename']}: {extraction_result}")
            return {"success": True, "extracted_fields": extraction_result.get("extraction_data", {})}
            
        except Exception as e:
            logger.error(f"Error in field extraction processing: {e}")
            db.rollback()
            return None

# 全局字段提取处理服务实例
field_extraction_processor = FieldExtractionProcessor()
