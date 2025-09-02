#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单文件分类消费者 - 处理单个文件分类请求
处理完成后发送webhook回调
"""

import logging
import time
from typing import Dict, Any

from app.consumers.file_classification_processor import content_processor
from app.services.callback_service import callback_service
from app.services.minio_service import minio_service
from app.models.schemas import SingleFileKafkaMessage, SingleFileClassificationJobData

logger = logging.getLogger(__name__)

class SimpleFileClassificationConsumer:
    """简单文件分类Kafka消费者服务"""
    
    # 类变量：定义该服务负责的主题
    TOPICS = ["single.file.classification"]
    
    def __init__(self):
        self.consumer = None
        self.running = False
    
    def start_consumer(self):
        """同步启动消费者"""
        try:
            logger.info("Starting simple file classification consumer service...")
            logger.debug(f"Using topics: {self.TOPICS}")
            
            # 创建消费者
            logger.debug("Creating Kafka consumer directly...")
            from kafka import KafkaConsumer
            import json
            
            self.consumer = KafkaConsumer(
                *self.TOPICS,
                bootstrap_servers=['localhost:9092'],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda m: m.decode('utf-8') if m else None,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id="legal_docs_consumers"
            )
            logger.debug(f"Consumer created successfully: {self.consumer}")
            
            logger.debug("Setting running flag to True...")
            self.running = True
            
            # 启动消费循环
            logger.debug("Starting consume loop...")
            self._consume_messages()
            
        except Exception as e:
            logger.error(f"Failed to start simple file classification consumer: {e}")
            raise
    
    def stop_consumer(self):
        """同步停止消费者 - 优雅关闭"""
        try:
            logger.info("Stopping simple file classification consumer service...")
            logger.debug("Setting running flag to False...")
            self.running = False
            
            # 优雅停止消费者
            if self.consumer:
                # 等待一下让消费者有机会退出循环
                import time
                time.sleep(2)
                
                logger.debug("Closing Kafka consumer...")
                # 关闭消费者
                self.consumer.close()
                self.consumer = None
                logger.debug("Kafka consumer stopped successfully")
            else:
                logger.debug("No consumer to stop")
            
            logger.info("Simple file classification consumer service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop simple file classification consumer: {e}")
    
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
                                self._handle_single_file_classification_job(message_data, msg)
                                
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
    
    def _handle_single_file_classification_job(self, message_data: Dict[str, Any], message):
        """处理单个文件分类任务"""
        try:
            # 使用Pydantic验证消息数据
            try:
                # 解析为SingleFileKafkaMessage (wrapped format)
                kafka_message = SingleFileKafkaMessage(**message_data)
                
                # 类型检查：使用消息类型字段
                if kafka_message.data.type == "single_file_classification_job":
                    # 解析为SingleFileClassificationJobData - the data is directly in kafka_message.data
                    job_data = SingleFileClassificationJobData(**kafka_message.data.model_dump())
                    logger.debug(f"Parsed single file classification job: {job_data}")
                else:
                    logger.warning(f"Unknown message type: {kafka_message.data.type}")
                    return
                    
            except Exception as e:
                logger.error(f"Invalid message format: {e}")
                logger.error(f"Message data keys: {list(message_data.keys()) if isinstance(message_data, dict) else 'Not a dict'}")
                return
            
            # 提取验证后的字段
            task_id = job_data.task_id
            job_id = job_data.job_id
            file_id = job_data.file_id
            s3_key = job_data.s3_key
            presigned_url = job_data.presigned_url
            file_type = job_data.file_type
            callback_url = job_data.callback_url
            delivery_method = job_data.delivery_method
            
            # 验证至少有一种文件传递方式
            if not s3_key and not presigned_url:
                error_msg = "Neither s3_key nor presigned_url provided in message"
                logger.error(error_msg)
                if callback_url:
                    self._send_error_callback(callback_url, file_id, task_id, job_id, error_msg)
                return
            
            logger.info(f"Processing single file classification job {job_id} for task {task_id} via {delivery_method}")
            
            # 根据传递方式获取文件内容
            if delivery_method == "presigned_url" and presigned_url:
                # 从预签名URL下载文件内容
                try:
                    import requests
                    
                    response = requests.get(presigned_url, timeout=30)
                    if response.status_code == 200:
                        file_content = response.content
                        logger.info(f"Downloaded file from presigned URL: {len(file_content)} bytes")
                    else:
                        raise Exception(f"HTTP {response.status_code}")
                        
                except Exception as e:
                    error_msg = f"Failed to download file from presigned URL: {e}"
                    logger.error(error_msg)
                    if callback_url:
                        self._send_error_callback(callback_url, file_id, task_id, job_id, error_msg)
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
                        self._send_error_callback(callback_url, file_id, task_id, job_id, error_msg)
                    return
            else:
                error_msg = f"Invalid delivery method or missing content: {delivery_method}"
                logger.error(error_msg)
                if callback_url:
                    self._send_error_callback(callback_url, file_id, task_id, job_id, error_msg)
                return
            
            # 处理文件分类 - 调用同步处理器
            result = content_processor.process_file_content(file_content, file_type, f"single_file_{task_id}{file_type}")
            
            if result and result.get("success") and result.get("category") != "未识别":
                # 分类成功
                category = result.get("category")
                is_recognized = 1  # 已识别
                
                logger.info(f"Single file classification completed for job {job_id}: {result}")
                
                # 发送成功回调 - 使用新的预定义格式
                if callback_url:
                    self._send_success_callback(callback_url, file_id, category, is_recognized)
                    
            else:
                # 分类失败或未识别
                category = "unknown"
                is_recognized = 0  # 未识别
                
                logger.warning(f"File classification failed or unrecognized: {result}")
                
                # 发送失败回调 - 使用新的预定义格式
                if callback_url:
                    self._send_success_callback(callback_url, file_id, category, is_recognized)
                
        except Exception as e:
            error_msg = f"Error handling single file classification job: {e}"
            logger.error(error_msg)
            
            # 尝试发送错误回调 - 使用新的预定义格式
            try:
                data = message_data.get("data", {})
                callback_url = data.get("callback_url")
                
                if callback_url:
                    # 发送失败回调
                    category = "unknown"
                    is_recognized = 0  # 未识别
                    self._send_success_callback(callback_url, file_id, category, is_recognized)
            except:
                pass
    
    def _send_success_callback(self, callback_url: str, file_id: str, category: str, is_recognized: int):
        """发送成功回调 - 使用预定义格式"""
        try:
            # 使用新的同步回调方法
            callback_service.send_classify_file_callback_sync(callback_url, file_id, category, is_recognized)
            logger.info(f"Success callback sent to: {callback_url}")
        except Exception as e:
            logger.error(f"Failed to send success callback: {e}")
    


# 创建全局实例
simple_file_classification_consumer = SimpleFileClassificationConsumer()
