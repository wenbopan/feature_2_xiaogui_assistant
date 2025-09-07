from openai import OpenAI
from app.config import settings
import logging
from typing import Dict, Any
import base64

logger = logging.getLogger(__name__)

# File size thresholds
QWEN_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes (conservative limit for Qwen)

class QwenService:
    """Qwen服务类 - 使用OpenAI兼容的API"""
    
    def __init__(self):
        # 优先从环境变量获取，如果没有则从配置获取
        import os
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            from app.config import settings
            api_key = settings.qwen_api_key
        
        if not api_key:
            raise ValueError("Qwen API key is required. Please set QWEN_API_KEY environment variable or configure it in settings")
        
        # 使用OpenAI兼容的客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # Qwen的OpenAI兼容端点
        )
        self.model_name = "qwen-vl-plus"
        
        logger.info(f"Qwen service initialized with OpenAI-compatible API and model: {self.model_name}")
    
    def _validate_file_size(self, file_content: bytes, filename: str) -> bool:
        """验证文件大小是否在Qwen API限制范围内"""
        file_size = len(file_content)
        if file_size > QWEN_MAX_FILE_SIZE:
            logger.warning(f"File {filename} is too large ({file_size} bytes) for Qwen API (max: {QWEN_MAX_FILE_SIZE} bytes)")
            return False
        return True
    
    def _get_mime_type(self, file_type: str) -> str:
        """根据文件类型获取MIME类型"""
        if file_type.lower() == '.pdf':
            return "application/pdf"
        elif file_type.lower() in ['.jpg', '.jpeg']:
            return "image/jpeg"
        elif file_type.lower() == '.png':
            return "image/png"
        elif file_type.lower() == '.webp':
            return "image/webp"
        elif file_type.lower() in ['.heic', '.heif']:
            return f"image/{file_type[1:].lower()}"
        else:
            return "application/octet-stream"
    
    def _classify_file_sync(self, file_content: bytes, file_type: str, filename: str, prompt: str) -> Dict[str, Any]:
        """分类文件 - 同步版本"""
        try:
            # 验证文件大小
            if not self._validate_file_size(file_content, filename):
                return {
                    "text": f'{{"category": "未识别", "confidence": 0.0, "reason": "文件过大，超过Qwen API限制", "key_info": "文件大小超过{QWEN_MAX_FILE_SIZE // (1024*1024)}MB"}}'
                }
            
            # 根据文件类型处理
            if file_type.lower() in ['.jpg', '.jpeg', '.png', '.pdf']:
                # 图片和PDF文件使用多模态模型
                return self._call_multimodal_model(prompt, file_content, file_type, "classification")
            else:
                # 文本文件
                try:
                    text_content = file_content.decode('utf-8')
                    return self._call_text_model(prompt, text_content, "classification")
                except UnicodeDecodeError:
                    logger.warning(f"Cannot decode file content for classification from {filename}")
                    return {
                        "text": '{"category": "未识别", "confidence": 0.0, "reason": "文件内容无法解码为文本", "key_info": "无法处理此文件"}'
                    }
                    
        except Exception as e:
            logger.error(f"Qwen classification failed for file {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "confidence": 0.0, "reason": "分类失败: {str(e)}", "key_info": "无法处理此文件"}}'
            }
    
    def _extract_fields_sync(self, file_content: bytes, file_type: str, filename: str, prompt: str) -> Dict[str, Any]:
        """提取字段 - 同步版本"""
        try:
            # 验证文件大小
            if not self._validate_file_size(file_content, filename):
                return {
                    "text": f'{{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "文件过大，超过Qwen API限制", "extraction_data": {{}}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "文件大小超过{QWEN_MAX_FILE_SIZE // (1024*1024)}MB"}}'
                }
            
            # 根据文件类型处理
            if file_type.lower() in ['.jpg', '.jpeg', '.png', '.pdf']:
                # 图片和PDF文件使用多模态模型
                return self._call_multimodal_model(prompt, file_content, file_type, "extraction")
            else:
                # 文本文件
                try:
                    text_content = file_content.decode('utf-8')
                    return self._call_text_model(prompt, text_content, "extraction")
                except UnicodeDecodeError:
                    logger.warning(f"Cannot decode file content for field extraction from {filename}")
                    return {
                        "text": '{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "文件内容无法解码为文本", "extraction_data": {}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "文件内容无法解码为文本"}'
                    }
                    
        except Exception as e:
            logger.error(f"Qwen field extraction failed for file {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "字段提取失败: {str(e)}", "extraction_data": {{}}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "提取失败: {str(e)}"}}'
            }
    
    def _call_multimodal_model(self, prompt: str, file_content: bytes, file_type: str, task_type: str) -> Dict[str, Any]:
        """调用多模态模型API - 使用OpenAI兼容接口"""
        try:
            # 将文件内容编码为base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            mime_type = self._get_mime_type(file_type)
            
            # 使用OpenAI兼容的API调用
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{file_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            # 提取响应文本
            content = response.choices[0].message.content
            return {"text": content}
            
        except Exception as e:
            logger.error(f"Qwen multimodal model call failed: {e}")
            return {
                "text": f'{{"error": "API调用异常: {str(e)}"}}'
            }
    
    def _call_text_model(self, prompt: str, text_content: str, task_type: str) -> Dict[str, Any]:
        """调用文本模型API - 使用OpenAI兼容接口"""
        try:
            # 使用OpenAI兼容的API调用
            response = self.client.chat.completions.create(
                model="qwen-plus",  # 文本模型
                messages=[
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n文件内容:\n{text_content}"
                    }
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            # 提取响应文本
            content = response.choices[0].message.content
            return {"text": content}
            
        except Exception as e:
            logger.error(f"Qwen text model call failed: {e}")
            return {
                "text": f'{{"error": "API调用异常: {str(e)}"}}'
            }

# 全局Qwen服务实例
qwen_service = QwenService()