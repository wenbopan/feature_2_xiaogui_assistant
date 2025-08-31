#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段提取消费者服务 - 处理字段提取任务
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.database import get_db, ProcessingMessage
from app.models.schemas import KafkaMessage, FieldExtractionJobMessage
from app.services.kafka_service import kafka_service
from app.consumers.field_extraction_processor import field_extraction_processor

logger = logging.getLogger(__name__)

class FieldExtractionConsumer:
    """字段提取Kafka消费者服务"""
    
    def __init__(self):
        self.consumer = None
        self.running = False
        self.topic = "field.extraction"
        self.group_id = "field_extraction_consumer_group"
        logger.info(f"Field extraction consumer initialized for topic: {self.topic}")
    
    def start_consumer(self):
        """同步启动消费者"""
        try:
            logger.info("Starting field extraction consumer service...")
            
            # 创建消费者
            self.consumer = kafka_service.create_sync_consumer([self.topic])
            self.running = True
            
            # 启动消费循环
            self._consume_messages()
            
            logger.info("Field extraction consumer service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start field extraction consumer: {e}")
            raise
    
    def stop_consumer(self):
        """同步停止消费者"""
        try:
            logger.info("Stopping field extraction consumer service...")
            self.running = False
            
            # 停止消费者
            if self.consumer:
                self.consumer.close()
                self.consumer = None
            
            logger.info("Field extraction consumer service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop field extraction consumer: {e}")
    
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
                                # 解析消息 - 使用Pydantic模型验证
                                message_data = msg.value
                                topic = msg.topic
                                
                                logger.debug(f"Received message from topic {topic}: {message_data}")
                                
                                # 使用Pydantic模型验证和解析消息
                                try:
                                    # 解析为KafkaMessage
                                    kafka_message = KafkaMessage(**message_data)
                                    
                                    # 类型检查：使用消息类型字段而不是Python类型检查
                                    if kafka_message.data.type == "field_extraction_job":
                                        # 解析为FieldExtractionJobMessage - the data is directly in kafka_message.data
                                        extraction_job = FieldExtractionJobMessage(**kafka_message.data.model_dump())
                                        logger.debug(f"Parsed field extraction job: {extraction_job}")
                                        
                                        # 处理字段提取任务
                                        self._handle_field_extraction_job(extraction_job, msg)
                                    else:
                                        logger.warning(f"Unknown message type: {kafka_message.data.type}")
                                        
                                except Exception as e:
                                    logger.error(f"Failed to parse message with Pydantic: {e}")
                                    logger.error(f"Raw message data: {message_data}")
                                    continue
                                
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
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
    
    def _handle_field_extraction_job(self, extraction_job: FieldExtractionJobMessage, message):
        """处理字段提取任务"""
        try:
            logger.info(f"Processing field extraction job for file {extraction_job.file_id} in task {extraction_job.task_id}")
            
            # 更新消息状态为已消费
            self._update_message_status(extraction_job.task_id, extraction_job.file_id, "consumed")
            
            # 获取数据库会话
            db = next(get_db())
            try:
                # 处理字段提取
                result = self._process_field_extraction(extraction_job, db)
                
                if result:
                    # 更新消息状态为已完成
                    self._update_message_status(extraction_job.task_id, extraction_job.file_id, "completed")
                    logger.info(f"Field extraction job completed for file {extraction_job.file_id}: {result}")
                else:
                    # 更新消息状态为失败
                    self._update_message_status(extraction_job.task_id, extraction_job.file_id, "failed")
                    logger.error(f"Field extraction job failed for file {extraction_job.file_id}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling field extraction job: {e}")
            # 尝试更新状态为失败
            try:
                self._update_message_status(extraction_job.task_id, extraction_job.file_id, "failed")
            except:
                pass
    
    def _process_field_extraction(self, extraction_job: FieldExtractionJobMessage, db: Session):
        """执行字段提取处理"""
        try:
            logger.info(f"Processing field extraction for file {extraction_job.file_id}")
            
            # 准备数据传递给处理器
            extraction_data = {
                'file_id': extraction_job.file_id,
                's3_key': extraction_job.s3_key,
                'file_type': extraction_job.file_type,
                'filename': extraction_job.filename
            }
            
            # 调用字段提取处理器
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    field_extraction_processor.process_field_extraction(extraction_data, db)
                )
            finally:
                loop.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in field extraction processing: {e}")
            return None
    
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
                    ProcessingMessage.topic == "field.extraction"
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
                    logger.warning(f"ProcessingMessage not found for task_id: {task_id}, file_id: {file_id}, topic: field.extraction")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update message status: {e}")

# 创建全局实例
field_extraction_consumer = FieldExtractionConsumer()
