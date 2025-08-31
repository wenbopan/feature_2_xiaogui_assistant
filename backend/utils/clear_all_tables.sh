#!/bin/bash

# ==========================================
# 清除所有数据库表内容和MinIO数据的脚本
# 用于重新做端到端测试
# ==========================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 数据库配置
DB_NAME="${DB_NAME:-legal_docs_dev}"
DB_USER="${DB_USER:-$(whoami)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# MinIO配置
MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-admin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-password123}"
MINIO_BUCKET="${MINIO_BUCKET:-legal-docs}"

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -u, --user USER     数据库用户名 (默认: 当前系统用户)"
    echo "  -d, --database DB   数据库名 (默认: legal_docs_dev)"
    echo "  -h, --host HOST     数据库主机 (默认: localhost)"
    echo "  -p, --port PORT     数据库端口 (默认: 5432)"
    echo "  --help              显示此帮助信息"
    echo ""
    echo "环境变量:"
    echo "  DB_USER             数据库用户名"
    echo "  DB_NAME             数据库名"
    echo "  DB_HOST             数据库主机"
    echo "  DB_PORT             数据库端口"
    echo "  MINIO_ENDPOINT      MinIO端点 (默认: localhost:9000)"
    echo "  MINIO_ACCESS_KEY    MinIO访问密钥 (默认: admin)"
    echo "  MINIO_SECRET_KEY    MinIO密钥 (默认: password123)"
    echo "  MINIO_BUCKET        MinIO存储桶 (默认: legal-docs)"
    echo ""
    echo "示例:"
    echo "  $0                           # 使用默认值"
    echo "  $0 -u myuser -d mydb        # 指定用户和数据库"
    echo "  DB_USER=myuser $0           # 通过环境变量指定"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            DB_USER="$2"
            shift 2
            ;;
        -d|--database)
            DB_NAME="$2"
            shift 2
            ;;
        -h|--host)
            DB_HOST="$2"
            shift 2
            ;;
        -p|--port)
            DB_PORT="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${BLUE}[INFO] 数据库配置:${NC}"
echo -e "${BLUE}  - 用户: ${DB_USER}${NC}"
echo -e "${BLUE}  - 数据库: ${DB_NAME}${NC}"
echo -e "${BLUE}  - 主机: ${DB_HOST}${NC}"
echo -e "${BLUE}  - 端口: ${DB_PORT}${NC}"
echo ""

echo -e "${BLUE}[INFO] MinIO配置:${NC}"
echo -e "${BLUE}  - 端点: ${MINIO_ENDPOINT}${NC}"
echo -e "${BLUE}  - 存储桶: ${MINIO_BUCKET}${NC}"
echo -e "${BLUE}  - 访问密钥: ${MINIO_ACCESS_KEY}${NC}"
echo ""

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}[INFO] 🗑️  清除所有数据库表内容和MinIO数据${NC}"
echo -e "${BLUE}==========================================${NC}"

# 检查PostgreSQL是否运行
if ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] PostgreSQL 未运行或无法连接${NC}"
    echo -e "${YELLOW}[INFO] 请确保PostgreSQL服务正在运行${NC}"
    exit 1
fi

echo -e "${GREEN}[INFO] PostgreSQL 连接正常${NC}"

# 检查MinIO是否运行
echo -e "${BLUE}[STEP] 0. 检查MinIO连接...${NC}"
if command -v mc >/dev/null 2>&1; then
    # 使用mc客户端检查连接
    if mc alias set local http://$MINIO_ENDPOINT $MINIO_ACCESS_KEY $MINIO_SECRET_KEY >/dev/null 2>&1; then
        if mc ls local/$MINIO_BUCKET >/dev/null 2>&1; then
            echo -e "${GREEN}[INFO] MinIO 连接正常${NC}"
            MINIO_AVAILABLE=true
        else
            echo -e "${YELLOW}[WARN] MinIO 存储桶 ${MINIO_BUCKET} 不存在或无法访问${NC}"
            MINIO_AVAILABLE=false
        fi
    else
        echo -e "${YELLOW}[WARN] MinIO 连接失败，跳过MinIO清理${NC}"
        MINIO_AVAILABLE=false
    fi
else
    echo -e "${YELLOW}[WARN] mc 客户端未安装，跳过MinIO清理${NC}"
    echo -e "${YELLOW}[INFO] 可以通过以下命令安装mc客户端:${NC}"
    echo -e "${YELLOW}  macOS: brew install minio/stable/mc${NC}"
    echo -e "${YELLOW}  Linux: wget https://dl.min.io/client/mc/release/linux-amd64/mc && chmod +x mc${NC}"
    MINIO_AVAILABLE=false
fi

# 定义要清除的表（按依赖关系排序，先清除子表）
TABLES=(
    "file_extraction_failures"
    "field_extractions"
    "file_classifications"
    "processing_messages"
    "extraction_tasks"
    "file_metadata"
    "tasks"
)

