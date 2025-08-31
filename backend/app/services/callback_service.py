#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回调服务 - 处理webhook HTTP回调
包括重试逻辑和状态跟踪
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class CallbackStatus(Enum):
    """回调状态枚举"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class CallbackRequest:
    """回调请求数据结构"""
    id: str
    url: str
    payload: Dict[str, Any]
    status: CallbackStatus
    created_at: datetime
    last_attempt: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None

class CallbackService:
    """回调服务类"""
    
    def __init__(self):
        self.callbacks: Dict[str, CallbackRequest] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.retry_delays = [1, 5, 15, 30, 60]  # 重试延迟（秒）
    
    async def initialize(self):
        """初始化HTTP会话"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'Content-Type': 'application/json'}
            )
            logger.info("Callback service HTTP session initialized")
    
    async def cleanup(self):
        """清理HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Callback service HTTP session closed")
    
    async def send_callback(
        self,
        callback_url: str,
        payload: Dict[str, Any],
        callback_id: Optional[str] = None
    ) -> str:
        """发送回调请求"""
        if not callback_id:
            callback_id = f"cb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # 创建回调请求记录
        callback_request = CallbackRequest(
            id=callback_id,
            url=callback_url,
            payload=payload,
            status=CallbackStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.callbacks[callback_id] = callback_request
        
        # 异步发送回调
        asyncio.create_task(self._send_callback_async(callback_request))
        
        logger.info(f"Callback request created: {callback_id} -> {callback_url}")
        return callback_id
    
    async def _send_callback_async(self, callback_request: CallbackRequest):
        """异步发送回调请求"""
        try:
            await self.initialize()
            
            # 准备请求数据
            request_data = {
                **callback_request.payload,
                "callback_id": callback_request.id,
                "timestamp": datetime.now().isoformat()
            }
            
            # 发送HTTP POST请求
            async with self.session.post(
                callback_request.url,
                json=request_data,
                headers={'Content-Type': 'application/json'}
            ) as response:
                
                if response.status in [200, 201, 202]:
                    # 成功
                    callback_request.status = CallbackStatus.SENT
                    callback_request.last_attempt = datetime.now()
                    logger.info(f"Callback sent successfully: {callback_request.id}")
                    
                    # 读取响应内容（可选）
                    try:
                        response_text = await response.text()
                        logger.debug(f"Callback response: {response_text}")
                    except:
                        pass
                        
                else:
                    # HTTP错误
                    error_msg = f"HTTP {response.status}: {response.reason}"
                    await self._handle_callback_failure(callback_request, error_msg)
                    
        except Exception as e:
            # 网络或其他错误
            error_msg = f"Network error: {str(e)}"
            await self._handle_callback_failure(callback_request, error_msg)
    
    async def _handle_callback_failure(self, callback_request: CallbackRequest, error_msg: str):
        """处理回调失败"""
        callback_request.error_message = error_msg
        callback_request.last_attempt = datetime.now()
        
        if callback_request.retry_count < callback_request.max_retries:
            # 重试
            callback_request.status = CallbackStatus.RETRYING
            callback_request.retry_count += 1
            
            # 计算重试延迟
            delay = self.retry_delays[min(callback_request.retry_count - 1, len(self.retry_delays) - 1)]
            
            logger.warning(f"Callback failed, retrying in {delay}s: {callback_request.id} - {error_msg}")
            
            # 延迟重试
            await asyncio.sleep(delay)
            asyncio.create_task(self._send_callback_async(callback_request))
            
        else:
            # 达到最大重试次数
            callback_request.status = CallbackStatus.FAILED
            logger.error(f"Callback failed permanently after {callback_request.max_retries} retries: {callback_request.id} - {error_msg}")
    
    def get_callback_status(self, callback_id: str) -> Optional[Dict[str, Any]]:
        """获取回调状态"""
        if callback_id not in self.callbacks:
            return None
        
        callback = self.callbacks[callback_id]
        return {
            "id": callback.id,
            "url": callback.url,
            "status": callback.status.value,
            "created_at": callback.created_at.isoformat(),
            "last_attempt": callback.last_attempt.isoformat() if callback.last_attempt else None,
            "retry_count": callback.retry_count,
            "max_retries": callback.max_retries,
            "error_message": callback.error_message
        }
    
    def get_all_callbacks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有回调状态"""
        return {cb_id: self.get_callback_status(cb_id) for cb_id in self.callbacks}
    
    async def retry_failed_callbacks(self):
        """重试所有失败的回调"""
        failed_callbacks = [
            cb for cb in self.callbacks.values() 
            if cb.status == CallbackStatus.FAILED and cb.retry_count < cb.max_retries
        ]
        
        for callback in failed_callbacks:
            callback.status = CallbackStatus.RETRYING
            callback.retry_count += 1
            logger.info(f"Retrying failed callback: {callback.id}")
            asyncio.create_task(self._send_callback_async(callback))

# 创建全局实例
callback_service = CallbackService()
