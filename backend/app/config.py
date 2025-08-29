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
    gemini_model: str = "gemini-2.5-pro"
    
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

# Gemini服务提示词配置
# 集中管理所有AI模型的提示词，便于维护和优化

# 文件分类提示词
CLASSIFICATION_PROMPT = """
请分析以下文件内容，将其分类为以下5个类别之一：
1. 发票 - 各类发票文档
2. 租赁协议 - 物业租赁协议文档  
3. 变更/解除协议 - 租赁变更或解除协议
4. 账单 - 各类账单文档
5. 银行回单 - 银行转账回单

文件名: {filename}
文件类型: {file_type}

请返回JSON格式的结果：
{{
    "category": "分类名称",
    "confidence": 0.0-1.0的置信度,
    "reason": "分类理由",
    "key_info": "关键信息摘要"
}}

如果无法确定分类，请将category设为"未识别"，confidence设为0.0
"""

# 字段提取提示词模板
FIELD_EXTRACTION_PROMPT = """
请分析以下文档，提取指定的字段信息。

文件名: {filename}
文件类型: {file_type}
文档分类: {category} - {description}

需要提取的字段：
{extraction_fields}

请返回JSON格式的结果：
{{
    "extraction_data": {{
        "字段名": "提取的值"
    }},
    "missing_fields": ["未能提取的字段列表"],
    "extraction_confidence": 0.0-1.0的提取置信度,
    "notes": "提取说明或备注"
}}

提取要求：
1. 只提取上述指定的字段，不要提取其他字段
2. 如果某个字段无法提取，请在missing_fields中列出
3. 金额字段请保持数字格式，不要包含货币符号
4. 日期字段请使用YYYY-MM-DD格式
5. 如果字段值为空或无法确定，请设为null
6. 提取应该基于文件的实际内容
7. 对于中文字段名，请保持中文格式
"""

# 字段提取提示词（同时进行分类和字段提取）
COMBINED_EXTRACTION_PROMPT = """
请分析以下文档，先进行文件分类，再根据分类结果提取对应的字段信息。

文件名: {filename}
文件类型: {file_type}

请返回JSON格式的结果：
{{
    "category": "文件分类结果",
    "classification_confidence": 0.0-1.0的分类置信度,
    "classification_reason": "分类理由",
    "extraction_data": {{
        "字段名": "提取的值"
    }},
    "missing_fields": ["未能提取的字段列表"],
    "extraction_confidence": 0.0-1.0的提取置信度,
    "notes": "提取说明或备注"
}}

分类要求：
请将文件分类为以下5个类别之一：

1. 发票 - 各类发票文档
   需要提取的字段：
   {invoice_fields}

2. 租赁协议 - 物业租赁协议文档  
   需要提取的字段：
   {lease_fields}

3. 变更/解除协议 - 租赁变更或解除协议
   需要提取的字段：
   {amendment_fields}

4. 账单 - 各类账单文档
   需要提取的字段：
   {bill_fields}

5. 银行回单 - 银行转账回单
   需要提取的字段：
   {bank_fields}

字段提取要求：
1. 先确定文档属于上述哪个分类
2. 只提取该分类下定义的字段，不要提取其他分类的字段
3. 如果某个字段无法提取，请在missing_fields中列出
4. 金额字段请保持数字格式，不要包含货币符号
5. 日期字段请使用YYYY-MM-DD格式
6. 如果字段值为空或无法确定，请设为null
7. 分类和字段提取应该基于文件的实际内容
8. 对于中文字段名，请保持中文格式
"""
