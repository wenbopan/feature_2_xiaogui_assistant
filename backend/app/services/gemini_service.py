from google import genai
from app.config import settings
import logging
from typing import Optional, Dict, Any
import base64
logger = logging.getLogger(__name__)

# File size thresholds
GEMINI_INLINE_SIZE_LIMIT = 20 * 1024 * 1024  # 20MB in bytes

class GeminiService:
    """Gemini服务类 - 使用现代google.genai库"""
    
    def __init__(self):
        # 优先从环境变量获取，如果没有则从配置获取
        import os
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            from app.config import settings
            api_key = settings.gemini_api_key
        
        if not api_key:
            raise ValueError("Gemini API key is required. Please set GEMINI_API_KEY environment variable or configure it in settings")
        
        # 使用现代google.genai库
        self.client = genai.Client(api_key=api_key, http_options={"timeout": 60})
        self.model_name = "gemini-2.5-flash"
        
        logger.info(f"Gemini API configured with model: {self.model_name}")
        logger.info("Gemini service initialized successfully with modern google.genai library")
    
    def _should_use_file_api(self, file_content: bytes) -> bool:
        """判断是否应该使用File API而不是内联数据"""
        return len(file_content) > GEMINI_INLINE_SIZE_LIMIT
    
    def _upload_file_to_gemini(self, file_content: bytes, file_type: str, filename: str) -> str:
        """上传文件到Gemini File API并返回文件URI"""
        try:
            # 创建BytesIO对象来包装文件内容
            import io
            file_obj = io.BytesIO(file_content)
            
            # 使用现代google.genai库上传文件 - 传递IOBase对象和配置
            uploaded_file = self.client.files.upload(
                file=file_obj,
                config={
                    "mime_type": self._get_mime_type(file_type),
                    "display_name": filename
                }
            )
            
            logger.info(f"File uploaded to Gemini File API: {uploaded_file.name}")
            return uploaded_file.name
            
        except Exception as e:
            logger.error(f"Failed to upload file to Gemini File API: {e}")
            raise
    
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
    
    def _create_inline_data(self, file_content: bytes, file_type: str) -> str:
        """创建内联数据（Base64编码）"""
        return base64.b64encode(file_content).decode('utf-8')
    
    def _classify_file_sync(self, file_content: bytes, file_type: str, filename: str, prompt: str) -> Dict[str, Any]:
        """分类文件 - 同步版本（仅API调用）"""
        try:
            # 调用Gemini API - 根据文件大小选择处理方式
            if file_type.lower() in ['.jpg', '.jpeg', '.png', '.pdf', '.webp', '.heic', '.heif']:
                # 图片和PDF文件使用多模态视觉模型
                if self._should_use_file_api(file_content):
                    # 大文件使用File API
                    logger.info(f"File {filename} is large ({len(file_content)} bytes), using File API")
                    file_uri = self._upload_file_to_gemini(file_content, file_type, filename)
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, file_uri]
                    )
                else:
                    # 小文件使用内联数据
                    logger.info(f"File {filename} is small ({len(file_content)} bytes), using inline data")
                    mime_type = self._get_mime_type(file_type)
                    
                    # 使用现代google.genai库的内联数据格式
                    from google.genai import types
                    inline_data = types.Part.from_bytes(
                        data=file_content,
                        mime_type=mime_type
                    )
                    
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, inline_data]
                    )
            else:
                # 文本文件
                try:
                    text_content = file_content.decode('utf-8')
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, text_content]
                    )
                except UnicodeDecodeError:
                    logger.warning(f"Cannot decode file content for classification from {filename}")
                    return {
                        "text": '{"category": "未识别", "confidence": 0.0, "reason": "文件内容无法解码为文本", "key_info": "无法处理此文件"}'
                    }
            
            # 返回原始响应
            return {"text": response.text}
            
        except Exception as e:
            logger.error(f"Gemini classification API call failed for file {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "confidence": 0.0, "reason": "API调用失败: {str(e)}", "key_info": "无法处理此文件"}}'
            }
    
    def _extract_fields_sync(self, file_content: bytes, file_type: str, filename: str, prompt: str) -> Dict[str, Any]:
        """提取字段 - 同步版本（仅API调用）"""
        try:
            # 调用Gemini API - 根据文件大小选择处理方式
            if file_type.lower() in ['.jpg', '.jpeg', '.png', '.pdf', '.webp', '.heic', '.heif']:
                # 图片和PDF文件使用多模态视觉模型
                if self._should_use_file_api(file_content):
                    # 大文件使用File API
                    logger.info(f"File {filename} is large ({len(file_content)} bytes), using File API for extraction")
                    file_uri = self._upload_file_to_gemini(file_content, file_type, filename)
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, file_uri]
                    )
                else:
                    # 小文件使用内联数据
                    logger.info(f"File {filename} is small ({len(file_content)} bytes), using inline data for extraction")
                    mime_type = self._get_mime_type(file_type)
                    
                    # 使用现代google.genai库的内联数据格式
                    from google.genai import types
                    inline_data = types.Part.from_bytes(
                        data=file_content,
                        mime_type=mime_type
                    )
                    
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, inline_data]
                    )
            else:
                # 文本文件
                try:
                    text_content = file_content.decode('utf-8')
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, text_content]
                    )
                except UnicodeDecodeError:
                    logger.warning(f"Cannot decode file content for field extraction from {filename}")
                    return {
                        "text": '{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "文件内容无法解码为文本", "extraction_data": {}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "文件内容无法解码为文本"}'
                    }
            
            # 返回原始响应
            return {"text": response.text}
            
        except Exception as e:
            logger.error(f"Gemini field extraction API call failed for file {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "API调用失败: {str(e)}", "extraction_data": {{}}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "API调用失败"}}'
            }

# 全局Gemini服务实例
gemini_service = GeminiService()