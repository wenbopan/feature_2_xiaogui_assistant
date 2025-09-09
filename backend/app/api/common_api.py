from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import timedelta
import logging
import time
from datetime import datetime

from app.models.database import get_db
from app.auth import (
    authenticate_user, create_access_token, get_current_active_user, 
    Token, User, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/v1", tags=["common"])
logger = logging.getLogger(__name__)

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录接口"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-02-18T00:00:00Z",
        "version": "1.0.0"
    }

@router.get("/ready")
async def readiness_check():
    """Readiness检查 - 检查所有依赖服务是否就绪"""
    from app.models.database import engine
    from app.services.minio_service import minio_service
    from app.services.kafka_service import kafka_service
    from app.consumers import kafka_consumer_service, simple_file_classification_consumer, simple_field_extraction_consumer
    
    start_time = time.time()
    checks = {}
    all_ready = True
    
    # 检查数据库连接
    """
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
    """
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
        simple_classification_status = simple_file_classification_consumer.running
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
        simple_extraction_status = simple_field_extraction_consumer.running
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
    """
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
     """
    
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

# ============================================================================
# CONFIGURATION MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/config/instructions")
async def get_instructions_config(current_user: User = Depends(get_current_active_user)):
    """获取当前指令配置（包含内存中的指令）"""
    from app.config import instructions_manager
    try:
        config = instructions_manager.get_config()
        memory_instructions = instructions_manager.get_memory_instructions()
        return {
            "success": True,
            "config": config,
            "memory_instructions": memory_instructions,
            "last_modified": instructions_manager._last_modified,
            "config_path": instructions_manager.config_path
        }
    except Exception as e:
        logger.error(f"Failed to get instructions config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

@router.post("/config/instructions/hot-swap")
async def hot_swap_instructions(instructions_data: dict, current_user: User = Depends(get_current_active_user)):
    """热交换指令（更新内存中的指令）"""
    from app.config import instructions_manager
    try:
        # 验证输入数据 - 使用中文分类名
        required_categories = ['发票', '租赁协议', '变更/解除协议', '账单', '银行回单']
        for category in required_categories:
            if category not in instructions_data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required category: {category}"
                )
        
        # 执行热交换
        instructions_manager.hot_swap_instructions(instructions_data)
        
        # 获取更新后的配置
        config = instructions_manager.get_config()
        memory_instructions = instructions_manager.get_memory_instructions()
        
        return {
            "success": True,
            "message": "Instructions hot-swapped successfully",
            "config": config,
            "memory_instructions": memory_instructions,
            "last_modified": instructions_manager._last_modified
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to hot-swap instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to hot-swap instructions: {str(e)}")

@router.post("/config/instructions/reset")
async def reset_instructions_to_original(current_user: User = Depends(get_current_active_user)):
    """重置指令为原始配置"""
    from app.config import instructions_manager
    try:
        instructions_manager.reset_to_original()
        config = instructions_manager.get_config()
        memory_instructions = instructions_manager.get_memory_instructions()
        
        return {
            "success": True,
            "message": "Instructions reset to original config successfully",
            "config": config,
            "memory_instructions": memory_instructions,
            "last_modified": instructions_manager._last_modified
        }
    except Exception as e:
        logger.error(f"Failed to reset instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset instructions: {str(e)}")

@router.get("/config/instructions/category/{category}")
async def get_instruction_for_category(category: str, current_user: User = Depends(get_current_active_user)):
    """获取指定分类的指令"""
    from app.config import instructions_manager
    try:
        instruction = instructions_manager.get_instruction_for_category(category)
        return {
            "success": True,
            "category": category,
            "instruction": instruction
        }
    except Exception as e:
        logger.error(f"Failed to get instruction for category {category}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get instruction: {str(e)}")
