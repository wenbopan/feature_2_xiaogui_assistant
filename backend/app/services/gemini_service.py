import google.generativeai as genai
from app.config import settings
import logging
from typing import Optional, Dict, Any, List
import json

logger = logging.getLogger(__name__)

class GeminiService:
    """Gemini服务类"""
    
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key is required")
        
        genai.configure(api_key=settings.gemini_api_key)
        # 强制使用正确的模型名称，忽略环境变量中的错误设置
        model_name = "gemini-1.5-flash"
        logger.info(f"Gemini API configured with model: {model_name}")
        self.model = genai.GenerativeModel(model_name)
        self.categories = ["发票", "租赁协议", "变更/解除协议", "账单", "银行回单"]
        
        logger.info("Gemini service initialized successfully")
    
    def _classify_file_sync(self, file_content: bytes, file_type: str, filename: str) -> Dict[str, Any]:
        """分类文件 - 同步版本（在executor中运行）"""
        try:
            # 从配置中获取分类提示词
            from app.config import CLASSIFICATION_PROMPT
            prompt = CLASSIFICATION_PROMPT.format(filename=filename, file_type=file_type)
            
            # 调用Gemini API - 统一使用视觉模型处理所有文件类型
            if file_type.lower() in ['.jpg', '.jpeg', '.png', '.pdf']:
                # 图片和PDF文件都使用多模态视觉模型
                # 对于PDF，Gemini可以理解文档布局、表格、图表等
                from google.generativeai.types import content_types
                
                # 根据文件类型设置正确的MIME类型
                if file_type.lower() == '.pdf':
                    mime_type = "application/pdf"
                else:
                    mime_type = f"image/{file_type[1:].lower()}"
                
                # 创建Blob对象 - 使用测试脚本中成功的方法
                try:
                    if hasattr(content_types, 'Blob'):
                        blob = content_types.Blob(mime_type=mime_type, data=file_content)
                    elif hasattr(content_types, 'BlobDict'):
                        blob = content_types.BlobDict(mime_type=mime_type, data=file_content)
                    else:
                        # 降级到字典格式
                        blob = {
                            "mime_type": mime_type,
                            "data": file_content
                        }
                        logger.info(f"Using dictionary format for blob creation")
                except Exception as e:
                    logger.error(f"Failed to create blob: {e}")
                    # 最终降级到字典格式
                    blob = {
                        "mime_type": mime_type,
                        "data": file_content
                    }
                
                response = self.model.generate_content([prompt, blob])
            else:
                # 其他文本文件，尝试解码为文本
                try:
                    text_content = file_content.decode('utf-8')
                    response = self.model.generate_content([prompt, text_content])
                except UnicodeDecodeError:
                    logger.warning(f"Cannot decode file content for {filename}")
                    return {
                        "category": "未识别",
                        "confidence": 0.0,
                        "reason": "文件内容无法解码为文本",
                        "key_info": "",
                        "raw_response": None
                    }
            
            # 记录Gemini的原始响应
            logger.info(f"Gemini raw response for {filename}: {response.text}")
            
            # 解析响应
            result = self._parse_classification_response(response.text)
            result["raw_response"] = response.text  # 添加原始响应
            logger.info(f"File {filename} classified as {result.get('category', 'unknown')} with confidence {result.get('confidence', 0.0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to classify file {filename}: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"分类失败: {str(e)}",
                "key_info": ""
            }
    
    def _extract_fields_sync(self, file_content: bytes, file_type: str, filename: str, category: str) -> Dict[str, Any]:
        """提取字段 - 同步版本（在executor中运行）"""
        try:
            from app.config import build_extraction_prompt
            from app.models.prompt_schemas import SUPPORTED_CATEGORIES
            
            # 验证分类参数
            if not category or category.strip() == "":
                raise ValueError("Category is required for field extraction")
            
            # 验证分类是否在支持的类别中
            if category not in SUPPORTED_CATEGORIES:
                raise ValueError(f"Unsupported category '{category}'. Supported categories: {SUPPORTED_CATEGORIES}")
            
            # 使用提供的分类信息
            classification_confidence = 1.0  # 假设提供的分类是准确的
            classification_reason = "使用提供的分类"
            
            if category == "未识别":
                return {
                    "category": "未识别",
                    "classification_confidence": classification_confidence,
                    "classification_reason": classification_reason,
                    "extraction_data": {},
                    "missing_fields": [],
                    "extraction_confidence": 0.0,
                    "notes": "文档类型未识别，无法进行字段提取"
                }
            
            # 构建提取提示词
            prompt = build_extraction_prompt(category)
            
            # 调用Gemini API - 完全参照内容分类的实现，统一使用视觉模型
            if file_type.lower() in ['.jpg', '.jpeg', '.png', '.pdf']:
                # 图片和PDF文件都使用多模态视觉模型
                # 对于PDF，Gemini可以理解文档布局、表格、图表等
                from google.generativeai.types import content_types
                
                # 根据文件类型设置正确的MIME类型
                if file_type.lower() == '.pdf':
                    mime_type = "application/pdf"
                else:
                    mime_type = f"image/{file_type[1:].lower()}"
                
                # 创建Blob对象 - 使用和内容分类完全一致的方法
                try:
                    if hasattr(content_types, 'Blob'):
                        blob = content_types.Blob(mime_type=mime_type, data=file_content)
                    elif hasattr(content_types, 'BlobDict'):
                        blob = content_types.BlobDict(mime_type=mime_type, data=file_content)
                    else:
                        # 降级到字典格式
                        blob = {
                            "mime_type": mime_type,
                            "data": file_content
                        }
                        logger.info(f"Using dictionary format for blob creation in field extraction")
                except Exception as e:
                    logger.error(f"Failed to create blob for field extraction: {e}")
                    # 最终降级到字典格式
                    blob = {
                        "mime_type": mime_type,
                        "data": file_content
                    }
                
                response = self.model.generate_content([prompt, blob])
            else:
                # 其他文本文件，尝试解码为文本
                try:
                    text_content = file_content.decode('utf-8')
                    response = self.model.generate_content([prompt, text_content])
                except UnicodeDecodeError:
                    logger.warning(f"Cannot decode file content for field extraction from {filename}")
                    return {
                        "category": "未识别",
                        "classification_confidence": 0.0,
                        "classification_reason": "文件内容无法解码为文本",
                        "extraction_data": {},
                        "missing_fields": [],
                        "extraction_confidence": 0.0,
                        "error": "文件内容无法解码为文本"
                    }
            
            # 记录Gemini的原始响应
            logger.info(f"Gemini raw response for field extraction from {filename}: {response.text}")
            
            # 解析响应
            result = self._parse_extraction_response(response.text)
            
            # 确保使用正确的分类信息
            result["category"] = category
            result["classification_confidence"] = classification_confidence
            result["classification_reason"] = classification_reason
            
            logger.info(f"Fields extracted from {filename}, category: {category}")
            
            return result
            
        except Exception as e:
            logger.error(f"Field extraction failed for file {filename}: {e}")
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": f"字段提取失败: {str(e)}",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "error": f"字段提取失败: {str(e)}"
            }
    
    def _get_field_config(self, category: str) -> Optional[Dict[str, Any]]:
        """获取字段配置 - 从prompt_schemas中读取"""
        from app.models.prompt_schemas import get_field_names_for_category, SUPPORTED_CATEGORIES
        
        if category in SUPPORTED_CATEGORIES and category != "未识别":
            return {
                "name": category,
                "display_name": category,
                "description": f"{category}文档",
                "confidence_threshold": 0.6,
                "extraction_fields": get_field_names_for_category(category)
            }
        
        return None
    
    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """解析分类响应 - 使用Pydantic模型"""
        from app.models.prompt_schemas import LLMResponseWrapper
        
        try:
            wrapper = LLMResponseWrapper.from_raw_response(response_text, "classification")
            
            if wrapper.parsed_response:
                return {
                    "category": wrapper.parsed_response.category,
                    "confidence": wrapper.parsed_response.confidence,
                    "reason": wrapper.parsed_response.reason,
                    "key_info": wrapper.parsed_response.key_info
                }
            else:
                logger.warning(f"Failed to parse classification response: {wrapper.parse_error}")
                return {
                    "category": "未识别",
                    "confidence": 0.0,
                    "reason": f"解析失败: {wrapper.parse_error}",
                    "key_info": response_text[:200] + "..." if len(response_text) > 200 else response_text
                }
                
        except Exception as e:
            logger.error(f"Error parsing classification response: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"解析失败: {str(e)}",
                "key_info": ""
            }
    
    def _parse_extraction_response(self, response_text: str) -> Dict[str, Any]:
        """解析字段提取响应 - 使用Pydantic模型"""
        from app.models.prompt_schemas import LLMResponseWrapper
        
        try:
            wrapper = LLMResponseWrapper.from_raw_response(response_text, "extraction")
            
            if wrapper.parsed_response:
                return {
                    "category": wrapper.parsed_response.category,
                    "classification_confidence": wrapper.parsed_response.classification_confidence,
                    "classification_reason": wrapper.parsed_response.classification_reason,
                    "extraction_data": wrapper.parsed_response.extraction_data,
                    "missing_fields": wrapper.parsed_response.missing_fields,
                    "extraction_confidence": wrapper.parsed_response.extraction_confidence,
                    "notes": wrapper.parsed_response.notes
                }
            else:
                logger.warning(f"Failed to parse extraction response: {wrapper.parse_error}")
                return {
                    "category": "未识别",
                    "classification_confidence": 0.0,
                    "classification_reason": f"解析失败: {wrapper.parse_error}",
                    "extraction_data": {},
                    "missing_fields": [],
                    "extraction_confidence": 0.0,
                    "notes": f"解析失败: {wrapper.parse_error}"
                }
                
        except Exception as e:
            logger.error(f"Error parsing extraction response: {e}")
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": f"解析失败: {str(e)}",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "notes": f"解析失败: {str(e)}"
            }
    
    def classify_file_sync(self, file_content: bytes, file_type: str, filename: str) -> Dict[str, Any]:
        """分类文件 - 同步版本（供同步消费者直接调用）"""
        return self._classify_file_sync(file_content, file_type, filename)
    
    def extract_fields_sync(self, file_content: bytes, file_type: str, filename: str, category: str) -> Dict[str, Any]:
        """提取字段 - 同步版本（供同步消费者直接调用）"""
        return self._extract_fields_sync(file_content, file_type, filename, category)

# 全局Gemini服务实例
gemini_service = GeminiService()
