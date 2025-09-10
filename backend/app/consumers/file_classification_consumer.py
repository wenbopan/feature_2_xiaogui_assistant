#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kafka消费者服务 - 处理内容处理任务
"""

import logging
import json
import time
from typing import Dict, Any

from app.consumers.file_classification_processor import content_processor
from app.models.database import get_db, Task, FileMetadata, FileClassification
from app.services.minio_service import minio_service
from datetime import datetime

logger = logging.getLogger(__name__)

class FileClassificationConsumer:
    """文件分类Kafka消费者服务"""
    
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
            logger.debug("Creating Kafka consumer directly...")
            from kafka import KafkaConsumer
            import json
            from app.config import settings
            
            self.consumer = KafkaConsumer(
                *self.TOPICS,
                bootstrap_servers=[settings.kafka_bootstrap_servers],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda m: m.decode('utf-8') if m else None,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id="legal_docs_consumers",
                session_timeout_ms=120000,  # 2 minutes - longer than Gemini timeout
                heartbeat_interval_ms=10000,  # 10 seconds - more responsive than 30s
                max_poll_interval_ms=180000,  # 3 minutes - max time between polls
                request_timeout_ms=130000  # 2 minutes 10 seconds - must be > session_timeout_ms
            )
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
                    message = self.consumer.poll(timeout_ms=5000)  # 5 seconds - increased from 1 second
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
            
            # 处理内容 - 消费者自己处理文件获取和数据库操作
            result = self._process_file_with_db(task_id, file_id)
            
            if result and result.get("success"):
                # 更新消息状态为已完成
                self._update_message_status(task_id, file_id, "completed")
                logger.info(f"Content processing job {job_id} completed: {result}")
            else:
                # 更新消息状态为失败
                self._update_message_status(task_id, file_id, "failed")
                logger.error(f"Content processing job {job_id} failed: {result}")
                
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
    
    def _process_file_with_db(self, task_id: int, file_id: int) -> Dict[str, Any]:
        """
        处理单个文件（包含数据库操作）- 消费者自己处理文件获取和数据库操作
        
        Args:
            task_id: 任务ID
            file_id: 文件ID
            
        Returns:
            处理结果字典
        """
        try:
            db = next(get_db())
            try:
                # 获取任务信息
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    logger.error(f"Task {task_id} not found")
                    return {"success": False, "error": "Task not found"}
                
                # 获取文件元数据
                file_metadata = db.query(FileMetadata).filter(FileMetadata.id == file_id).first()
                if not file_metadata:
                    logger.error(f"File metadata {file_id} not found")
                    return {"success": False, "error": "File metadata not found"}
                
                # 获取文件内容
                file_content = minio_service.get_file_content(file_metadata.s3_key)
                if not file_content:
                    logger.error(f"Failed to get file content for {file_metadata.s3_key}")
                    return {"success": False, "error": "Failed to get file content"}
                
                # 使用处理器进行分类（不依赖数据库）
                result = content_processor.process_file_content(
                    file_content,
                    file_metadata.file_type,
                    file_metadata.original_filename,
                    task.organize_date,
                    task.project_name
                )
                
                if result["success"] and result.get("logical_filename"):
                    # 更新FileMetadata的逻辑文件名
                    file_metadata.logical_filename = result["logical_filename"]
                    
                    # 创建分类记录
                    classification = FileClassification(
                        task_id=task.id,
                        file_metadata_id=file_metadata.id,
                        category=result["category"],
                        confidence=result["confidence"],
                        final_filename=result["logical_filename"],
                        classification_method=result["classification"].get("method", "gemini"),
                        gemini_response=result["classification"].get("raw_response")
                    )
                    
                    db.add(classification)
                    db.commit()
                    
                    logger.info(f"File logically renamed: {file_metadata.original_filename} -> {result['logical_filename']}")
                    return {"success": True, "logical_filename": result["logical_filename"]}
                else:
                    # 未识别的文件
                    logger.info(f"File classified as unrecognized: {file_metadata.original_filename}")
                    return {"success": True, "category": "unrecognized"}
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing file {file_id}: {e}")
            return {"success": False, "error": str(e)}
    
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
kafka_consumer_service = FileClassificationConsumer()
