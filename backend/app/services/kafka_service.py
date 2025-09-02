import asyncio
from app.config import settings
import logging
import json
from typing import Dict, Any, Optional, List
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError
import uuid
from app.models.schemas import KafkaMessage, KafkaMessageMetadata, FieldExtractionJobMessage, ContentExtractionJobMessage

logger = logging.getLogger(__name__)

class KafkaService:
    """Kafka服务类 - 使用真正的Kafka集群"""
    
    def __init__(self):
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.topic_prefix = settings.kafka_topic_prefix
        self.is_connected = False
        self.producer = None
        self.consumers = {}
        
        logger.info(f"Kafka service initialized - Bootstrap servers: {self.bootstrap_servers}")
    
    async def connect(self) -> bool:
        """连接到Kafka集群"""
        try:
            # 创建生产者
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda x: json.dumps(x).encode()
            )
            await self.producer.start()
            
            self.is_connected = True
            logger.info(f"Kafka service connected to {self.bootstrap_servers}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False
    
    def create_sync_consumer(self, topics: List[str]):
        """创建同步消费者（用于线程中）"""
        try:
            from kafka import KafkaConsumer
            import json
            
            # 创建同步Kafka消费者
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda m: m.decode('utf-8') if m else None,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id="legal_docs_consumers"  # Fixed consumer group name
            )
            
            logger.info(f"Created sync consumer for topics: {topics}")
            return consumer
            
        except Exception as e:
            logger.error(f"Failed to create sync consumer: {e}")
            raise
    
    async def disconnect(self):
        """断开Kafka连接"""
        try:
            if self.producer:
                await self.producer.stop()
            
            # 停止所有消费者
            for consumer in self.consumers.values():
                if consumer and hasattr(consumer, 'stop'):
                    await consumer.stop()
            
            self.is_connected = False
            logger.info("Kafka service disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from Kafka: {e}")
    
    def publish_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """发布消息到指定主题"""
        try:
            if not self.is_connected or not self.producer:
                logger.error("Kafka producer not connected")
                return False
            
            # 使用Pydantic模型验证消息结构
            if topic == "field.extraction":
                # 验证字段提取消息
                field_extraction_message = FieldExtractionJobMessage(**message)
                
                # 创建标准化的Kafka消息
                kafka_message = KafkaMessage(
                    metadata=KafkaMessageMetadata(
                        id=str(uuid.uuid4()),
                        timestamp=asyncio.get_event_loop().time(),
                        key=key,
                        source="field_extraction_service"
                    ),
                    data=field_extraction_message
                )
                
                # 序列化消息
                message_with_metadata = kafka_message.model_dump()
                
            elif topic == "content.extraction":
                # 验证内容提取消息
                content_extraction_message = ContentExtractionJobMessage(**message)
                
                # 创建标准化的Kafka消息
                kafka_message = KafkaMessage(
                    metadata=KafkaMessageMetadata(
                        id=str(uuid.uuid4()),
                        timestamp=asyncio.get_event_loop().time(),
                        key=key,
                        source="content_extraction_service"
                    ),
                    data=content_extraction_message
                )
                
                # 序列化消息
                message_with_metadata = kafka_message.model_dump()
                
            else:
                # 其他主题的消息保持原有结构
                message_with_metadata = {
                    "id": str(uuid.uuid4()),
                    "timestamp": asyncio.get_event_loop().time(),
                    "key": key,
                    "data": message
                }
            
            # 异步发送消息，不等待完成
            asyncio.create_task(self._send_message(topic, message_with_metadata, key))
            
            logger.info(f"Message queued for {topic}: {message.get('type', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message to {topic}: {e}")
            return False
    
    async def _send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None):
        """内部异步发送消息方法"""
        await self.producer.send_and_wait(
            topic, 
            value=message, 
            key=key.encode() if key else None
        )
    
    async def create_consumer(self, topics: List[str]) -> AIOKafkaConsumer:
        """创建Kafka消费者"""
        try:
            consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id="legal_consumer_group",  # 使用固定的消费者组ID
                value_deserializer=lambda x: json.loads(x.decode()),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            await consumer.start()
            
            consumer_id = str(uuid.uuid4())
            self.consumers[consumer_id] = consumer
            
            logger.info(f"Created Kafka consumer for topics: {topics}")
            return consumer
            
        except Exception as e:
            logger.error(f"Failed to create consumer for topics {topics}: {e}")
            raise
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态信息"""
        return {
            'connected': self.is_connected,
            'bootstrap_servers': self.bootstrap_servers,
            'active_consumers': len(self.consumers),
            'producer_connected': self.producer is not None
        }

# 全局Kafka服务实例
kafka_service = KafkaService()
