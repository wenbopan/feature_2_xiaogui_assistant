from pydantic_settings import BaseSettings
from typing import List, Dict, Any
import os
import yaml
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # MinIO 配置 - Production defaults for containerized deployment
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password123"
    minio_bucket: str = "legal-docs"
    minio_secure: bool = False
    
    # Kafka 配置 - Production defaults for containerized deployment
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_prefix: str = "legal"
    
    # Gemini 配置 - 优先从环境变量读取，如果没有则使用默认值
    gemini_api_key: str = ""  # 默认值，可通过环境变量GEMINI_API_KEY覆盖
    gemini_model: str = "gemini-1.5-flash"
    
    # Qwen 配置 - 优先从环境变量读取，如果没有则使用默认值
    qwen_api_key: str = ""  # 默认值，可通过环境变量QWEN_API_KEY覆盖
    qwen_model: str = "qwen-vl-plus"
    
    # LLM 默认模型配置
    llm_default_model: str = "qwen"  # Default to Qwen for China deployment
    
    # 数据库配置 - Production defaults for containerized deployment
    database_url: str = "postgresql://panwenbo:@localhost:5432/legal_docs_dev"
    
    # PostgreSQL 配置（当database_url为空时使用）
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "panwenbo"
    postgres_password: str = ""
    postgres_db: str = "legal_docs_dev"
    
    # 应用配置 - Production defaults
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    
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

# =============================================================================
# YAML Configuration Loading with Hot Reload
# =============================================================================

