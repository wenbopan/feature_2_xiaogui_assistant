#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理消息状态更新器
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.database import ProcessingMessage

logger = logging.getLogger(__name__)

class ProcessingMessageUpdater:
    """ProcessingMessage状态更新工具类"""
    
    @staticmethod
    def update_status(
        db: Session,
        job_id: str,
        new_status: str,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
        partition: Optional[int] = None,
        offset: Optional[int] = None,
        **kwargs
    ) -> bool:
        """
        更新ProcessingMessage的状态
        
        Args:
            db: 数据库会话
            job_id: 任务ID
            new_status: 新状态 (created, consumed, processing, completed, failed)
            error: 错误信息（仅在failed状态时需要）
            attempts: 尝试次数
            partition: Kafka分区
            offset: Kafka偏移量
            **kwargs: 其他需要更新的字段
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 查询ProcessingMessage记录
            processing_msg = db.query(ProcessingMessage).filter(
                ProcessingMessage.job_id == job_id
            ).first()
            
            if not processing_msg:
                logger.warning(f"ProcessingMessage not found for job_id: {job_id}")
                return False
            
            # 更新状态
            processing_msg.status = new_status
            processing_msg.updated_at = datetime.now()
            
            # 根据状态设置相应的时间字段
            if new_status == "consumed":
                processing_msg.consumed_at = datetime.now()
            elif new_status == "processing":
                if not processing_msg.consumed_at:
                    processing_msg.consumed_at = datetime.now()
            elif new_status == "completed":
                processing_msg.completed_at = datetime.now()
            elif new_status == "failed":
                if error:
                    processing_msg.error = error
                if attempts:
                    processing_msg.attempts = attempts
                else:
                    processing_msg.attempts = (processing_msg.attempts or 0) + 1
            
            # 更新Kafka元信息
            if partition is not None:
                processing_msg.partition = partition
            if offset is not None:
                processing_msg.offset = offset
            
            # 更新其他字段
            for key, value in kwargs.items():
                if hasattr(processing_msg, key):
                    setattr(processing_msg, key, value)
            
            # 提交更改
            db.commit()
            
            logger.debug(f"Successfully updated ProcessingMessage {job_id} status to {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update ProcessingMessage {job_id} status to {new_status}: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def mark_consumed(
        db: Session,
        job_id: str,
        partition: Optional[int] = None,
        offset: Optional[int] = None
    ) -> bool:
        """标记消息已被消费"""
        return ProcessingMessageUpdater.update_status(
            db=db,
            job_id=job_id,
            new_status="consumed",
            partition=partition,
            offset=offset
        )
    
    @staticmethod
    def mark_processing(
        db: Session,
        job_id: str,
        attempts: Optional[int] = None
    ) -> bool:
        """标记消息正在处理中"""
        return ProcessingMessageUpdater.update_status(
            db=db,
            job_id=job_id,
            new_status="processing",
            attempts=attempts
        )
    
    @staticmethod
    def mark_completed(
        db: Session,
        job_id: str
    ) -> bool:
        """标记消息处理完成"""
        return ProcessingMessageUpdater.update_status(
            db=db,
            job_id=job_id,
            new_status="completed"
        )
    
    @staticmethod
    def mark_failed(
        db: Session,
        job_id: str,
        error: str,
        attempts: Optional[int] = None
    ) -> bool:
        """标记消息处理失败"""
        return ProcessingMessageUpdater.update_status(
            db=db,
            job_id=job_id,
            new_status="failed",
            error=error,
            attempts=attempts
        )
