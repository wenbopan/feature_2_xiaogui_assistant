#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt-related Pydantic schemas for LLM responses
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
import json

# =============================================================================
# Field Definition Models for LLM Output Schema
# =============================================================================

class BaseExtractionFields(BaseModel):
    """基础提取字段"""
    pass

class InvoiceFields(BaseExtractionFields):
    """发票字段"""
    发票序号: Optional[str] = Field(None, description="发票序号")
    购买方名称: Optional[str] = Field(None, description="购买方名称")
    开票日期: Optional[str] = Field(None, description="开票日期，格式：YYYY-MM-DD")
    含税金额: Optional[str] = Field(None, description="含税金额")
    所属租期: Optional[str] = Field(None, description="所属租期")
    租赁房屋: Optional[str] = Field(None, description="租赁房屋")
    发票号码: Optional[str] = Field(None, description="发票号码")
    备注: Optional[str] = Field(None, description="备注")
    税率: Optional[str] = Field(None, description="税率，可包含百分号等符号")

class LeaseAgreementFields(BaseExtractionFields):
    """租赁协议字段"""
    承租人名称: Optional[str] = Field(None, description="承租人名称")
    租赁合同编号: Optional[str] = Field(None, description="租赁合同编号")
    合同签署日: Optional[str] = Field(None, description="合同签署日，格式：YYYY-MM-DD")
    租赁房屋: Optional[str] = Field(None, description="租赁房屋")
    租赁面积: Optional[str] = Field(None, description="租赁面积（计费面积），可包含单位如平方米等")
    租金条款: Optional[str] = Field(None, description="租金条款")
    账期条款: Optional[str] = Field(None, description="账期条款")
    租赁期限: Optional[str] = Field(None, description="租赁期限")
    免租期条款: Optional[str] = Field(None, description="免租期条款")
    押金条款: Optional[str] = Field(None, description="押金条款")

class AmendmentTerminationFields(BaseExtractionFields):
    """变更/解除协议字段"""
    协议序号: Optional[str] = Field(None, description="协议序号")
    承租人名称: Optional[str] = Field(None, description="承租人名称")
    协议全称: Optional[str] = Field(None, description="协议全称")
    对应变更解除补充的协议编号: Optional[str] = Field(None, description="对应变更/解除/补充的协议编号")
    本协议编号: Optional[str] = Field(None, description="本协议编号")
    主要变更内容: Optional[str] = Field(None, description="主要变更内容")
    签署日期: Optional[str] = Field(None, description="签署日期，格式：YYYY-MM-DD")

class BillFields(BaseExtractionFields):
    """账单字段"""
    账单序号: Optional[str] = Field(None, description="账单序号")
    承租人名称: Optional[str] = Field(None, description="承租人名称")
    租赁房屋: Optional[str] = Field(None, description="租赁房屋")
    含税金额: Optional[str] = Field(None, description="含税金额")
    所属租期: Optional[str] = Field(None, description="所属租期")
    预收租金情况: Optional[str] = Field(None, description="预收租金情况")
    补缴上期租金情况: Optional[str] = Field(None, description="补缴上期租金情况")
    同时缴纳押金情况: Optional[str] = Field(None, description="同时缴纳押金情况")
    租金减免情况: Optional[str] = Field(None, description="租金减免情况")
    账单发出日期: Optional[str] = Field(None, description="账单发出日期，格式：YYYY-MM-DD")

class BankReceiptFields(BaseExtractionFields):
    """银行回单字段"""
    银行回单序号: Optional[str] = Field(None, description="银行回单序号")
    付款人名称: Optional[str] = Field(None, description="付款人名称")
    流水日期: Optional[str] = Field(None, description="流水日期，格式：YYYY-MM-DD")
    转账金额: Optional[str] = Field(None, description="转账金额，可包含货币符号如CNY、USD等")
    所属租期: Optional[str] = Field(None, description="所属租期")
    租赁房屋: Optional[str] = Field(None, description="租赁房屋")
    回单号码: Optional[str] = Field(None, description="回单号码")
    备注摘要: Optional[str] = Field(None, description="备注/摘要")
    付款账号: Optional[str] = Field(None, description="付款账号")

# =============================================================================
# LLM Response Models for Structured Output
# =============================================================================

