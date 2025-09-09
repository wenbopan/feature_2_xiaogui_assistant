from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
import uvicorn
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager

from app.config import settings, ensure_directories, instructions_manager
from app.models.database import create_tables
from app.api import common_api, batch_api, single_file_api
from app.services.kafka_service import kafka_service
from app.consumers import kafka_consumer_service, field_extraction_consumer, simple_file_classification_consumer, simple_field_extraction_consumer
from app.services.minio_service import minio_service

# 确保logs目录存在
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 控制台输出
        RotatingFileHandler(  # 文件输出，支持轮转
            logs_dir / "app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,  # 保留5个备份文件
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)

# Global thread references for cleanup
content_consumer_thread = None
field_extraction_thread = None
simple_classification_thread = None
simple_extraction_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global content_consumer_thread, field_extraction_thread, simple_classification_thread, simple_extraction_thread
    
    # 启动时
    logger.info("Starting Legal Docs MVP application...")
    
    # 确保目录存在
    ensure_directories()
    
    # 创建数据库表
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise
    
    # 初始化指令配置到内存
    try:
        logger.info("Initializing instructions configuration...")
        instructions_manager.initialize_config()
        
        # 验证初始化成功
        if not instructions_manager.is_initialized():
            raise RuntimeError("Instructions config initialization failed")
            
        memory_instructions = instructions_manager.get_memory_instructions()
        logger.info(f"Instructions loaded into memory successfully")
        logger.info(f"Loaded instruction categories: {list(memory_instructions.keys())}")
        logger.info("All required instruction categories are loaded and validated")
            
    except Exception as e:
        logger.error(f"Failed to initialize instructions in memory: {e}")
        logger.error("Instructions are critical for document processing. Application cannot start without them.")
        raise
    
    # 验证API密钥配置（强依赖）
    try:
        logger.info("Validating API key configuration...")
        
        # 检查Gemini API Key
        if not settings.gemini_api_key or settings.gemini_api_key.strip() == "":
            raise ValueError("GEMINI_API_KEY is not set or empty")
        
        # 检查Qwen API Key
        if not settings.qwen_api_key or settings.qwen_api_key.strip() == "":
            raise ValueError("QWEN_API_KEY is not set or empty")
        
        logger.info("API key configuration validation passed")
        logger.info(f"Using LLM model: {settings.llm_default_model}")
        logger.info(f"Gemini model: {settings.gemini_model}")
        logger.info(f"Qwen model: {settings.qwen_model}")
            
    except Exception as e:
        logger.error(f"API key validation failed: {e}")
        logger.error("API keys are critical for AI processing. Application cannot start without valid API keys.")
        logger.error("Please set GEMINI_API_KEY and QWEN_API_KEY environment variables.")
        raise
    
    # 启动Kafka服务（强依赖）
    try:
        await kafka_service.connect()
        logger.info("Kafka service connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka service: {e}")
        logger.error("Kafka is a critical dependency. Application cannot start without it.")
        raise
    
    # 启动Kafka消费者服务在单独线程中（强依赖）
    try:
        logger.info("Starting content processing consumer in separate thread...")
        content_consumer_thread = threading.Thread(
            target=kafka_consumer_service.start_consumer,
            name="ContentConsumerThread",
            daemon=True
        )
        content_consumer_thread.start()
        logger.info("Content processing consumer thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start content processing consumer thread: {e}")
        logger.error("Content processing consumer is a critical dependency. Application cannot start without it.")
        raise
    
    # 启动字段提取消费者服务在单独线程中（强依赖）
    try:
        logger.info("Starting field extraction consumer in separate thread...")
        field_extraction_thread = threading.Thread(
            target=field_extraction_consumer.start_consumer,
            name="FieldExtractionThread",
            daemon=True
        )
        field_extraction_thread.start()
        logger.info("Field extraction consumer thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start field extraction consumer thread: {e}")
        logger.error("Field extraction consumer is a critical dependency. Application cannot start without it.")
        raise
    
    # 启动简单文件分类消费者服务在单独线程中（强依赖）
    try:
        logger.info("Starting simple file classification consumer in separate thread...")
        simple_classification_thread = threading.Thread(
            target=simple_file_classification_consumer.start_consumer,
            name="SimpleClassificationThread",
            daemon=True
        )
        simple_classification_thread.start()
        logger.info("Simple file classification consumer thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start simple file classification consumer thread: {e}")
        logger.error("Simple file classification consumer is a critical dependency. Application cannot start without it.")
        raise
    
    # 启动简单字段提取消费者服务在单独线程中（强依赖）
    try:
        logger.info("Starting simple field extraction consumer in separate thread...")
        simple_extraction_thread = threading.Thread(
            target=simple_field_extraction_consumer.start_consumer,
            name="SimpleExtractionThread",
            daemon=True
        )
        simple_extraction_thread.start()
        logger.info("Simple field extraction consumer thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start simple field extraction consumer thread: {e}")
        logger.error("Simple field extraction consumer is a critical dependency. Application cannot start without it.")
        raise
    
    # 启动MinIO服务（强依赖）
    try:
        success = await minio_service.connect()
        if success:
            logger.info("MinIO service connected successfully")
        else:
            logger.error("MinIO service connection failed")
            logger.error("MinIO is a critical dependency. Application cannot start without it.")
            raise Exception("MinIO connection failed")
    except Exception as e:
        logger.error(f"Failed to connect to MinIO service: {e}")
        logger.error("MinIO is a critical dependency. Application cannot start without it.")
        raise
    
    # 记录启动完成信息
    memory_instructions = instructions_manager.get_memory_instructions()
    logger.info("Application startup completed")
    logger.info(f"Instructions ready: {len(memory_instructions)} categories loaded")
    logger.info(f"Available instruction categories: {', '.join(memory_instructions.keys())}")
    
    yield
    
    # 关闭时
    logger.info("Shutting down Legal Docs MVP application...")
    
    # 停止简单字段提取消费者线程
    try:
        if simple_extraction_thread and simple_extraction_thread.is_alive():
            simple_field_extraction_consumer.stop_consumer()
            simple_extraction_thread.join(timeout=5.0)
            logger.info("Simple field extraction consumer thread stopped")
    except Exception as e:
        logger.error(f"Error stopping simple field extraction consumer thread: {e}")
    
    # 停止简单文件分类消费者线程
    try:
        if simple_classification_thread and simple_classification_thread.is_alive():
            simple_file_classification_consumer.stop_consumer()
            simple_classification_thread.join(timeout=5.0)
            logger.info("Simple file classification consumer thread stopped")
    except Exception as e:
        logger.error(f"Error stopping simple file classification consumer thread: {e}")
    
    # 停止字段提取消费者线程
    try:
        if field_extraction_thread and field_extraction_thread.is_alive():
            field_extraction_consumer.stop_consumer()
            field_extraction_thread.join(timeout=5.0)
            logger.info("Field extraction consumer thread stopped")
    except Exception as e:
        logger.error(f"Error stopping field extraction consumer thread: {e}")
    
    # 停止内容处理消费者线程
    try:
        if content_consumer_thread and content_consumer_thread.is_alive():
            kafka_consumer_service.stop_consumer()
            content_consumer_thread.join(timeout=5.0)
            logger.info("Content processing consumer thread stopped")
    except Exception as e:
        logger.error(f"Error stopping content processing consumer thread: {e}")
    
    # 断开Kafka连接
    try:
        await kafka_service.disconnect()
        logger.info("Kafka service disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting Kafka service: {e}")
    
    # 断开MinIO连接
    try:
        minio_service.disconnect()
        logger.info("MinIO service disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting MinIO service: {e}")
    
    logger.info("Application shutdown completed")

