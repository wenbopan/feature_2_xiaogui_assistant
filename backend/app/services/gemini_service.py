import google.generativeai as genai
from app.config import settings
import logging
from typing import Optional, Dict, Any, List
import json
import base64
import asyncio

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
    
    async def classify_file(self, file_content: bytes, file_type: str, filename: str) -> Dict[str, Any]:
        """分类文件 - 异步版本"""
        try:
            # 使用asyncio.to_thread来避免阻塞事件循环，并添加超时
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._classify_file_sync, file_content, file_type, filename),
                timeout=30.0  # 30秒超时
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Gemini API call timeout for file: {filename}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": "Gemini API调用超时",
                "key_info": "",
                "raw_response": None
            }
        except Exception as e:
            logger.error(f"Async classification failed: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"异步分类失败: {str(e)}",
                "key_info": "",
                "raw_response": None
            }
    
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
    
    async def extract_fields(self, file_content: bytes, file_type: str, filename: str) -> Dict[str, Any]:
        """提取字段 - 同时进行文件分类和字段提取 - 异步版本"""
        try:
            # 使用asyncio.to_thread来避免阻塞事件循环，并添加超时
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._extract_fields_sync, file_content, file_type, filename),
                timeout=30.0  # 30秒超时
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Gemini API call timeout for field extraction from file: {filename}")
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": "Gemini API调用超时",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "error": "Gemini API调用超时"
            }
        except Exception as e:
            logger.error(f"Async field extraction failed: {e}")
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": f"异步字段提取失败: {str(e)}",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "error": f"异步字段提取失败: {str(e)}"
            }
    
    def _extract_fields_sync(self, file_content: bytes, file_type: str, filename: str) -> Dict[str, Any]:
        """提取字段 - 同时进行文件分类和字段提取 - 同步版本（在executor中运行）"""
        try:
            # 从配置中获取字段提取提示词
            from app.config import COMBINED_EXTRACTION_PROMPT
            from app.models.schemas import CATEGORY_FIELD_NAMES
            
            # 获取各分类的字段列表
            invoice_fields = "\n   ".join(CATEGORY_FIELD_NAMES["发票"])
            lease_fields = "\n   ".join(CATEGORY_FIELD_NAMES["租赁协议"])
            amendment_fields = "\n   ".join(CATEGORY_FIELD_NAMES["变更/解除协议"])
            bill_fields = "\n   ".join(CATEGORY_FIELD_NAMES["账单"])
            bank_fields = "\n   ".join(CATEGORY_FIELD_NAMES["银行回单"])
            
            prompt = COMBINED_EXTRACTION_PROMPT.format(
                filename=filename, 
                file_type=file_type,
                invoice_fields=invoice_fields,
                lease_fields=lease_fields,
                amendment_fields=amendment_fields,
                bill_fields=bill_fields,
                bank_fields=bank_fields
            )
            
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
            logger.info(f"Fields extracted from {filename}, category: {result.get('category', 'unknown')}")
            
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
        """获取字段配置 - 从schemas中读取"""
        from app.models.schemas import CATEGORY_CONFIGS
        
        if category in CATEGORY_CONFIGS:
            config = CATEGORY_CONFIGS[category]
            return {
                "name": config.name,
                "display_name": config.display_name,
                "description": config.description,
                "confidence_threshold": config.confidence_threshold,
                "extraction_fields": config.extraction_fields
            }
        
        return None
    
    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """解析分类响应"""
        try:
            # 尝试提取JSON部分
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # 验证必要字段
                if 'category' in result and 'confidence' in result:
                    return {
                        "category": result.get("category", "未识别"),
                        "confidence": float(result.get("confidence", 0.0)),
                        "reason": result.get("reason", ""),
                        "key_info": result.get("key_info", "")
                    }
            
            # 如果无法解析JSON，尝试从文本中提取信息
            return self._extract_info_from_text(response_text)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return self._extract_info_from_text(response_text)
        except Exception as e:
            logger.error(f"Error parsing classification response: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"解析失败: {str(e)}",
                "key_info": ""
            }
    
    def _parse_extraction_response(self, response_text: str) -> Dict[str, Any]:
        """解析字段提取响应 - 包含分类和字段提取信息"""
        try:
            # 尝试提取JSON部分
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # 验证必要字段
                if 'category' in result and 'extraction_data' in result:
                    return {
                        "category": result.get("category", "未识别"),
                        "classification_confidence": float(result.get("classification_confidence", 0.0)),
                        "classification_reason": result.get("classification_reason", ""),
                        "extraction_data": result.get("extraction_data", {}),
                        "missing_fields": result.get("missing_fields", []),
                        "extraction_confidence": float(result.get("extraction_confidence", 0.0)),
                        "notes": result.get("notes", "")
                    }
            
            # 如果无法解析JSON，返回默认结果
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": "无法解析响应",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "notes": "无法解析响应"
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction JSON response: {e}")
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": f"JSON解析失败: {str(e)}",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "notes": f"JSON解析失败: {str(e)}"
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
    
    def _extract_info_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取信息"""
        text_lower = text.lower()
        
        # 简单的关键词匹配
        category = "未识别"
        confidence = 0.0
        
        if "发票" in text:
            category = "发票"
            confidence = 0.7
        elif "租赁协议" in text or "租赁合同" in text:
            category = "租赁协议"
            confidence = 0.7
        elif "变更" in text or "解除" in text:
            category = "变更/解除协议"
            confidence = 0.7
        elif "账单" in text or "费用" in text:
            category = "账单"
            confidence = 0.7
        elif "银行" in text or "转账" in text or "回单" in text:
            category = "银行回单"
            confidence = 0.7
        
        return {
            "category": category,
            "confidence": confidence,
            "reason": "基于关键词匹配",
            "key_info": text[:200] + "..." if len(text) > 200 else text
        }

# 全局Gemini服务实例
gemini_service = GeminiService()