class ClassificationResponse(BaseModel):
    """文件分类响应模型"""
    category: str = Field(..., description="文件分类结果")
    confidence: float = Field(..., description="分类置信度", ge=0.0, le=1.0)
    reason: str = Field(..., description="分类理由")
    key_info: str = Field(..., description="关键信息摘要")
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError('Confidence must be a number')
        return float(v)
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        valid_categories = ["发票", "租赁协议", "变更/解除协议", "账单", "银行回单", "未识别"]
        if v not in valid_categories:
            raise ValueError(f'Category must be one of: {valid_categories}')
        return v

class FieldExtractionResponse(BaseModel):
    """字段提取响应模型"""
    category: str = Field(..., description="文件分类结果")
    classification_confidence: float = Field(..., description="分类置信度", ge=0.0, le=1.0)
    classification_reason: str = Field(..., description="分类理由")
    extraction_data: Dict[str, Any] = Field(..., description="提取的字段数据")
    missing_fields: List[str] = Field(default_factory=list, description="未能提取的字段列表")
    extraction_confidence: float = Field(..., description="字段提取置信度", ge=0.0, le=1.0)
    notes: str = Field(default="", description="提取说明或备注")
    
    @field_validator('classification_confidence', 'extraction_confidence')
    @classmethod
    def validate_confidence(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError('Confidence must be a number')
        return float(v)
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        valid_categories = ["发票", "租赁协议", "变更/解除协议", "账单", "银行回单", "未识别"]
        if v not in valid_categories:
            raise ValueError(f'Category must be one of: {valid_categories}')
        return v
    
    @field_validator('extraction_data')
    @classmethod
    def validate_extraction_data(cls, v):
        if not isinstance(v, dict):
            raise ValueError('Extraction data must be a dictionary')
        return v

class LLMResponseWrapper(BaseModel):
    """LLM响应包装器，用于处理可能的JSON解析错误"""
    raw_response: str
    parsed_response: Optional[Union[ClassificationResponse, FieldExtractionResponse]] = None
    parse_error: Optional[str] = None
    
    @classmethod
    def from_raw_response(cls, raw_response: str, response_type: str = "classification"):
        """从原始响应创建包装器"""
        try:
            # 尝试提取JSON部分
            start_idx = raw_response.find('{')
            end_idx = raw_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = raw_response[start_idx:end_idx]
                data = json.loads(json_str)
                
                if response_type == "classification":
                    parsed = ClassificationResponse(**data)
                elif response_type == "extraction":
                    parsed = FieldExtractionResponse(**data)
                else:
                    raise ValueError(f"Unknown response type: {response_type}")
                
                return cls(
                    raw_response=raw_response,
                    parsed_response=parsed,
                    parse_error=None
                )
            else:
                return cls(
                    raw_response=raw_response,
                    parsed_response=None,
                    parse_error="No JSON found in response"
                )
                
        except json.JSONDecodeError as e:
            return cls(
                raw_response=raw_response,
                parsed_response=None,
                parse_error=f"JSON decode error: {str(e)}"
            )
        except Exception as e:
            return cls(
                raw_response=raw_response,
                parsed_response=None,
                parse_error=f"Validation error: {str(e)}"
            )

# 支持的文档分类
SUPPORTED_CATEGORIES = ["发票", "租赁协议", "变更/解除协议", "账单", "银行回单", "未识别"]

# 分类字段映射（用于LLM输出schema）
CATEGORY_FIELD_MAPPING = {
    "发票": InvoiceFields,
    "租赁协议": LeaseAgreementFields,
    "变更/解除协议": AmendmentTerminationFields,
    "账单": BillFields,
    "银行回单": BankReceiptFields
}

def get_field_names_for_category(category: str) -> List[str]:
    """获取指定分类的字段名称列表 - 从Pydantic模型获取"""
    field_model = CATEGORY_FIELD_MAPPING.get(category)
    if field_model:
        return list(field_model.__fields__.keys())
    return []

def build_output_schema_for_category(category: str) -> str:
    """为指定分类构建输出JSON schema"""
    field_model = CATEGORY_FIELD_MAPPING.get(category)
    if not field_model:
        return "{}"
    
    # 从Pydantic模型获取字段信息
    schema_fields = []
    for field_name, field_info in field_model.__fields__.items():
        schema_fields.append(f'    "{field_name}": "提取的值"')
    
    schema = "{\n" + ",\n".join(schema_fields) + "\n}"
    return schema
