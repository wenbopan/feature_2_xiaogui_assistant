#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单字段提取消费者 - 处理单个文件字段提取请求
处理完成后发送webhook回调
"""

import logging
import time
import asyncio
from typing import Dict, Any
from app.services.kafka_service import kafka_service
from app.consumers.field_extraction_processor import field_extraction_processor
from app.services.callback_service import callback_service
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

class SimpleFieldExtractionConsumer:
    """简单字段提取Kafka消费者服务"""
    
    # 类变量：定义该服务负责的主题
    TOPICS = ["single.file.extraction"]
    
    def __init__(self):
        self.consumer = None
        self.running = False
    
    def start_consumer(self):
        """同步启动消费者"""
        try:
            logger.info("Starting simple field extraction consumer service...")
            logger.debug(f"Using topics: {self.TOPICS}")
            
            # 创建消费者
            logger.debug("Creating Kafka consumer via kafka_service...")
            self.consumer = kafka_service.create_sync_consumer(self.TOPICS)
            logger.debug(f"Consumer created successfully: {self.consumer}")
            
            logger.debug("Setting running flag to True...")
            self.running = True
            
            # 启动消费循环
            logger.debug("Starting consume loop...")
            self._consume_messages()
            
        except Exception as e:
            logger.error(f"Failed to start simple field extraction consumer: {e}")
            raise
    
    def stop_consumer(self):
        """同步停止消费者"""
        try:
            logger.info("Stopping simple field extraction consumer service...")
            logger.debug("Setting running flag to False...")
            self.running = False
            
            # 停止消费者
            if self.consumer:
                logger.debug("Stopping Kafka consumer...")
                self.consumer.close()
                self.consumer = None
                logger.debug("Kafka consumer stopped successfully")
            else:
                logger.debug("No consumer to stop")
            
            logger.info("Simple field extraction consumer service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop simple field extraction consumer: {e}")
    
    def _consume_messages(self):
        """同步消费消息的主循环"""
        try:
            while self.running:
                try:
                    # 同步消费消息
                    message = self.consumer.poll(timeout_ms=1000)
                    if not message:
                        continue
                    
                    # Handle multiple messages from poll result
                    for tp, messages in message.items():
                        for msg in messages:
                            if not self.running:
                                break
                            
                            try:
                                # 解析消息
                                message_data = msg.value
                                topic = msg.topic
                                
                                logger.debug(f"Received message from topic {topic}: {message_data}")
                                
                                # 处理消息
                                self._handle_single_file_extraction_job(message_data, msg)
                                
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                                # 继续处理下一条消息
                                continue
                    
                    if not self.running:
                        break
                        
                except Exception as e:
                    logger.error(f"Error in consume loop: {e}")
                    time.sleep(1)  # 避免无限循环
                    continue
                    
        except Exception as e:
            logger.error(f"Fatal error in consume loop: {e}")
            raise
    
    def _handle_single_file_extraction_job(self, message_data: Dict[str, Any], message):
        """处理单个文件字段提取任务"""
        try:
            # 获取任务信息
            task_id = message_data.get("task_id")
            job_id = message_data.get("job_id")
            s3_key = message_data.get("s3_key")  # MinIO S3 key
            presigned_url = message_data.get("presigned_url")  # 预签名URL
            file_type = message_data.get("file_type")
            callback_url = message_data.get("callback_url")
            delivery_method = message_data.get("delivery_method", "minio")
            
            if not all([task_id, job_id, file_type]):
                logger.error(f"Missing required fields in message: {message_data}")
                return
            
            # 验证至少有一种文件传递方式
            if not s3_key and not presigned_url:
                error_msg = "Neither s3_key nor presigned_url provided in message"
                logger.error(error_msg)
                if callback_url:
                    self._send_error_callback(callback_url, task_id, job_id, error_msg)
                return
            
            logger.info(f"Processing single file extraction job {job_id} for task {task_id} via {delivery_method}")
            
            # 根据传递方式获取文件内容
            if delivery_method == "presigned_url" and presigned_url:
                # 从预签名URL下载文件内容
                try:
                    import aiohttp
                    import asyncio
                    
                    # 创建事件循环来调用异步方法
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        async def download_from_url():
                            async with aiohttp.ClientSession() as session:
                                async with session.get(presigned_url) as response:
                                    if response.status == 200:
                                        return await response.read()
                                    else:
                                        raise Exception(f"HTTP {response.status}")
                        
                        file_content = loop.run_until_complete(download_from_url())
                        logger.info(f"Downloaded file from presigned URL: {len(file_content)} bytes")
                    finally:
                        loop.close()
                        
                except Exception as e:
                    error_msg = f"Failed to download file from presigned URL: {e}"
                    logger.error(error_msg)
                    if callback_url:
                        self._send_error_callback(callback_url, task_id, job_id, error_msg)
                    return
            elif delivery_method == "minio" and s3_key:
                # 从MinIO下载文件内容
                try:
                    file_content = minio_service.get_file_content(s3_key)
                    if not file_content:
                        error_msg = f"Failed to get file content from MinIO: {s3_key}"
                        logger.error(error_msg)
                        if callback_url:
                            self._send_error_callback(callback_url, task_id, job_id, error_msg)
                        return
                    logger.info(f"Downloaded file from MinIO: {len(file_content)} bytes")
                except Exception as e:
                    error_msg = f"Failed to download file from MinIO: {e}"
                    logger.error(error_msg)
                    if callback_url:
                        self._send_error_callback(callback_url, task_id, job_id, error_msg)
                    return
            else:
                error_msg = f"Invalid delivery method or missing content: {delivery_method}"
                logger.error(error_msg)
                if callback_url:
                    self._send_error_callback(callback_url, task_id, job_id, error_msg)
                return
            
            # 处理字段提取 - 调用异步方法
            import asyncio
            try:
                # Create event loop for async call
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 准备数据传递给处理器
                extraction_data = {
                    'file_id': 0,  # 临时ID
                    's3_key': "",  # 空字符串，因为文件内容直接传递
                    'file_type': file_type,
                    'filename': f"single_file_{task_id}{file_type}"
                }
                
                # 调用字段提取处理器
                result = loop.run_until_complete(
                    field_extraction_processor.process_field_extraction(extraction_data, None)
                )
            finally:
                loop.close()
            
            if result and result.get("success"):
                # 提取成功
                success_result = {
                    "task_id": task_id,
                    "job_id": job_id,
                    "status": "completed",
                    "result": {
                        "extracted_fields": result.get("extracted_fields", {}),
                        "field_category": result.get("field_category", "未识别"),
                        "confidence": result.get("confidence", 0.0),
                        "method": "gemini_vision"
                    },
                    "timestamp": time.time()
                }
                
                logger.info(f"Single file extraction completed for job {job_id}: {result}")
                
                # 发送成功回调
                if callback_url:
                    self._send_success_callback(callback_url, success_result)
                    
            else:
                # 提取失败
                error_msg = f"Field extraction failed: {result}"
                logger.warning(error_msg)
                
                if callback_url:
                    self._send_error_callback(callback_url, task_id, job_id, error_msg)
                
        except Exception as e:
            error_msg = f"Error handling single file extraction job: {e}"
            logger.error(error_msg)
            
            # 尝试发送错误回调
            try:
                callback_url = message_data.get("callback_url")
                task_id = message_data.get("task_id")
                job_id = message_data.get("job_id")
                
                if callback_url and task_id and job_id:
                    self._send_error_callback(callback_url, task_id, job_id, error_msg)
            except:
                pass
    
    def _send_success_callback(self, callback_url: str, result: Dict[str, Any]):
        """发送成功回调"""
        try:
            # 异步发送回调
            asyncio.create_task(
                callback_service.send_callback(callback_url, result)
            )
            logger.info(f"Success callback sent to: {callback_url}")
        except Exception as e:
            logger.error(f"Failed to send success callback: {e}")
    
    def _send_error_callback(self, callback_url: str, task_id: str, job_id: str, error_msg: str):
        """发送错误回调"""
        try:
            error_result = {
                "task_id": task_id,
                "job_id": job_id,
                "status": "failed",
                "error": error_msg,
                "timestamp": time.time()
            }
            
            # 异步发送回调
            asyncio.create_task(
                callback_service.send_callback(callback_url, error_result)
            )
            logger.info(f"Error callback sent to: {callback_url}")
        except Exception as e:
            logger.error(f"Failed to send error callback: {e}")

# 创建全局实例
simple_field_extraction_consumer = SimpleFieldExtractionConsumer()
