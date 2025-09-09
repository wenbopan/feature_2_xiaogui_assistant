from openai import OpenAI
from app.config import settings
import logging
from typing import Dict, Any, List
import base64
import io
from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger(__name__)

# File size thresholds
QWEN_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes for individual images
# Use config max_file_size for PDF files (100MB)

class QwenService:
    """Qwen服务类 - 使用OpenAI兼容的API"""
    
    def __init__(self):
        # 优先从环境变量获取，如果没有则从配置获取
        import os
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
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
    
    def _validate_file_size(self, file_content: bytes, filename: str, is_pdf: bool = False) -> bool:
        """验证文件大小是否在Qwen API限制范围内"""
        file_size = len(file_content)
        max_size = settings.max_file_size if is_pdf else QWEN_MAX_FILE_SIZE
        if file_size > max_size:
            logger.warning(f"File {filename} is too large ({file_size} bytes) for Qwen API (max: {max_size} bytes)")
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
    
    def _convert_pdf_to_images(self, pdf_content: bytes, filename: str) -> List[bytes]:
        """将PDF转换为图像列表"""
        try:
            # 使用pdf2image转换PDF为图像
            # 设置DPI为200以获得平衡的质量和文件大小
            images = convert_from_bytes(
                pdf_content,
                dpi=200,  # 平衡质量和文件大小
                first_page=1,
                last_page=60,  # 支持最多60页，充分利用Qwen的高分辨率图像处理能力
                fmt='JPEG',
                jpegopt={'quality': 80, 'optimize': True}  # 降低质量以减小文件大小
            )
            
            # 将PIL图像转换为字节
            image_bytes_list = []
            for i, image in enumerate(images):
                # 如果图像太大，进行压缩
                if image.width > 1536 or image.height > 1536:
                    image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
                
                # 转换为字节
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=80, optimize=True)
                image_bytes = img_byte_arr.getvalue()
                
                # 检查单个图像大小
                if len(image_bytes) > QWEN_MAX_FILE_SIZE:
                    logger.warning(f"PDF page {i+1} from {filename} is too large after conversion, skipping")
                    continue
                    
                image_bytes_list.append(image_bytes)
                logger.info(f"Converted PDF page {i+1} from {filename} to image ({len(image_bytes)} bytes)")
            
            logger.info(f"Successfully converted {len(image_bytes_list)} pages from PDF {filename} (max 60 pages supported)")
            
            if not image_bytes_list:
                raise ValueError("No valid images could be extracted from PDF")
                
            return image_bytes_list
            
        except Exception as e:
            logger.error(f"Failed to convert PDF {filename} to images: {e}")
            raise ValueError(f"PDF转换失败: {str(e)}")
    
    def _classify_pdf_file(self, prompt: str, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """分类PDF文件 - 转换为图像后处理"""
        try:
            # 转换PDF为图像
            image_bytes_list = self._convert_pdf_to_images(pdf_content, filename)
            
            # 处理所有页面图像
            if image_bytes_list:
                logger.info(f"Processing {len(image_bytes_list)} pages of PDF {filename} for classification")
                return self._call_multimodal_model_with_multiple_images(prompt, image_bytes_list, "classification")
            else:
                return {
                    "text": '{"category": "未识别", "confidence": 0.0, "reason": "PDF无法转换为图像", "key_info": "无法处理此PDF文件"}'
                }
                
        except Exception as e:
            logger.error(f"PDF classification failed for {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "confidence": 0.0, "reason": "PDF分类失败: {str(e)}", "key_info": "无法处理此PDF文件"}}'
            }
    
    def _classify_file_sync(self, file_content: bytes, file_type: str, filename: str, prompt: str) -> Dict[str, Any]:
        """分类文件 - 同步版本"""
        try:
            # 验证文件大小
            if not self._validate_file_size(file_content, filename, is_pdf=True):
                return {
                    "text": f'{{"category": "未识别", "confidence": 0.0, "reason": "文件过大，超过Qwen API限制", "key_info": "文件大小超过{settings.max_file_size // (1024*1024)}MB"}}'
                }
            
            # 根据文件类型处理
            if file_type.lower() == '.pdf':
                # PDF文件需要先转换为图像
                return self._classify_pdf_file(prompt, file_content, filename)
            elif file_type.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif']:
                # 图片文件直接使用多模态模型
                return self._call_multimodal_model(prompt, file_content, file_type, "classification")
            else:
                # 其他文件类型不支持
                logger.warning(f"Unsupported file type {file_type} for classification from {filename}")
                return {
                    "text": '{"category": "未识别", "confidence": 0.0, "reason": "不支持的文件类型", "key_info": "仅支持PDF和图片文件"}'
                }
                    
        except Exception as e:
            logger.error(f"Qwen classification failed for file {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "confidence": 0.0, "reason": "分类失败: {str(e)}", "key_info": "无法处理此文件"}}'
            }
    
    def _extract_pdf_fields(self, prompt: str, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """提取PDF字段 - 转换为图像后处理"""
        try:
            # 转换PDF为图像
            image_bytes_list = self._convert_pdf_to_images(pdf_content, filename)
            
            # 处理所有页面图像
            if image_bytes_list:
                logger.info(f"Processing {len(image_bytes_list)} pages of PDF {filename} for field extraction")
                return self._call_multimodal_model_with_multiple_images(prompt, image_bytes_list, "extraction")
            else:
                return {
                    "text": '{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "PDF无法转换为图像", "extraction_data": {}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "无法处理此PDF文件"}'
                }
                
        except Exception as e:
            logger.error(f"PDF field extraction failed for {filename}: {e}")
            return {
                "text": f'{{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "PDF字段提取失败: {str(e)}", "extraction_data": {{}}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "无法处理此PDF文件"}}'
            }
    
    def _extract_fields_sync(self, file_content: bytes, file_type: str, filename: str, prompt: str) -> Dict[str, Any]:
        """提取字段 - 同步版本"""
        try:
            # 验证文件大小
            if not self._validate_file_size(file_content, filename, is_pdf=True):
                return {
                    "text": f'{{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "文件过大，超过Qwen API限制", "extraction_data": {{}}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "文件大小超过{settings.max_file_size // (1024*1024)}MB"}}'
                }
            
            # 根据文件类型处理
            if file_type.lower() == '.pdf':
                # PDF文件需要先转换为图像
                return self._extract_pdf_fields(prompt, file_content, filename)
            elif file_type.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif']:
                # 图片文件直接使用多模态模型
                return self._call_multimodal_model(prompt, file_content, file_type, "extraction")
            else:
                # 其他文件类型不支持
                logger.warning(f"Unsupported file type {file_type} for field extraction from {filename}")
                return {
                    "text": '{"category": "未识别", "classification_confidence": 0.0, "classification_reason": "不支持的文件类型", "extraction_data": {}, "missing_fields": [], "extraction_confidence": 0.0, "notes": "仅支持PDF和图片文件"}'
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
            
            # 构建系统提示词
            system_prompt = "You are an AI specialized in recognizing and extracting text from images. Your mission is to analyze the image document and generate the result while maintaining user privacy and data integrity."
            
            # 根据任务类型设置参数
            extra_params = {}
            if task_type == "extraction":
                extra_params = {
                    "presence_penalty": 1.5
                }
            
            # 使用OpenAI兼容的API调用
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
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
                temperature=0.1,
                **extra_params
            )
            
            # 提取响应文本
            content = response.choices[0].message.content
            return {"text": content}
            
        except Exception as e:
            logger.error(f"Qwen multimodal model call failed: {e}")
            return {
                "text": f'{{"error": "API调用异常: {str(e)}"}}'
            }
    
    def _call_multimodal_model_with_multiple_images(self, prompt: str, image_bytes_list: List[bytes], task_type: str) -> Dict[str, Any]:
        """调用多模态模型API - 处理多张图像"""
        try:
            # 构建系统提示词
            system_prompt = "You are an AI specialized in recognizing and extracting text from images. Your mission is to analyze the image document and generate the result while maintaining user privacy and data integrity."
            
            # 构建消息内容
            content = [{"type": "text", "text": prompt}]
            
            # 添加所有图像
            for i, image_bytes in enumerate(image_bytes_list):
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                })
                logger.info(f"Added image {i+1} to multimodal request ({len(image_bytes)} bytes)")
            
            # 根据任务类型设置参数
            extra_params = {}
            if task_type == "extraction":
                extra_params = {
                    "presence_penalty": 1.5
                }
            
            # 使用OpenAI兼容的API调用
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=4000,
                temperature=0.1,
                **extra_params
            )
            
            # 提取响应文本
            content = response.choices[0].message.content
            return {"text": content}
            
        except Exception as e:
            logger.error(f"Qwen multimodal model call with multiple images failed: {e}")
            return {
                "text": f'{{"error": "API调用异常: {str(e)}"}}'
            }
    

# 全局Qwen服务实例
qwen_service = QwenService()