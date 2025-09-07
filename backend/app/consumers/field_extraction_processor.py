#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段提取处理服务
处理文档字段提取的业务逻辑
"""

import logging
from typing import Dict, Any

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class FieldExtractionProcessor:
    """字段提取处理服务类 - 纯业务逻辑，无数据库和文件系统依赖"""
    
    def __init__(self):
        self.supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    
    def extract_fields_from_content(self, file_content: bytes, file_type: str, filename: str, category: str, model_type: str = None) -> Dict[str, Any]:
        """
        从文件内容中提取字段 - 核心业务逻辑方法
        
        Args:
            file_content: 文件二进制内容
            file_type: 文件类型/扩展名
            filename: 文件名
            category: 文档分类（必需）
            model_type: AI模型类型（可选，默认为qwen）
            
        Returns:
            字段提取结果字典
        """
        try:
            # 记录使用的模型
            actual_model = model_type or "qwen"
            logger.info(f"🔍 Field extraction processor using {actual_model.upper()} model for: {filename} (category: {category})")
            
            # 验证分类参数
            if not category or category.strip() == "":
                raise ValueError("Category is required for field extraction")
            
            # 验证分类是否在支持的类别中
            from app.models.prompt_schemas import SUPPORTED_CATEGORIES
            if category not in SUPPORTED_CATEGORIES:
                raise ValueError(f"Unsupported category '{category}'. Supported categories: {SUPPORTED_CATEGORIES}")
            
            # 调用LLM服务进行实际的字段提取（同步方式）
            extraction_result = llm_service.extract_fields_sync(
                file_content=file_content,
                file_type=file_type,
                filename=filename,
                category=category,
                model_type=model_type
            )
            
            # 返回提取结果（不涉及数据库操作，由调用方处理）
            logger.info(f"Field extraction completed for file {filename}: {extraction_result}")
            return {
                "success": True, 
                "extracted_fields": extraction_result.get("extraction_data", {}),
                "field_category": extraction_result.get("category", "未识别"),
                "confidence": extraction_result.get("extraction_confidence", 0.0),
                "method": f"{model_type or 'qwen'}_vision"
            }
            
        except Exception as e:
            logger.error(f"Error in field extraction processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "extracted_fields": {},
                "field_category": "未识别",
                "confidence": 0.0,
                "method": "failed"
            }

# 全局字段提取处理服务实例
field_extraction_processor = FieldExtractionProcessor()