# 存储清除前的记录数（使用普通变量，兼容性更好）
RECORD_COUNTS_FILE_EXTRACTION_FAILURES=0
RECORD_COUNTS_FIELD_EXTRACTIONS=0
RECORD_COUNTS_FILE_CLASSIFICATIONS=0
RECORD_COUNTS_PROCESSING_MESSAGES=0
RECORD_COUNTS_EXTRACTION_TASKS=0
RECORD_COUNTS_FILE_METADATA=0
RECORD_COUNTS_TASKS=0

# MinIO文件统计
MINIO_FILE_COUNT=0

echo -e "${BLUE}[STEP] 1. 统计清除前的记录数...${NC}"

# 统计每个表的记录数
for table in "${TABLES[@]}"; do
    echo -e "${YELLOW}[INFO] 统计表 ${table} 的记录数...${NC}"
    
    # 使用psql查询记录数
    count=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ')
    
    if [ $? -eq 0 ] && [ "$count" != "" ]; then
        # 根据表名设置对应的变量
        case $table in
            "file_extraction_failures")
                RECORD_COUNTS_FILE_EXTRACTION_FAILURES=$count
                ;;
            "field_extractions")
                RECORD_COUNTS_FIELD_EXTRACTIONS=$count
                ;;
            "file_classifications")
                RECORD_COUNTS_FILE_CLASSIFICATIONS=$count
                ;;
            "processing_messages")
                RECORD_COUNTS_PROCESSING_MESSAGES=$count
                ;;
            "extraction_tasks")
                RECORD_COUNTS_EXTRACTION_TASKS=$count
                ;;
            "file_metadata")
                RECORD_COUNTS_FILE_METADATA=$count
                ;;
            "tasks")
                RECORD_COUNTS_TASKS=$count
                ;;
        esac
        echo -e "${GREEN}[INFO] 表 ${table}: ${count} 条记录${NC}"
    else
        echo -e "${YELLOW}[WARN] 表 ${table}: 无法获取记录数或表不存在${NC}"
    fi
done

# 统计MinIO文件数量
if [ "$MINIO_AVAILABLE" = true ]; then
    echo -e "${YELLOW}[INFO] 统计MinIO存储桶中的文件数量...${NC}"
    # 使用正确的mc命令格式统计文件数量
    MINIO_FILE_COUNT=$(mc ls local/$MINIO_BUCKET --recursive 2>/dev/null | wc -l)
    echo -e "${GREEN}[INFO] MinIO存储桶: ${MINIO_FILE_COUNT} 个文件${NC}"
fi

echo -e "${BLUE}[STEP] 2. 开始清除表内容...${NC}"

# 先禁用外键约束检查
echo -e "${YELLOW}[INFO] 禁用外键约束检查...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SET session_replication_role = replica;" 2>/dev/null

# 清除每个表的内容
for table in "${TABLES[@]}"; do
    echo -e "${YELLOW}[INFO] 清除表 ${table} 的内容...${NC}"
    
    # 使用psql清除表内容
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "DELETE FROM $table;" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS] 表 ${table} 内容已清除${NC}"
    else
        echo -e "${RED}[ERROR] 清除表 ${table} 失败${NC}"
    fi
done

# 重新启用外键约束检查
echo -e "${YELLOW}[INFO] 重新启用外键约束检查...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SET session_replication_role = DEFAULT;" 2>/dev/null

echo -e "${BLUE}[STEP] 3. 清除MinIO数据...${NC}"

if [ "$MINIO_AVAILABLE" = true ]; then
    echo -e "${YELLOW}[INFO] 开始清除MinIO存储桶中的所有文件...${NC}"
    
    # 列出所有文件
    echo -e "${YELLOW}[INFO] 列出存储桶中的所有文件...${NC}"
    mc ls local/$MINIO_BUCKET --recursive 2>/dev/null | head -20
    
    if [ $MINIO_FILE_COUNT -gt 0 ]; then
        echo -e "${YELLOW}[INFO] 删除存储桶中的所有文件...${NC}"
        
        # 删除所有文件（保留存储桶）
        # 使用正确的mc命令删除所有对象
        mc rm local/$MINIO_BUCKET --recursive --force 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[SUCCESS] MinIO存储桶中的所有文件已删除${NC}"
            
            # 验证删除结果
            echo -e "${YELLOW}[INFO] 验证删除结果...${NC}"
            remaining_files=$(mc ls local/$MINIO_BUCKET --recursive 2>/dev/null | wc -l)
            if [ "$remaining_files" -eq 0 ]; then
                echo -e "${GREEN}[SUCCESS] 验证通过：存储桶中无剩余文件${NC}"
            else
                echo -e "${RED}[ERROR] 验证失败：存储桶中仍有 ${remaining_files} 个文件${NC}"
            fi
        else
            echo -e "${RED}[ERROR] 删除MinIO文件失败${NC}"
        fi
    else
        echo -e "${YELLOW}[INFO] MinIO存储桶中无文件需要删除${NC}"
    fi
