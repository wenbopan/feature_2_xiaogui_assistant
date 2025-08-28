import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.database import get_db, ProcessingMessage, FieldExtraction
from app.models.schemas import KafkaMessage, FieldExtractionJobMessage
from app.services.minio_service import minio_service
from app.services.gemini_service import gemini_service
from app.services.kafka_service import kafka_service

logger = logging.getLogger(__name__)

class FieldExtractionConsumer:
    """字段提取Kafka消费者服务"""
    
    def __init__(self):
        self.consumer = None
        self.running = False
        self.consume_task = None
        self.topic = "field.extraction"
        self.group_id = "field_extraction_consumer_group"
        # 限制并发处理数量，避免阻塞事件循环
        self.semaphore = asyncio.Semaphore(5)  # 最多同时处理5个文件
        logger.info(f"Field extraction consumer initialized for topic: {self.topic}")
    
    async def start_async_consumer(self):
        """异步启动消费者"""
        try:
            logger.info("Starting field extraction consumer service...")
            
            # 创建消费者
            self.consumer = await kafka_service.create_consumer([self.topic])
            self.running = True
            
            # 启动消费循环作为后台任务
            self.consume_task = asyncio.create_task(self._consume_messages())
            
            logger.info("Field extraction consumer service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start field extraction consumer: {e}")
            raise
    
    async def stop_async_consumer(self):
        """异步停止消费者"""
        try:
            logger.info("Stopping field extraction consumer service...")
            self.running = False
            
            # 取消消费任务
            if self.consume_task and not self.consume_task.done():
                self.consume_task.cancel()
                try:
                    await self.consume_task
                except asyncio.CancelledError:
                    pass
            
            # 停止消费者
            if self.consumer:
                await self.consumer.stop()
                self.consumer = None
            
            logger.info("Field extraction consumer service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop field extraction consumer: {e}")
    
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
                            # 解析消息 - 使用Pydantic模型验证
                            message_data = message.value
                            topic = message.topic
                            
                            logger.debug(f"Received message from topic {topic}: {message_data}")
                            
                            # 使用Pydantic模型验证和解析消息
                            try:
                                # 解析为KafkaMessage
                                kafka_message = KafkaMessage(**message_data)
                                
                                # 类型检查：使用消息类型字段而不是Python类型检查
                                if kafka_message.data.type == "field_extraction_job":
                                    logger.debug(f"Message validated successfully: {kafka_message.data}")
                                    
                                    # 使用信号量控制并发数量，避免阻塞事件循环
                                    asyncio.create_task(self._handle_message_with_semaphore(kafka_message.data, message))
                                    logger.debug(f"Field extraction message queued for processing")
                                else:
                                    logger.warning(f"Unexpected message type: {kafka_message.data.type}, expected field_extraction_job")
                                    continue
                                
                            except Exception as validation_error:
                                logger.error(f"Message validation failed: {validation_error}")
                                # 记录无效消息，但继续处理下一条
                                continue
                            
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            continue
                            
                except Exception as e:
                    if self.running:
                        logger.error(f"Error in consume loop: {e}")
                        await asyncio.sleep(1)  # 短暂等待后重试
                        
        except Exception as e:
            logger.error(f"Fatal error in consume loop: {e}")
    
    async def _handle_message_with_semaphore(self, message_data: FieldExtractionJobMessage, raw_message: Any) -> None:
        """使用信号量控制并发的消息处理"""
        async with self.semaphore:
            await self._handle_message(message_data, raw_message)
    
    async def _handle_message(self, message_data: FieldExtractionJobMessage, raw_message: Any) -> None:
        """处理字段提取消息"""
        try:
            # 使用Pydantic模型，字段已经验证过
            job_id = message_data.job_id
            task_id = message_data.task_id
            file_id = message_data.file_id
            
            logger.info(f"Processing field extraction job: {job_id} for file: {file_id}")
            
            # 获取数据库会话
            db = next(get_db())
            try:
                # 1. 标记消息已被消费
                from app.services.processing_message_updater import ProcessingMessageUpdater
                
                if not ProcessingMessageUpdater.mark_consumed(db, job_id):
                    logger.warning(f"Failed to mark job {job_id} as consumed")
                
                # 2. 标记消息正在处理中
                if not ProcessingMessageUpdater.mark_processing(db, job_id):
                    logger.warning(f"Failed to mark job {job_id} as processing")
                
                # 3. 处理字段提取
                result = await self._handle_field_extraction_job(message_data, db)
                
                # 4. 标记处理完成
                if not ProcessingMessageUpdater.mark_completed(db, job_id):
                    logger.warning(f"Failed to mark job {job_id} as completed")
                
                logger.info(f"Field extraction job {job_id} completed successfully")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to process field extraction message: {e}")
            # 记录ProcessingMessage状态为failed
            try:
                from app.services.processing_message_updater import ProcessingMessageUpdater
                
                db = next(get_db())
                if not ProcessingMessageUpdater.mark_failed(db, message_data.job_id, str(e), attempts=1):
                    logger.warning(f"Failed to mark job {message_data.job_id} as failed")
                db.close()
            except Exception as db_error:
                logger.error(f"Failed to record error in ProcessingMessage: {db_error}")
    
    async def _handle_field_extraction_job(self, message_data: FieldExtractionJobMessage, db: Session) -> Dict[str, Any]:
        """处理单个字段提取任务"""
        try:
            file_id = message_data.file_id
            s3_key = message_data.s3_key
            file_type = message_data.file_type
            filename = message_data.filename
            
            # 获取文件内容
            file_content = minio_service.get_file_content(s3_key)
            if not file_content:
                raise Exception(f"Failed to get file content from MinIO: {s3_key}")
            
            # 调用Gemini API提取字段（同时进行分类）- 确保是异步调用
            extraction_result = await gemini_service.extract_fields(
                file_content=file_content,
                file_type=file_type,
                filename=filename
            )
            
            # 直接创建FieldExtraction记录，关联到原文件
            field_extraction = FieldExtraction(
                file_metadata_id=file_id,  # 直接关联到原文件
                field_category=extraction_result.get("category", "未识别"),  # 字段提取的分类
                extraction_data=extraction_result.get("extraction_data", {}),
                missing_fields=extraction_result.get("missing_fields", []),
                extraction_method="gemini",
                confidence=extraction_result.get("extraction_confidence", 0.0)
            )
            
            db.add(field_extraction)
            
            # 同时更新file_metadata表的extracted_fields列（生产环境使用）
            from app.models.database import FileMetadata
            
            file_metadata = db.query(FileMetadata).filter(FileMetadata.id == file_id).first()
            if file_metadata:
                file_metadata.extracted_fields = extraction_result.get("extraction_data", {})
                logger.info(f"Updated file_metadata.extracted_fields for file {file_id}")
            else:
                logger.warning(f"FileMetadata not found for file_id: {file_id}")
            
            db.commit()
            
            logger.info(f"Field extraction completed for file {filename}, category: {extraction_result.get('category', 'unknown')}")
            
            return {
                "success": True,
                "category": extraction_result.get("category", "未识别"),
                "classification_confidence": extraction_result.get("classification_confidence", 0.0),
                "extraction_data": extraction_result.get("extraction_data", {}),
                "missing_fields": extraction_result.get("missing_fields", []),
                "extraction_confidence": extraction_result.get("extraction_confidence", 0.0)
            }
            
        except Exception as e:
            logger.error(f"Field extraction failed for file {message_data.filename}: {e}")
            raise e

# 全局字段提取消费者实例
field_extraction_consumer = FieldExtractionConsumer()
