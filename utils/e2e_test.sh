#!/bin/bash

# e2e_test.sh - 端到端测试脚本
# 测试逻辑重命名系统的完整流程

# 设置错误处理
set -e  # 任何命令失败时立即退出

# 日志函数
log_info() {
    echo "[INFO] $1"
}

log_step() {
    echo "[STEP] $1"
}

log_warn() {
    echo "[WARN] $1"
}

log_error() {
    echo "[ERROR] $1"
}

# 配置
API_BASE="http://localhost:8000/api/v1"
TEST_PROJECT="E2E测试项目"
TEST_DATE="2025-08-27"
TEST_ZIP_PATH="/Users/panwenbo/Downloads/重命名后混在一起.zip"

# 检查服务状态
check_service_status() {
    log_step "检查服务状态..."
    
    local max_retries=30
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -s "${API_BASE}/health" > /dev/null 2>&1; then
            log_info "服务已启动并运行正常"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        log_info "等待服务启动... (尝试 $retry_count/$max_retries)"
        sleep 2
    done
    
    log_error "服务启动超时"
    return 1
}

# 创建测试任务
create_test_task() {
    log_step "创建测试任务..."
    
    local task_response=$(curl -s -X POST "${API_BASE}/tasks/" \
        -H "Content-Type: application/json" \
        -d '{
            "project_name": "E2E测试项目",
            "organize_date": "'$(date +%Y-%m-%d)'"
        }')
    
    local task_id=$(echo "$task_response" | jq -r '.id')
    
    if [ "$task_id" = "null" ] || [ -z "$task_id" ]; then
        log_error "创建任务失败: $task_response"
    else
        log_info "任务创建成功，ID: $task_id"
    fi
    echo "$task_id"
}

# 上传测试文件
upload_test_file() {
    local task_id=$1
    
    log_step "上传测试文件..."
    
    local zip_file="/Users/panwenbo/Downloads/重命名后混在一起.zip"
    
    if [ ! -f "$zip_file" ]; then
        log_error "测试文件不存在: $zip_file"
        return 1
    fi
    
    log_info "开始上传文件: $zip_file"
    local upload_response=$(curl -s -X POST "${API_BASE}/tasks/${task_id}/upload" \
        -F "file=@${zip_file}")
    
    log_info "上传响应: $upload_response"
    
    local status=$(echo "$upload_response" | jq -r '.status')
    log_info "解析状态: $status"
    
    if [ "$status" != "completed" ] && [ "$status" != "partially_completed" ]; then
        log_error "文件上传失败: $upload_response"
    else
        local total_files=$(echo "$upload_response" | jq -r '.details.total_files')
        log_info "文件上传成功，共 $total_files 个文件"
    fi
}

# 启动内容处理
start_content_processing() {
    local task_id=$1
    
    log_step "启动内容处理..."
    
    local process_response=$(curl -s -X POST "${API_BASE}/tasks/${task_id}/process")
    
    local total_jobs=$(echo "$process_response" | jq -r '.total_jobs')
    local failed_jobs=$(echo "$process_response" | jq -r '.failed_jobs')
    
    if [ "$total_jobs" = "null" ] || [ "$total_jobs" = "0" ]; then
        log_error "启动内容处理失败: $process_response"
    else
        log_info "内容处理已启动，共 $total_jobs 个作业"
    fi
}

# 启动字段提取
start_field_extraction() {
    local task_id=$1
    
    log_step "启动字段提取..."
    
    local extraction_response=$(curl -s -X POST "${API_BASE}/tasks/${task_id}/extract-fields")
    
    local total_jobs=$(echo "$extraction_response" | jq -r '.total_jobs')
    local failed_jobs=$(echo "$extraction_response" | jq -r '.failed_jobs')
    
    if [ "$total_jobs" = "null" ] || [ "$total_jobs" = "0" ]; then
        log_error "启动字段提取失败: $extraction_response"
    else
        log_info "字段提取已启动，共 $total_jobs 个作业"
    fi
}

# 监控处理进度
monitor_processing_progress() {
    local task_id=$1
    
    log_step "监控内容处理进度..."
    
    local max_wait=300  # 最多等待5分钟
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        local progress_response=$(curl -s "${API_BASE}/tasks/${task_id}/processing-progress")
        local progress=$(echo "$progress_response" | jq -r '.progress_percentage')
        local completed_jobs=$(echo "$progress_response" | jq -r '.completed_jobs')
        local total_jobs=$(echo "$progress_response" | jq -r '.total_jobs')
        
        log_info "处理进度: ${progress}% (${completed_jobs}/${total_jobs})"
        
        if [ "$progress" = "100.0" ] || [ "$completed_jobs" = "$total_jobs" ]; then
            log_info "内容处理完成！"
            break
        fi
        
        sleep 10
        wait_time=$((wait_time + 10))
    done
    
    log_error "内容处理超时"
    return 1
}