class InstructionsConfigManager:
    """指令配置管理器，支持内存热交换"""
    
    def __init__(self):
        # Config file is at backend/config/instructions.yaml, not backend/app/config/
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "instructions.yaml")
        self._original_config = None  # 原始YAML配置（只读）
        self._memory_instructions = {}  # 内存中的指令（可热交换）
        self._last_modified = 0
        self._initialized = False  # 标记是否已初始化
    
    def initialize_config(self) -> None:
        """初始化配置（启动时调用）"""
        if self._initialized:
            logger.warning("Instructions config already initialized")
            return
            
        try:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Instructions config file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._original_config = yaml.safe_load(f)
            self._last_modified = os.path.getmtime(self.config_path)
            
            # 将指令加载到内存中
            instructions = self._original_config.get("instructions", {})
            for category, config in instructions.items():
                if isinstance(config, dict) and "instruction" in config:
                    self._memory_instructions[category] = config["instruction"]
                elif isinstance(config, str):
                    self._memory_instructions[category] = config
            
            # 验证所有必需的分类都存在 - 使用中文分类名
            required_categories = ['发票', '租赁协议', '变更/解除协议', '账单', '银行回单']
            missing_categories = [cat for cat in required_categories if cat not in self._memory_instructions]
            
            if missing_categories:
                raise ValueError(f"Missing required instruction categories: {missing_categories}")
            
            # 验证所有分类都有非空指令
            empty_categories = [cat for cat in required_categories if not self._memory_instructions.get(cat, '').strip()]
            if empty_categories:
                raise ValueError(f"Empty instructions for categories: {empty_categories}")
            
            self._initialized = True
            logger.info(f"Instructions config initialized successfully from: {self.config_path}")
            logger.info(f"Loaded categories: {list(self._memory_instructions.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to initialize instructions config: {e}")
            self._original_config = {"instructions": {}}
            self._memory_instructions = {}
            self._initialized = False
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置（包含内存中的指令）"""
        if not self._initialized:
            raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
            
        config = self._original_config.copy() if self._original_config else {"instructions": {}}
        
        # 用内存中的指令覆盖配置
        if "instructions" not in config:
            config["instructions"] = {}
        
        for category, instruction in self._memory_instructions.items():
            if category not in config["instructions"]:
                config["instructions"][category] = {}
            config["instructions"][category]["instruction"] = instruction
        
        return config
    
    def get_instruction_for_category(self, category: str) -> str:
        """获取指定分类的提取指令（从内存中读取）"""
        if not self._initialized:
            raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
            
        # 从内存中获取
        if category in self._memory_instructions:
            return self._memory_instructions[category]
        
        # 如果内存中没有，尝试从原始配置获取
        if self._original_config:
            instructions = self._original_config.get("instructions", {})
            if category in instructions:
                if isinstance(instructions[category], dict):
                    return instructions[category].get("instruction", "")
                elif isinstance(instructions[category], str):
                    return instructions[category]
        
        # 如果都没有，返回默认指令
        return "请从文档中提取相关信息。"
    
    def hot_swap_instructions(self, new_instructions: Dict[str, str]) -> None:
        """热交换指令（更新内存中的指令）"""
        if not self._initialized:
            raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
            
        logger.info(f"Hot swapping instructions for categories: {list(new_instructions.keys())}")
        
        # 验证输入 - 使用中文分类名
        required_categories = ['发票', '租赁协议', '变更/解除协议', '账单', '银行回单']
        for category in required_categories:
            if category not in new_instructions:
                raise ValueError(f"Missing required category: {category}")
        
        # 验证指令不为空
        empty_categories = [cat for cat in required_categories if not new_instructions.get(cat, '').strip()]
        if empty_categories:
            raise ValueError(f"Empty instructions for categories: {empty_categories}")
        
        # 更新内存中的指令
        for category, instruction in new_instructions.items():
            if category in required_categories:
                self._memory_instructions[category] = instruction
                logger.info(f"Updated instruction for category '{category}': {instruction[:50]}...")
        
        logger.info("Hot swap completed successfully")
    
    def reset_to_original(self) -> None:
        """重置为原始配置"""
        if not self._initialized:
            raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
            
        logger.info("Resetting instructions to original config...")
        self._memory_instructions.clear()
        
        # 重新从原始配置加载
        if self._original_config:
            instructions = self._original_config.get("instructions", {})
            for category, config in instructions.items():
                if isinstance(config, dict) and "instruction" in config:
                    self._memory_instructions[category] = config["instruction"]
                elif isinstance(config, str):
                    self._memory_instructions[category] = config
        
        logger.info("Reset to original config completed")
    
    def get_memory_instructions(self) -> Dict[str, str]:
        """获取当前内存中的指令"""
        if not self._initialized:
            raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
        return self._memory_instructions.copy()
    
    def get_original_config(self) -> Dict[str, Any]:
        """获取原始配置（只读）"""
        if not self._initialized:
            raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
        return self._original_config.copy() if self._original_config else {"instructions": {}}
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

# 全局配置管理器实例
instructions_manager = InstructionsConfigManager()

def load_instructions_config() -> Dict[str, Any]:
    """加载指令配置文件（向后兼容）"""
    if not instructions_manager.is_initialized():
        raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
    return instructions_manager.get_config()

def get_instruction_for_category(category: str) -> str:
    """获取指定分类的提取指令（向后兼容）"""
    if not instructions_manager.is_initialized():
        raise RuntimeError("Instructions config not initialized. Call initialize_config() first.")
    return instructions_manager.get_instruction_for_category(category)

# 加载指令配置（向后兼容）
# Note: INSTRUCTIONS_CONFIG will be available after initialize_config() is called
INSTRUCTIONS_CONFIG = None

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



# 字段提取提示词构建函数
def build_extraction_prompt(category: str, output_schema: str = None) -> str:
    """构建字段提取提示词"""
    from app.models.prompt_schemas import build_output_schema_for_category
    
    # 使用配置管理器实例获取指令（支持热重载）
    instruction = instructions_manager.get_instruction_for_category(category)
    
    # 如果配置管理器返回空指令，使用向后兼容函数作为后备
    if not instruction or instruction.strip() == "":
        logger.warning(f"Empty instruction from config manager for category '{category}', falling back to legacy function")
        instruction = get_instruction_for_category(category)
        
        # 如果后备也失败，使用默认指令
        if not instruction or instruction.strip() == "":
            logger.warning(f"Empty instruction from legacy function for category '{category}', using default instruction")
            instruction = "请从文档中提取相关信息。"
    
    logger.info(f"Using instruction for category '{category}': {instruction[:100]}{'...' if len(instruction) > 100 else ''}")
    
    # 如果没有提供output_schema，自动生成
    if output_schema is None:
        output_schema = build_output_schema_for_category(category)
    
    return f"""
{instruction}

请提取以下字段并以以下确切的JSON格式返回：
{{
    "category": "{category}",
    "classification_confidence": 1.0,
    "classification_reason": "使用提供的分类",
    "extraction_data": {output_schema},
    "missing_fields": [],
    "extraction_confidence": 0.9,
    "notes": "字段提取完成"
}}

提取要求：
1. 只提取上述指定的字段，不要提取其他字段
2. 如果某个字段无法提取，请在missing_fields中列出
3. 金额字段请保持数字格式，不要包含货币符号
4. 日期字段请使用YYYY-MM-DD格式
5. 如果字段值为空或无法确定，请设为null
6. 提取应该基于文件的实际内容
7. 对于中文字段名，请保持中文格式
8. 必须返回完整的JSON结构，包含所有必需字段
"""
