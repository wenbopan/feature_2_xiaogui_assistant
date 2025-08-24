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
            # 构建分类提示词
            prompt = f"""
            请分析以下文件内容，将其分类为以下5个类别之一：
            1. 发票 - 各类发票文档
            2. 租赁协议 - 物业租赁协议文档  
            3. 变更/解除协议 - 租赁变更或解除协议
            4. 账单 - 各类账单文档
            5. 银行回单 - 银行转账回单
            
            文件名: {filename}
            文件类型: {file_type}
            
            请返回JSON格式的结果：
            {{
                "category": "分类名称",
                "confidence": 0.0-1.0的置信度,
                "reason": "分类理由",
                "key_info": "关键信息摘要"
            }}
            
            如果无法确定分类，请将category设为"未识别"，confidence设为0.0
            """
            
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
            # 构建提取提示词 - 同时要求分类和字段提取
            prompt = f"""
            请分析以下文档，同时进行文件分类和字段提取。
            
            文件名: {filename}
            文件类型: {file_type}
            
            请返回JSON格式的结果：
            {{
                "category": "文件分类结果",
                "classification_confidence": 0.0-1.0的分类置信度,
                "classification_reason": "分类理由",
                "extraction_data": {{
                    "字段名": "提取的值"
                }},
                "missing_fields": ["未能提取的字段列表"],
                "extraction_confidence": 0.0-1.0的提取置信度,
                "notes": "提取说明或备注"
            }}
            
            分类要求：
            请将文件分类为以下5个类别之一：
            1. 发票 - 各类发票文档
            2. 租赁协议 - 物业租赁协议文档  
            3. 变更/解除协议 - 租赁变更或解除协议
            4. 账单 - 各类账单文档
            5. 银行回单 - 银行转账回单
            
            字段提取要求：
            根据分类结果，提取对应的关键字段信息。
            
            注意：
            1. 如果某个字段无法提取，请在missing_fields中列出
            2. 金额字段请保持数字格式，不要包含货币符号
            3. 日期字段请使用YYYY-MM-DD格式
            4. 如果字段值为空或无法确定，请设为null
            5. 分类和字段提取应该基于文件的实际内容
            """
            
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
        """获取字段配置"""
        field_configs = {
            "发票": {
                "购买方名称": "string",
                "开票日期": "date",
                "含税金额": "number",
                "所属租期": "string",
                "租赁(计费)面积": "number",
                "楼栋&房号": "string"
            },
            "租赁协议": {
                "承租人名称": "string",
                "楼栋&房号": "string",
                "租赁(计费)面积": "number",
                "租赁期起止": "string",
                "免租期条款": "string"
            },
            "变更/解除协议": {
                "承租人名称": "string",
                "楼栋&房号": "string",
                "租赁(计费)面积": "number",
                "涉及租赁期、免租期、账期、押金条款的变更情况": "string",
                "涉及租金条款的变更情况": "string"
            },
            "账单": {
                "承租人名称": "string",
                "楼栋&房号": "string",
                "含税金额": "number",
                "所属租期": "string"
            },
            "银行回单": {
                "付款人名称": "string",
                "流水日期": "date",
                "转账金额": "number",
                "所属租期": "string",
                "楼栋&房号": "string"
            }
        }
        
        return field_configs.get(category)
    
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
