import logging
from typing import Optional, Dict, Any
from app.config import settings, CLASSIFICATION_PROMPT, build_extraction_prompt
from app.models.prompt_schemas import SUPPORTED_CATEGORIES

logger = logging.getLogger(__name__)

class LLMService:
    """LLM服务类 - 统一管理不同AI模型"""
    
    def __init__(self):
        self.categories = ["发票", "租赁协议", "变更/解除协议", "账单", "银行回单"]
        
        # 从配置获取默认模型，如果没有则使用qwen
        from app.config import settings
        self.default_model = getattr(settings, 'llm_default_model', 'qwen')
        logger.info(f"LLM service initialized with default model: {self.default_model}")
    
    def classify_file_sync(self, file_content: bytes, file_type: str, filename: str, model_type: Optional[str] = None) -> Dict[str, Any]:
        """分类文件 - 同步版本"""
        try:
            # 使用默认模型如果未指定
            if not model_type:
                model_type = self.default_model
            
            # 记录使用的模型
            logger.info(f"🤖 Using {model_type.upper()} model for file classification: {filename}")
            
            # 从配置中获取分类提示词
            prompt = CLASSIFICATION_PROMPT.format(filename=filename, file_type=file_type)
            
            # 记录发送给AI模型的分类提示词（用于调试）
            logger.info(f"=== {model_type.upper()} CLASSIFICATION PROMPT ===")
            logger.info(f"Filename: {filename}")
            logger.info(f"File type: {file_type}")
            logger.info(f"Model: {model_type}")
            logger.info(f"Prompt length: {len(prompt)} characters")
            logger.info(f"Full prompt:\n{prompt}")
            logger.info(f"=== END {model_type.upper()} CLASSIFICATION PROMPT ===")
            
            # 根据模型类型调用相应的服务
            if model_type.lower() == "gemini":
                from app.services.gemini_service import gemini_service
                response = gemini_service._classify_file_sync(file_content, file_type, filename, prompt)
            elif model_type.lower() == "qwen":
                from app.services.qwen_service import qwen_service
                response = qwen_service._classify_file_sync(file_content, file_type, filename, prompt)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            # 记录AI模型的原始响应
            logger.info(f"{model_type} raw response for classification from {filename}: {response.get('text', 'No text response')}")
            
            # 解析响应
            result = self._parse_classification_response(response, model_type)
            
            logger.info(f"File classified as: {result.get('category', 'Unknown')} with confidence: {result.get('confidence', 0.0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"File classification failed for file {filename}: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"分类失败: {str(e)}",
                "key_info": "无法处理此文件"
            }
    
    def extract_fields_sync(self, file_content: bytes, file_type: str, filename: str, category: str, model_type: Optional[str] = None) -> Dict[str, Any]:
        """提取字段 - 同步版本"""
        try:
            # 使用默认模型如果未指定
            if not model_type:
                model_type = self.default_model
            
            # 记录使用的模型
            logger.info(f"🤖 Using {model_type.upper()} model for field extraction: {filename} (category: {category})")
            
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
            
            # 记录发送给AI模型的完整提示词（用于调试）
            logger.info(f"=== {model_type.upper()} FIELD EXTRACTION PROMPT FOR {category.upper()} ===")
            logger.info(f"Filename: {filename}")
            logger.info(f"File type: {file_type}")
            logger.info(f"Category: {category}")
            logger.info(f"Model: {model_type}")
            logger.info(f"Prompt length: {len(prompt)} characters")
            logger.info(f"Full prompt:\n{prompt}")
            logger.info(f"=== END {model_type.upper()} FIELD EXTRACTION PROMPT ===")
            
            # 根据模型类型调用相应的服务
            if model_type.lower() == "gemini":
                from app.services.gemini_service import gemini_service
                response = gemini_service._extract_fields_sync(file_content, file_type, filename, prompt)
            elif model_type.lower() == "qwen":
                from app.services.qwen_service import qwen_service
                response = qwen_service._extract_fields_sync(file_content, file_type, filename, prompt)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            # 记录AI模型的原始响应
            logger.info(f"{model_type} raw response for field extraction from {filename}: {response.get('text', 'No text response')}")
            
            # 解析响应
            result = self._parse_extraction_response(response, model_type)
            
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
                "notes": f"提取失败: {str(e)}"
            }
    
    def _parse_classification_response(self, response: Dict[str, Any], model_type: str) -> Dict[str, Any]:
        """解析分类响应"""
        try:
            if model_type.lower() == "gemini":
                # Gemini返回的是text字段
                response_text = response.get("text", "")
            elif model_type.lower() == "qwen":
                # Qwen返回的是text字段
                response_text = response.get("text", "")
            else:
                response_text = str(response)
            
            # 尝试解析JSON响应
            import json
            try:
                # 提取JSON部分（如果响应包含其他文本）
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    parsed = json.loads(json_text)
                else:
                    parsed = json.loads(response_text)
                
                return {
                    "category": parsed.get("category", "未识别"),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "reason": parsed.get("reason", "无理由"),
                    "key_info": parsed.get("key_info", "无关键信息")
                }
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response from {model_type}: {response_text}")
                return {
                    "category": "未识别",
                    "confidence": 0.0,
                    "reason": f"响应格式错误: {response_text[:100]}",
                    "key_info": "无法解析响应"
                }
                
        except Exception as e:
            logger.error(f"Error parsing classification response from {model_type}: {e}")
            return {
                "category": "未识别",
                "confidence": 0.0,
                "reason": f"解析失败: {str(e)}",
                "key_info": "解析错误"
            }
    
    def _parse_extraction_response(self, response: Dict[str, Any], model_type: str) -> Dict[str, Any]:
        """解析字段提取响应"""
        try:
            if model_type.lower() == "gemini":
                # Gemini返回的是text字段
                response_text = response.get("text", "")
            elif model_type.lower() == "qwen":
                # Qwen返回的是text字段
                response_text = response.get("text", "")
            else:
                response_text = str(response)
            
            # 尝试解析JSON响应
            import json
            try:
                # 提取JSON部分（如果响应包含其他文本）
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    parsed = json.loads(json_text)
                else:
                    parsed = json.loads(response_text)
                
                return {
                    "category": parsed.get("category", "未识别"),
                    "classification_confidence": float(parsed.get("classification_confidence", 1.0)),
                    "classification_reason": parsed.get("classification_reason", "使用提供的分类"),
                    "extraction_data": parsed.get("extraction_data", {}),
                    "missing_fields": parsed.get("missing_fields", []),
                    "extraction_confidence": float(parsed.get("extraction_confidence", 0.0)),
                    "notes": parsed.get("notes", "字段提取完成")
                }
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response from {model_type}: {response_text}")
                return {
                    "category": "未识别",
                    "classification_confidence": 0.0,
                    "classification_reason": f"响应格式错误: {response_text[:100]}",
                    "extraction_data": {},
                    "missing_fields": [],
                    "extraction_confidence": 0.0,
                    "notes": f"解析失败: {response_text[:100]}"
                }
                
        except Exception as e:
            logger.error(f"Error parsing extraction response from {model_type}: {e}")
            return {
                "category": "未识别",
                "classification_confidence": 0.0,
                "classification_reason": f"解析失败: {str(e)}",
                "extraction_data": {},
                "missing_fields": [],
                "extraction_confidence": 0.0,
                "notes": f"解析失败: {str(e)}"
            }

# 全局LLM服务实例
llm_service = LLMService()
