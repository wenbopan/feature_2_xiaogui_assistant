#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kafka消费者服务 - 处理内容处理任务
"""

import logging
import json
import time
from typing import Dict, Any
from app.services.kafka_service import kafka_service
from app.services.content_processor import content_processor
from app.models.database import get_db
from datetime import datetime

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    """Kafka消费者服务"""
    
    # 类变量：定义该服务负责的主题
    TOPICS = ["file.processing"]
    
    def __init__(self):
        self.consumer = None
        self.running = False
    
    def start_consumer(self):
        """同步启动消费者"""
        try:
            logger.info("Starting Kafka consumer service...")
            logger.debug(f"Using topics: {self.TOPICS}")
            
            # 创建消费者，使用类定义的主题
            logger.debug("Creating Kafka consumer via kafka_service...")
            self.consumer = kafka_service.create_sync_consumer(self.TOPICS)
            logger.debug(f"Consumer created successfully: {self.consumer}")
            
            logger.debug("Setting running flag to True...")
            self.running = True
            
            # 启动消费循环
            logger.debug("Starting consume loop...")
            self._consume_messages()
            
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
    
    def stop_consumer(self):
        """同步停止消费者"""
        try:
            logger.info("Stopping Kafka consumer service...")
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
            
            logger.info("Kafka consumer service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop Kafka consumer: {e}")
    
    def _consume_messages(self):
        """同步消费消息的主循环"""
        try:
            while self.running:
                try:
                    # 同步消费消息 - kafka-python poll() doesn't have timeout parameter
                    message = self.consumer.poll(timeout_ms=1000)
                    if not message:
                        continue
                    
                    # Handle multiple messages from poll result
                    for tp, messages in message.items():
                        for msg in messages:
                            if not self.running:
                                break
                            
                            try:
                                # 解析消息 - 消息已经由deserializer解析
                                message_data = msg.value
                                topic = msg.topic
                                
                                logger.debug(f"Received message from topic {topic}: {message_data}")
                                
                                # 处理消息
                                self._handle_processing_job(message_data, msg)
                                
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
    
    def _handle_processing_job(self, message_data: Dict[str, Any], message):
        """处理内容处理任务"""
        try:
            # 获取任务信息 - 支持嵌套的data结构
            if "data" in message_data:
                # 消息格式: {"id": "...", "timestamp": ..., "data": {"task_id": ..., "job_id": ..., "file_id": ...}}
                data = message_data["data"]
                task_id = data.get("task_id")
                job_id = data.get("job_id")
                file_id = data.get("file_id")
            else:
                # 直接格式: {"task_id": ..., "job_id": ..., "file_id": ...}
                task_id = message_data.get("task_id")
                job_id = message_data.get("job_id")
                file_id = message_data.get("file_id")
            
            if not all([task_id, job_id, file_id]):
                logger.error(f"Missing required fields in message: {message_data}")
                return
            
            logger.info(f"Processing content job {job_id} for file {file_id} in task {task_id}")
            
            # 更新消息状态为已消费
            self._update_message_status(task_id, file_id, "consumed")
            
            # 处理内容 - 调用异步方法
            import asyncio
            try:
                # Create event loop for async call
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    content_processor.process_file(task_id, file_id)
                )
            finally:
                loop.close()
            
            if result:
                # 更新消息状态为已完成
                self._update_message_status(task_id, file_id, "completed")
                logger.info(f"Content processing job {job_id} completed: {result}")
            else:
                # 更新消息状态为失败
                self._update_message_status(task_id, file_id, "failed")
                logger.error(f"Content processing job {job_id} failed")
                
        except Exception as e:
            logger.error(f"Error handling processing job: {e}")
            # 尝试更新状态为失败
            try:
                if "data" in message_data:
                    data = message_data["data"]
                    task_id = data.get("task_id")
                    file_id = data.get("file_id")
                else:
                    task_id = message_data.get("task_id")
                    file_id = message_data.get("file_id")
                    
                if task_id and file_id:
                    self._update_message_status(task_id, file_id, "failed")
            except:
                pass
    
    def _update_message_status(self, task_id: int, file_id: int, status: str):
        """更新处理消息状态"""
        try:
            from app.models.database import ProcessingMessage
            
            db = next(get_db())
            try:
                # Find the ProcessingMessage record by task_id, file_metadata_id, and topic
                processing_msg = db.query(ProcessingMessage).filter(
                    ProcessingMessage.task_id == task_id,
                    ProcessingMessage.file_metadata_id == file_id,
                    ProcessingMessage.topic == "file.processing"
                ).first()
                
                if processing_msg:
                    # Update the status directly
                    processing_msg.status = status
                    processing_msg.updated_at = datetime.now()
                    
                    if status == "consumed":
                        processing_msg.consumed_at = datetime.now()
                    elif status == "completed":
                        processing_msg.completed_at = datetime.now()
                    elif status == "failed":
                        processing_msg.completed_at = datetime.now()
                    
                    db.commit()
                    logger.info(f"Message {task_id}:{file_id} marked as {status}")
                else:
                    logger.warning(f"ProcessingMessage not found for task_id: {task_id}, file_id: {file_id}, topic: file.processing")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update message status: {e}")

# 创建全局实例
kafka_consumer_service = KafkaConsumerService()
