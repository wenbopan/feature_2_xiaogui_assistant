#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kafka消费者服务 - 处理内容处理任务
"""

import logging
import json
import asyncio
from typing import Dict, Any
from app.services.kafka_service import kafka_service
from app.services.content_processor import content_processor
from app.models.database import get_db

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    """Kafka消费者服务"""
    
    # 类变量：定义该服务负责的主题
    TOPICS = ["file.processing"]
    
    def __init__(self):
        self.consumer = None
        self.running = False
        self.consume_task = None
        # 限制并发处理数量，避免阻塞事件循环
        self.semaphore = asyncio.Semaphore(5)  # 最多同时处理5个文件
    
    async def start_async_consumer(self):
        """异步启动消费者"""
        try:
            logger.info("Starting Kafka consumer service...")
            logger.debug(f"Using topics: {self.TOPICS}")
            
            # 创建消费者，使用类定义的主题
            logger.debug("Creating Kafka consumer via kafka_service...")
            self.consumer = await kafka_service.create_consumer(self.TOPICS)
            logger.debug(f"Consumer created successfully: {self.consumer}")
            
            logger.debug("Setting running flag to True...")
            self.running = True
            
            # 启动消费循环作为后台任务
            logger.debug("Creating consume task...")
            self.consume_task = asyncio.create_task(self._consume_messages())
            logger.debug(f"Consume task created: {self.consume_task}")
            
            logger.info("Kafka consumer service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
    
    async def stop_async_consumer(self):
        """异步停止消费者"""
        try:
            logger.info("Stopping Kafka consumer service...")
            logger.debug("Setting running flag to False...")
            self.running = False
            
            # 取消消费任务
            if self.consume_task and not self.consume_task.done():
                logger.debug(f"Cancelling consume task: {self.consume_task}")
                self.consume_task.cancel()
                try:
                    await self.consume_task
                    logger.debug("Consume task cancelled successfully")
                except asyncio.CancelledError:
                    logger.debug("Consume task cancellation completed")
                    pass
            else:
                logger.debug("No active consume task to cancel")
            
            # 停止消费者
            if self.consumer:
                logger.debug("Stopping Kafka consumer...")
                await self.consumer.stop()
                self.consumer = None
                logger.debug("Kafka consumer stopped successfully")
            else:
                logger.debug("No consumer to stop")
            
            logger.info("Kafka consumer service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop Kafka consumer: {e}")
    
    async def _consume_messages(self):
        """异步消费消息的主循环"""
        try:
            while self.running:
                try:
                    # 异步消费消息
                    async for message in self.consumer:
                        if not self.running:
                            break
                        
                        try:
                            # 解析消息 - 消息已经由deserializer解析
                            message_data = message.value
                            topic = message.topic
                            
                            logger.info(f"Received message from topic {topic}: {message_data}")
                            logger.debug(f"Message key: {message.key}")
                            logger.debug(f"Message offset: {message.offset}")
                            logger.debug(f"Message partition: {message.partition}")
                            logger.debug(f"Message timestamp: {message.timestamp}")
                            
                            # 处理文件处理任务
                            if topic == "file.processing":
                                logger.debug(f"Processing file.processing message...")
                                # 使用信号量控制并发数量
                                asyncio.create_task(self._handle_processing_job_with_semaphore(message_data, message))
                                logger.debug(f"File.processing message queued for processing")
                            else:
                                logger.warning(f"Unknown topic: {topic}")
                                logger.debug(f"Skipping unknown topic message")
                        
                        except Exception as e:
                            logger.error(f"Failed to process message: {e}")
                            continue
                
                except Exception as e:
                    if self.running:  # 只在服务运行时记录错误
                        logger.error(f"Error in message consumption loop: {e}")
                        await asyncio.sleep(1)  # 短暂休息后重试
                
        except Exception as e:
            logger.error(f"Consumer loop terminated: {e}")
        finally:
            if self.consumer:
                await self.consumer.stop()
    
    async def _handle_processing_job_with_semaphore(self, message_data: Dict[str, Any], raw_message=None):
        """使用信号量控制并发的处理任务"""
        async with self.semaphore:
            await self._handle_processing_job(message_data, raw_message)
    
    async def _handle_processing_job(self, message_data: Dict[str, Any], raw_message=None):
        """处理内容处理任务"""
        try:
            logger.debug(f"=== Starting to handle processing job ===")
            logger.debug(f"Raw message_data: {message_data}")
            
            # 从data字段中获取实际的任务信息
            data = message_data.get("data", {})
            task_id = data.get("task_id")
            job_id = data.get("job_id")
            file_id = data.get("file_id")
            
            logger.debug(f"Extracted data - task_id: {task_id}, job_id: {job_id}, file_id: {file_id}")
            
            if not task_id or not job_id or not file_id:
                logger.error("Invalid processing job message: missing task_id, job_id or file_id")
                logger.error(f"Message data: {message_data}")
                return
            
            logger.info(f"Processing content job {job_id} for file {file_id} in task {task_id}")
            logger.debug(f"Job details - task_id: {task_id}, job_id: {job_id}, file_id: {file_id}")
            
            # 获取数据库会话
            logger.debug("Getting database session...")
            db = next(get_db())
            logger.debug("Database session acquired successfully")
            
            try:
                # 1. 标记消息已被消费
                try:
                    from app.services.processing_message_updater import ProcessingMessageUpdater
                    
                    # 获取Kafka元信息
                    partition = getattr(raw_message, "partition", None) if raw_message else None
                    offset = getattr(raw_message, "offset", None) if raw_message else None
                    
                    # 标记为consumed状态
                    if not ProcessingMessageUpdater.mark_consumed(db, job_id, partition, offset):
                        logger.warning(f"Failed to mark job {job_id} as consumed")
                    
                    # 标记为processing状态
                    if not ProcessingMessageUpdater.mark_processing(db, job_id, attempts=1):
                        logger.warning(f"Failed to mark job {job_id} as processing")
                        
                except Exception as meta_err:
                    logger.warning(f"Failed to update processing message metadata: {meta_err}")

                # 处理内容任务
                logger.debug(f"Calling content_processor.process_content_job...")
                result = await content_processor.process_content_job(message_data, db)
                logger.info(f"Content processing job {job_id} completed: {result}")
                logger.debug(f"Processing result details: {result}")

                # 2. 标记处理完成或失败
                try:
                    from app.services.processing_message_updater import ProcessingMessageUpdater
                    
                    if result.get("status") == "completed":
                        # 标记为completed状态
                        if not ProcessingMessageUpdater.mark_completed(db, job_id):
                            logger.warning(f"Failed to mark job {job_id} as completed")
                    else:
                        # 标记为failed状态
                        error_msg = str(result.get("error", "Unknown error"))
                        if not ProcessingMessageUpdater.mark_failed(db, job_id, error_msg):
                            logger.warning(f"Failed to mark job {job_id} as failed")
                            
                except Exception as meta_err:
                    logger.warning(f"Failed to finalize processing message metadata: {meta_err}")
                
            finally:
                logger.debug("Closing database session...")
                db.close()
                logger.debug("Database session closed")
                
        except Exception as e:
            logger.error(f"Failed to handle processing job: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            logger.error(f"Message data that caused error: {message_data}")
            
            # 处理失败时，记录消息失败信息
            try:
                logger.debug("Attempting to mark file as failed in database...")
                task_id = message_data.get("data", {}).get("task_id")
                file_id = message_data.get("data", {}).get("file_id")
                
                logger.debug(f"Extracted task_id: {task_id}, file_id: {file_id} for error handling")
                
                logger.debug(f"Getting database session for error handling...")
                db = next(get_db())
                try:
                    from datetime import datetime
                    from app.models.database import ProcessingMessage
                    pm = db.query(ProcessingMessage).filter(ProcessingMessage.job_id == message_data.get("data", {}).get("job_id")).first()
                    if pm is not None:
                        pm.status = "failed"
                        pm.error = str(e)
                        pm.completed_at = datetime.now()
                        db.commit()
                        logger.info("Updated processing message status to failed")
                finally:
                    logger.debug("Closing database session for error handling...")
                    db.close()
                    logger.debug("Database session closed for error handling")
            except Exception as db_error:
                logger.error(f"Failed to mark file as failed in database: {db_error}")
                logger.error(f"Database error type: {type(db_error).__name__}")
                logger.error(f"Database error details: {str(db_error)}")
    


# 全局Kafka消费者服务实例
kafka_consumer_service = KafkaConsumerService()