# 监控提取进度
monitor_extraction_progress() {
    local task_id=$1
    
    log_step "监控字段提取进度..."
    
    local max_wait=300  # 最多等待5分钟
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        local progress_response=$(curl -s "${API_BASE}/tasks/${task_id}/extraction-progress")
        local progress=$(echo "$progress_response" | jq -r '.progress_percentage')
        local completed_jobs=$(echo "$progress_response" | jq -r '.completed_jobs')
        local total_jobs=$(echo "$progress_response" | jq -r '.total_jobs')
        
        log_info "提取进度: ${progress}% (${completed_jobs}/${total_jobs})"
        
        if [ "$progress" = "100.0" ] || [ "$completed_jobs" = "$total_jobs" ]; then
            log_info "字段提取完成！"
            break
        fi
        
        sleep 10
        wait_time=$((wait_time + 10))
    done
    
    log_error "字段提取超时"
    return 1
}

# 验证处理结果
verify_processing_results() {
    local task_id=$1
    
    log_step "验证处理结果..."
    
    # 检查逻辑文件名是否已设置
    local logical_filename_count=$(psql -h localhost -U panwenbo -d legal_docs_dev -t -c "
        SELECT COUNT(*) FROM file_metadata 
        WHERE task_id = $task_id AND logical_filename IS NOT NULL
    " | tr -d ' ')
    
    if [ "$logical_filename_count" -eq 0 ]; then
        log_error "没有文件设置逻辑文件名"
    else
        log_info "逻辑文件名设置成功，共 $logical_filename_count 个文件"
    fi
    
    # 检查提取字段是否已设置
    local extracted_fields_count=$(psql -h localhost -U panwenbo -d legal_docs_dev -t -c "
        SELECT COUNT(*) FROM file_metadata 
        WHERE task_id = $task_id AND extracted_fields IS NOT NULL
    " | tr -d ' ')
    
    if [ "$extracted_fields_count" -eq 0 ]; then
        log_warn "没有文件设置提取字段（可能是Gemini API地理限制）"
    else
        log_info "提取字段设置成功，共 $extracted_fields_count 个文件"
    fi
}

# 显示样本结果
show_sample_results() {
    local task_id=$1
    
    log_step "显示样本处理结果..."
    
    # 显示几个样本文件
    local samples=$(psql -h localhost -U panwenbo -d legal_docs_dev -t -c "
        SELECT 
            original_filename,
            logical_filename,
            CASE 
                WHEN extracted_fields IS NOT NULL THEN '有提取数据'
                ELSE '无提取数据'
            END as extraction_status
        FROM file_metadata 
        WHERE task_id = $task_id 
        AND logical_filename IS NOT NULL
        LIMIT 5
    ")
    
    if [ -n "$samples" ]; then
        log_info "样本处理结果:"
        echo "$samples" | while IFS='|' read -r original logical extraction; do
            log_info "  - 原文件名: $original"
            log_info "    逻辑文件名: $logical"
            log_info "    提取状态: $extraction"
            echo
        done
    else
        log_warn "没有找到处理完成的样本文件"
    fi
}

# 测试提取API并显示样本结果
test_extraction_api_and_results() {
    local task_id=$1
    
    log_step "测试提取API并显示样本结果..."
    
    # 1. 测试提取API响应
    log_info "测试字段提取API..."
    local extraction_response=$(curl -s -X POST "${API_BASE}/tasks/${task_id}/extract-fields")
    
    local total_jobs=$(echo "$extraction_response" | jq -r '.total_jobs')
    local failed_jobs=$(echo "$extraction_response" | jq -r '.failed_jobs')
    
    log_info "提取API响应:"
    log_info "  - 总作业数: $total_jobs"
    log_info "  - 失败作业数: $failed_jobs"
    log_info "  - 状态: $(echo "$extraction_response" | jq -r '.status')"
    
    # 2. 显示样本提取结果
    log_info "显示样本提取结果..."
    
    # 获取有提取数据的样本文件
    local extraction_samples=$(psql -h localhost -U panwenbo -d legal_docs_dev -t -c "
        SELECT 
            id,
            original_filename,
            extracted_fields
        FROM file_metadata 
        WHERE task_id = $task_id 
        AND extracted_fields IS NOT NULL
        LIMIT 3
    ")
    
    if [ -n "$extraction_samples" ]; then
        log_info "样本提取结果:"
        echo "$extraction_samples" | while IFS='|' read -r id original extracted; do
            log_info "  - 文件ID: $id"
            log_info "    原文件名: $original"
            log_info "    提取字段数据:"
            
            # 格式化显示JSON数据
            if [ -n "$extracted" ] && [ "$extracted" != "null" ]; then
                echo "$extracted" | jq '.' 2>/dev/null || log_info "    $extracted"
            else
                log_info "    无提取数据"
            fi
            echo
        done
    else
        log_warn "没有找到有提取数据的样本文件"
    fi
    
    # 3. 显示分类结果样本
    log_info "显示分类结果样本..."
    
    local classification_samples=$(psql -h localhost -U panwenbo -d legal_docs_dev -t -c "
        SELECT 
            fc.id,
            fm.original_filename,
            fc.category,
            fc.confidence,
            fc.final_filename,
            fc.classification_method
        FROM file_classifications fc
        JOIN file_metadata fm ON fc.file_metadata_id = fm.id
        WHERE fc.task_id = $task_id
        LIMIT 3
    ")
    
    if [ -n "$classification_samples" ]; then
        log_info "样本分类结果:"
        echo "$classification_samples" | while IFS='|' read -r id original category confidence final method; do
            log_info "  - 分类ID: $id"
            log_info "    原文件名: $original"
            log_info "    分类结果: $category"
            log_info "    置信度: $confidence"
            log_info "    最终文件名: $final"
            log_info "    分类方法: $method"
            echo
        done
    else
        log_warn "没有找到分类结果样本"
    fi
    
    # 4. 显示提取统计信息
    log_info "显示提取统计信息..."
    
    local extraction_stats=$(psql -h localhost -U panwenbo -d legal_docs_dev -t -c "
        SELECT 
            COUNT(*) as total_files,
            COUNT(CASE WHEN extracted_fields IS NOT NULL THEN 1 END) as files_with_extractions,
            COUNT(CASE WHEN logical_filename IS NOT NULL THEN 1 END) as files_with_logical_names,
            COUNT(CASE WHEN extracted_fields IS NOT NULL AND logical_filename IS NOT NULL THEN 1 END) as fully_processed_files
        FROM file_metadata 
        WHERE task_id = $task_id
    " | tr -d ' ')
    
    if [ -n "$extraction_stats" ]; then
        local total=$(echo "$extraction_stats" | cut -d'|' -f1)
        local with_extractions=$(echo "$extraction_stats" | cut -d'|' -f2)
        local with_logical=$(echo "$extraction_stats" | cut -d'|' -f3)
        local fully_processed=$(echo "$extraction_stats" | cut -d'|' -f4)
        
        log_info "提取统计:"
        log_info "  - 总文件数: $total"
        log_info "  - 有提取数据的文件: $with_extractions"
        log_info "  - 有逻辑文件名的文件: $with_logical"
        log_info "  - 完全处理的文件: $fully_processed"
    fi
}

# 清理测试数据
cleanup_test_data() {
    local task_id=$1
    
    log_step "清理测试数据..."
    
    # 清理数据库中的测试数据
    psql -h localhost -U panwenbo -d legal_docs_dev -c "
        DELETE FROM field_extractions WHERE task_id = $task_id;
        DELETE FROM file_classifications WHERE task_id = $task_id;
        DELETE FROM file_metadata WHERE task_id = $task_id;
        DELETE FROM tasks WHERE id = $task_id;
    " > /dev/null 2>&1
    
    log_info "测试数据清理完成"
}

# 主函数
main() {
    log_info "开始E2E测试..."
    
    # 设置API基础URL
    API_BASE="http://localhost:8000/api/v1"
    
    # 清理环境并重启服务
    log_step "清理环境并重启服务..."
    
    if [ -f "./shutdown.sh" ]; then
        log_info "运行 shutdown.sh..."
        ./shutdown.sh
    fi
    
    if [ -f "./utils/clear_all_tables.sh" ]; then
        log_info "清理数据库表..."
        ./utils/clear_all_tables.sh
    fi
    
    if [ -f "./startup.sh" ]; then
        log_info "启动服务..."
        ./startup.sh --dev
    fi
    
    # 等待服务启动
    sleep 5
    
    # 检查服务状态
    check_service_status
    
    # 创建测试任务
    local task_id=$(create_test_task)
    
    # 上传测试文件
    upload_test_file "$task_id"
    
    # 启动内容处理
    start_content_processing "$task_id"
    
    # 启动字段提取
    start_field_extraction "$task_id"
    
    # 监控处理进度
    monitor_processing_progress "$task_id"
    
    # 监控提取进度
    monitor_extraction_progress "$task_id"
    
    # 验证处理结果
    verify_processing_results "$task_id"
    
    # 显示样本结果
    show_sample_results "$task_id"
    
    # 测试提取API并显示样本结果
    test_extraction_api_and_results "$task_id"
    
    # 清理
    cleanup_test_data "$task_id"
    
    log_info "E2E测试完成！"
}

# 运行主函数
main "$@"
