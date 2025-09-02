"""
File type utilities using gRPC proto definitions
"""
from .common_pb2 import FileType

# Mapping from Chinese category names to FileType enum values
CATEGORY_TO_FILETYPE = {
    "发票": FileType.FILE_TYPE_INVOICE,
    "银行流水": FileType.FILE_TYPE_BANK_STATEMENT,
    "账单": FileType.FILE_TYPE_BILL,
    "租赁协议": FileType.FILE_TYPE_LEASE_AGREEMENT,
    "unknown": FileType.FILE_TYPE_UNKNOWN,
}

# Reverse mapping from FileType enum values to Chinese names
FILETYPE_TO_CATEGORY = {
    FileType.FILE_TYPE_INVOICE: "发票",
    FileType.FILE_TYPE_BANK_STATEMENT: "银行流水", 
    FileType.FILE_TYPE_BILL: "账单",
    FileType.FILE_TYPE_LEASE_AGREEMENT: "租赁协议",
    FileType.FILE_TYPE_UNKNOWN: "unknown",
}

def get_file_type_enum(category: str) -> int:
    """
    Convert Chinese category name to FileType enum value
    
    Args:
        category: Chinese category name (e.g., "发票", "银行流水")
        
    Returns:
        FileType enum value (0-4)
    """
    return CATEGORY_TO_FILETYPE.get(category, FileType.FILE_TYPE_UNKNOWN)

def get_category_name(file_type: int) -> str:
    """
    Convert FileType enum value to Chinese category name
    
    Args:
        file_type: FileType enum value (0-4)
        
    Returns:
        Chinese category name
    """
    return FILETYPE_TO_CATEGORY.get(file_type, "unknown")