# 创建FastAPI应用
app = FastAPI(
    title="Legal Docs MVP API",
    description="法律文档智能整理与字段提取系统",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(common_api.router, prefix="/api")
app.include_router(batch_api.router, prefix="/api")
app.include_router(single_file_api.router, prefix="/api")

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception handler: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": "2025-02-18T00:00:00Z"
        }
    )

# 简单健康检查接口
@app.get("/health")
async def health_check():
    """简单健康检查接口"""
    from datetime import datetime
    
    # 检查指令配置状态
    try:
        if instructions_manager.is_initialized():
            memory_instructions = instructions_manager.get_memory_instructions()
            instructions_status = {
                "initialized": True,
                "categories_count": len(memory_instructions),
                "categories": list(memory_instructions.keys())
            }
        else:
            instructions_status = {
                "initialized": False,
                "error": "Instructions config not initialized"
            }
    except Exception as e:
        instructions_status = {
            "initialized": False,
            "error": str(e)
        }
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "instructions": instructions_status
    }

# Readiness检查接口
@app.get("/ready")
async def readiness_check():
    """Readiness检查 - 检查所有依赖服务是否就绪"""
    from datetime import datetime
    import time
    from app.models.database import engine
    from app.services.minio_service import minio_service
    
    start_time = time.time()
    checks = {}
    all_ready = True
    
    # 检查数据库连接
    try:
        # 测试数据库连接
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "ready",
            "message": "Database connection successful"
        }
    except Exception as e:
        checks["database"] = {
            "status": "not_ready",
            "message": f"Database connection failed: {str(e)}"
        }
        all_ready = False
    
    # 检查Kafka连接
    try:
        kafka_status = kafka_service.get_connection_status()
        if kafka_status["connected"] and kafka_status["producer_connected"]:
            checks["kafka"] = {
                "status": "ready",
                "message": "Kafka producer connected",
                "details": kafka_status
            }
        else:
            checks["kafka"] = {
                "status": "not_ready",
                "message": "Kafka not fully connected",
                "details": kafka_status
            }
            all_ready = False
    except Exception as e:
        checks["kafka"] = {
            "status": "not_ready",
            "message": f"Kafka check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查Kafka Consumer
    try:
        consumer_status = kafka_consumer_service.running and kafka_consumer_service.consumer is not None
        if consumer_status:
            checks["kafka_consumer"] = {
                "status": "ready",
                "message": "Kafka consumer running"
            }
        else:
            checks["kafka_consumer"] = {
                "status": "not_ready",
                "message": "Kafka consumer not running"
            }
            all_ready = False
    except Exception as e:
        checks["kafka_consumer"] = {
            "status": "not_ready",
            "message": f"Kafka consumer check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查简单文件分类消费者
    try:
        simple_classification_status = (
            simple_classification_thread and 
            simple_classification_thread.is_alive() and 
            simple_file_classification_consumer.running
        )
        if simple_classification_status:
            checks["simple_classification_consumer"] = {
                "status": "ready",
                "message": "Simple file classification consumer running"
            }
        else:
            checks["simple_classification_consumer"] = {
                "status": "not_ready",
                "message": "Simple file classification consumer not running"
            }
            all_ready = False
    except Exception as e:
        checks["simple_classification_consumer"] = {
            "status": "not_ready",
            "message": f"Simple file classification consumer check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查简单字段提取消费者
    try:
        simple_extraction_status = (
            simple_extraction_thread and 
            simple_extraction_thread.is_alive() and 
            simple_field_extraction_consumer.running
        )
        if simple_extraction_status:
            checks["simple_extraction_consumer"] = {
                "status": "ready",
                "message": "Simple field extraction consumer running"
            }
        else:
            checks["simple_extraction_consumer"] = {
                "status": "not_ready",
                "message": "Simple field extraction consumer not running"
            }
            all_ready = False
    except Exception as e:
        checks["simple_extraction_consumer"] = {
            "status": "not_ready",
            "message": f"Simple field extraction consumer check failed: {str(e)}"
        }
        all_ready = False
    
    # 检查MinIO连接
    try:
        # 检查MinIO连接状态
        minio_status = minio_service.is_connected and minio_service.client is not None
        if minio_status:
            # 尝试列举bucket来验证连接
            buckets = minio_service.client.list_buckets()
            checks["minio"] = {
                "status": "ready",
                "message": "MinIO connection successful",
                "bucket_count": len(buckets)
            }
        else:
            checks["minio"] = {
                "status": "not_ready",
                "message": "MinIO service not connected"
            }
            all_ready = False
    except Exception as e:
        checks["minio"] = {
            "status": "not_ready",
            "message": f"MinIO check failed: {str(e)}"
        }
        all_ready = False
    
    # 计算检查耗时
    check_duration = time.time() - start_time
    
    response_data = {
        "status": "ready" if all_ready else "not_ready",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "check_duration_seconds": round(check_duration, 3),
        "services": checks
    }
    
    # 根据readiness状态返回适当的HTTP状态码
    status_code = 200 if all_ready else 503
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )

# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Legal Docs MVP API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "readiness": "/ready"
    }

# 队列状态接口
@app.get("/kafka-status")
async def get_kafka_status():
    """获取Kafka连接状态信息"""
    try:
        status = kafka_service.get_connection_status()
        return {
            "status": "success",
            "data": status,
            "timestamp": "2025-02-18T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Failed to get kafka status: {e}")
        raise HTTPException(status_code=500, detail=f"获取Kafka状态失败: {str(e)}")

if __name__ == "__main__":
    # 在生产环境中禁用reload模式，避免文件监控导致容器不健康
    # 只有在设置了 RELOAD_MODE=true 环境变量时才启用reload
    reload_mode = os.getenv("RELOAD_MODE", "false").lower() == "true"
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=reload_mode,
        log_level=settings.log_level.lower()
    )
