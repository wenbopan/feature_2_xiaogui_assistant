from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uvicorn
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager

from app.config import settings, ensure_directories
from app.models.database import create_tables
from app.api import api
from app.services.kafka_service import kafka_service
from app.services.kafka_consumer import kafka_consumer_service
from app.services.field_extraction_consumer import field_extraction_consumer
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global content_consumer_thread, field_extraction_thread
    
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
    
    logger.info("Application startup completed")
    
    yield
    
    # 关闭时
    logger.info("Shutting down Legal Docs MVP application...")
    
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
app.include_router(api.router, prefix="/api")

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
    return {
        "status": "healthy",
        "timestamp": "2025-02-18T00:00:00Z",
        "version": "1.0.0"
    }

# Readiness检查接口
# @app.get("/ready")
# async def readiness_check():
#     """Readiness检查 - 检查所有依赖服务是否就绪"""
#     from datetime import datetime
#     import time
#     from app.models.database import engine
#     from app.services.minio_service import minio_service
#     
#     start_time = time.time()
#     checks = {}
#     all_ready = True
#     
#     # 检查数据库连接
#     try:
#         # 测试数据库连接
#         from sqlalchemy import text
#         with engine.connect() as conn:
#             conn.execute(text("SELECT 1"))
#         checks["database"] = {
#             "status": "ready",
#             "message": "Database connection successful"
#         }
#     except Exception as e:
#         checks["database"] = {
#             "status": "not_ready",
#             "message": f"Database connection failed: {str(e)}"
#         }
#         all_ready = False
#     
#     # 检查Kafka连接
#     try:
#         kafka_status = kafka_service.get_connection_status()
#         if kafka_status["connected"] and kafka_status["producer_connected"]:
#             checks["kafka"] = {
#                 "status": "ready",
#                 "message": "Kafka producer connected",
#                 "details": kafka_status
#             }
#         else:
#             checks["kafka"] = {
#                 "status": "not_ready",
#                 "message": "Kafka not fully connected",
#                 "details": kafka_status
#             }
#             all_ready = False
#     except Exception as e:
#         checks["kafka"] = {
#             "status": "not_ready",
#             "message": f"Kafka check failed: {str(e)}"
#         }
#         all_ready = False
#     
#     # 检查Kafka Consumer
#     try:
#         consumer_status = kafka_consumer_service.running and kafka_consumer_service.consumer is not None
#         if consumer_status:
#             checks["kafka_consumer"] = {
#                 "status": "ready",
#                 "message": "Kafka consumer running"
#             }
#         else:
#             checks["kafka_consumer"] = {
#                 "status": "not_ready",
#                 "message": "Kafka consumer not running"
#             }
#             all_ready = False
#     except Exception as e:
#         checks["kafka_consumer"] = {
#             "status": "not_ready",
#             "message": f"Kafka consumer check failed: {str(e)}"
#         }
#         all_ready = False
#     
#     # 检查MinIO连接
#     try:
#         # 检查MinIO连接状态
#         minio_status = minio_service.is_connected and minio_service.client is not None
#         if minio_status:
#             # 尝试列举bucket来验证连接
#             buckets = minio_service.client.list_buckets()
#             checks["minio"] = {
#                 "status": "ready",
#                 "message": "MinIO connection successful",
#                 "bucket_count": len(buckets)
#             }
#         else:
#             checks["minio"] = {
#                 "status": "not_ready",
#                 "message": "MinIO service not connected"
#             }
#             all_ready = False
#     except Exception as e:
#         checks["minio"] = {
#             "status": "not_ready",
#             "message": f"MinIO check failed: {str(e)}"
#         }
#         all_ready = False
#     
#     # 计算检查耗时
#     check_duration = time.time() - start_time
#     
#     response_data = {
#         "status": "ready" if all_ready else "not_ready",
#         "timestamp": datetime.now().isoformat(),
#         "version": "1.0.0",
#         "check_duration_seconds": round(check_duration, 3),
#         "services": checks
#     }
#     
#     # 根据readiness状态返回适当的HTTP状态码
#     status_code = 200 if all_ready else 503
#     
#     return JSONResponse(
#         status_code=status_code,
#         content=response_data
#     )

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
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
