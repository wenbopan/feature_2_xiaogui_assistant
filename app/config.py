from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # MinIO 配置
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password123"
    minio_bucket: str = "legal-docs"
    minio_secure: bool = False
    
    # Kafka 配置
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_prefix: str = "legal"
    
    # Gemini 配置
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    
    # 数据库配置
    # 优先使用环境变量DATABASE_URL，如果没有则使用PostgreSQL配置构建
    database_url: str = ""
    
    # PostgreSQL 配置（当database_url为空时使用）
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "panwenbo"  # 改为当前用户
    postgres_password: str = ""  # 当前用户通常不需要密码
    postgres_db: str = "legal_docs_dev"
    
    # 应用配置
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # 重试配置
    retry_max_attempts: int = 3
    retry_backoffs: str = "30s,2m,5m"  # 改为字符串，在getter中转换
    
    @property
    def retry_backoffs_list(self) -> List[str]:
        """将字符串格式的重试间隔转换为列表"""
        return [interval.strip() for interval in self.retry_backoffs.split(",")]
    
    @property
    def database_url_final(self) -> str:
        """构建最终的数据库URL，优先使用环境变量中的DATABASE_URL"""
        if self.database_url:
            return self.database_url
        
        # 如果没有设置DATABASE_URL，则使用PostgreSQL配置构建
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    # 文件处理配置
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    max_zip_size: int = 1024 * 1024 * 1024  # 1GB
    max_extracted_files: int = 10000
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 全局配置实例
settings = Settings()

# 确保必要的目录存在
def ensure_directories():
    """确保必要的目录存在"""
    os.makedirs("logs", exist_ok=True)
    
    # 不创建项目根目录下的temp和uploads目录
    # 让各个服务使用系统临时目录，避免项目目录污染