else
    echo -e "${YELLOW}[INFO] 跳过MinIO清理（MinIO不可用）${NC}"
fi

echo -e "${BLUE}[STEP] 4. 清除完成，汇报结果...${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}[SUMMARY] 清除结果汇总${NC}"
echo -e "${BLUE}==========================================${NC}"

total_cleared=0

# 显示每个表的清除结果
if [ "$RECORD_COUNTS_FILE_EXTRACTION_FAILURES" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 file_extraction_failures: 清除了 ${RECORD_COUNTS_FILE_EXTRACTION_FAILURES} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_FILE_EXTRACTION_FAILURES))
else
    echo -e "${YELLOW}⚠️  表 file_extraction_failures: 无记录${NC}"
fi

if [ "$RECORD_COUNTS_FIELD_EXTRACTIONS" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 field_extractions: 清除了 ${RECORD_COUNTS_FIELD_EXTRACTIONS} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_FIELD_EXTRACTIONS))
else
    echo -e "${YELLOW}⚠️  表 field_extractions: 无记录${NC}"
fi

if [ "$RECORD_COUNTS_FILE_CLASSIFICATIONS" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 file_classifications: 清除了 ${RECORD_COUNTS_FILE_CLASSIFICATIONS} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_FILE_CLASSIFICATIONS))
else
    echo -e "${YELLOW}⚠️  表 file_classifications: 无记录${NC}"
fi

if [ "$RECORD_COUNTS_PROCESSING_MESSAGES" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 processing_messages: 清除了 ${RECORD_COUNTS_PROCESSING_MESSAGES} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_PROCESSING_MESSAGES))
else
    echo -e "${YELLOW}⚠️  表 processing_messages: 无记录${NC}"
fi

if [ "$RECORD_COUNTS_EXTRACTION_TASKS" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 extraction_tasks: 清除了 ${RECORD_COUNTS_EXTRACTION_TASKS} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_EXTRACTION_TASKS))
else
    echo -e "${YELLOW}⚠️  表 extraction_tasks: 无记录${NC}"
fi

if [ "$RECORD_COUNTS_FILE_METADATA" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 file_metadata: 清除了 ${RECORD_COUNTS_FILE_METADATA} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_FILE_METADATA))
else
    echo -e "${YELLOW}⚠️  表 file_metadata: 无记录${NC}"
fi

if [ "$RECORD_COUNTS_TASKS" -gt 0 ]; then
    echo -e "${GREEN}✅ 表 tasks: 清除了 ${RECORD_COUNTS_TASKS} 条记录${NC}"
    total_cleared=$((total_cleared + RECORD_COUNTS_TASKS))
else
    echo -e "${YELLOW}⚠️  表 tasks: 无记录${NC}"
fi

# 显示MinIO清理结果
if [ "$MINIO_AVAILABLE" = true ]; then
    if [ "$MINIO_FILE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✅ MinIO存储桶: 清除了 ${MINIO_FILE_COUNT} 个文件${NC}"
        total_cleared=$((total_cleared + MINIO_FILE_COUNT))
    else
        echo -e "${YELLOW}⚠️  MinIO存储桶: 无文件${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  MinIO: 跳过清理（不可用）${NC}"
fi

echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}[SUCCESS] 总共清除了 ${total_cleared} 条记录/文件${NC}"
echo -e "${BLUE}[INFO] 所有表内容和MinIO数据已清除，可以开始新的端到端测试${NC}"
echo -e "${BLUE}==========================================${NC}"

# 自动重置自增序列
echo -e "${BLUE}[STEP] 5. 重置自增序列...${NC}"

for table in "${TABLES[@]}"; do
    # 检查表是否有自增列
    sequence_query="SELECT column_name FROM information_schema.columns WHERE table_name = '$table' AND column_default LIKE 'nextval%';"
    sequence_column=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "$sequence_query" 2>/dev/null | tr -d ' ')
    
    if [ "$sequence_column" != "" ]; then
        echo -e "${YELLOW}[INFO] 重置表 ${table} 的序列...${NC}"
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "ALTER SEQUENCE ${table}_${sequence_column}_seq RESTART WITH 1;" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[SUCCESS] 表 ${table} 序列已重置${NC}"
        else
            echo -e "${RED}[ERROR] 重置表 ${table} 序列失败${NC}"
        fi
    fi
done

echo -e "${GREEN}[SUCCESS] 🎉 数据库和MinIO清理完成！${NC}"
echo -e "${BLUE}[INFO] 现在可以开始新的端到端测试了${NC}"
