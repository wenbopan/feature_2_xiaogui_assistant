import os
import zipfile
import shutil
import logging
import tempfile
import uuid
import pdb
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.database import Task, FileMetadata, ProcessingMessage, FileExtractionFailure
from app.services.minio_service import minio_service
from app.services.kafka_service import kafka_service

logger = logging.getLogger(__name__)

class FileService:
    """文件处理服务"""
    
    def __init__(self):
        # 使用系统临时目录
        self.temp_dir = None
        # 支持的文件扩展名
        self.supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
    

    
    def process_zip_upload(self, task_id: int, zip_file_path: str, project_name: str, organize_date: str, db: Session) -> Dict[str, Any]:
        """处理ZIP文件上传 - 只负责解压和存储原始文件"""
        try:
            logger.info(f"Processing ZIP upload for task {task_id}")
            logger.info(f"ZIP file path: {zip_file_path}")
            logger.info(f"Project name: {project_name}")
            logger.info(f"Organize date: {organize_date}")
            
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="legal_docs_")
            logger.info(f"Created temporary directory: {self.temp_dir}")
            
            # 验证ZIP文件存在
            if not os.path.exists(zip_file_path):
                raise Exception(f"ZIP file not found: {zip_file_path}")
            
            # 验证ZIP文件大小
            zip_size = os.path.getsize(zip_file_path)
            logger.info(f"ZIP file size: {zip_size} bytes")
            
            # 1. 上传ZIP到MinIO
            zip_s3_key = f"tasks/{task_id}/uploads/original.zip"
            logger.info(f"Uploading ZIP to MinIO with key: {zip_s3_key}")
            
            if not minio_service.upload_file(zip_file_path, zip_s3_key):
                logger.error("Failed to upload ZIP to MinIO")
                raise Exception("Failed to upload ZIP to MinIO")
            
            logger.info("ZIP uploaded to MinIO successfully")
            
            # 2. 解压ZIP文件（只解压，不处理内容）
            logger.info("Starting ZIP extraction...")
            extraction_result = self._extract_zip(zip_file_path, task_id, db)
            extracted_files = extraction_result.get("files", [])
            failed_files = extraction_result.get("failed_files", [])
            
            logger.info(f"Extracted {len(extracted_files)} files from ZIP, {len(failed_files)} files failed")
            
            # 3. 更新任务状态
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "extracted"  # 改为extracted状态
                db.commit()
                logger.info(f"Task status updated to 'extracted'")
            
            total_files = len(extracted_files) + len(failed_files)
            logger.info(f"Task {task_id}: {len(extracted_files)} files extracted, {len(failed_files)} extraction failures")
            
            # 确定最终状态
            if failed_files and len(failed_files) == total_files:
                final_status = "extraction_failed"
            elif failed_files:
                final_status = "extraction_completed_with_errors"
            else:
                final_status = "extraction_success"
            
            logger.info(f"Final extraction status: {final_status}")
            
            return {
                "task_id": task_id,
                "total_files": total_files,
                "extracted_files": len(extracted_files),
                "extraction_failures": len(failed_files),
                "status": final_status
            }
            
        except Exception as e:
            logger.error(f"Failed to process ZIP upload for task {task_id}: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # 更新任务状态为失败
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                db.commit()
                logger.info("Task status updated to 'failed'")
            raise
        finally:
            # 清理临时目录
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                    logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
                    self.temp_dir = None
                except Exception as e:
                    logger.error(f"Failed to clean up temporary directory {self.temp_dir}: {e}")
    
    def create_content_processing_task(self, task_id: int, db: Session) -> Dict[str, Any]:
        """创建内容处理任务 - 为每个文件创建独立的Kafka任务"""
        try:
            # 验证任务状态 - 允许extracted和processing状态重新处理
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise Exception("Task not found")
            
            if task.status not in ["extracted", "processing"]:
                raise Exception(f"Task status must be 'extracted' or 'processing', current: {task.status}")
            
            # 清理之前的FileClassification记录，避免重复数据
            from app.models.database import FileClassification
            existing_classifications = db.query(FileClassification).filter(FileClassification.task_id == task_id).all()
            if existing_classifications:
                logger.info(f"Cleaning up {len(existing_classifications)} existing FileClassification records for task {task_id}")
                for classification in existing_classifications:
                    db.delete(classification)
                db.commit()
                logger.info(f"Successfully cleaned up existing FileClassification records")
            
            # 查询该任务下的所有文件
            files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
            if not files:
                raise Exception(f"No files found for task {task_id}")
            
            logger.info(f"Found {len(files)} files for task {task_id}, creating individual processing jobs")
            
            # 为每个文件创建独立的Kafka任务
            created_jobs = []
            failed_files = []
            
            for file_metadata in files:
                try:
                    job_id = str(uuid.uuid4())
                    
                    # 创建文件级别的Kafka任务消息
                    message = {
                        "job_id": job_id,
                        "task_id": task_id,
                        "file_id": file_metadata.id,  # 关键：包含具体文件ID
                        "s3_key": file_metadata.s3_key,
                        "original_filename": file_metadata.original_filename,
                        "file_type": file_metadata.file_type,
                        "type": "file_processing",  # 改为文件处理类型
                        "created_at": datetime.now().isoformat(),
                        "stages": ["content_reading", "classification", "renaming"]
                    }
                    
                    # 1. 检查是否已存在ProcessingMessage记录，如果存在则覆盖
                    existing_message = db.query(ProcessingMessage).filter(
                        ProcessingMessage.task_id == task_id,
                        ProcessingMessage.file_metadata_id == file_metadata.id,
                        ProcessingMessage.topic == "file.processing"
                    ).first()
                    
                    if existing_message:
                        # 覆盖现有记录
                        existing_message.job_id = job_id
                        existing_message.payload = message
                        existing_message.status = "created"
                        existing_message.created_at = datetime.now()
                        existing_message.updated_at = datetime.now()
                        existing_message.consumed_at = None
                        existing_message.completed_at = None
                        existing_message.error = None
                        existing_message.attempts = 0
                        logger.info(f"Updated existing ProcessingMessage record for file {file_metadata.original_filename}")
                    else:
                        # 创建新的ProcessingMessage记录
                        processing_message = ProcessingMessage(
                            job_id=job_id,
                            task_id=task_id,
                            file_metadata_id=file_metadata.id,
                            topic="file.processing",
                            payload=message,
                            status="created",
                            created_at=datetime.now()
                        )
                        db.add(processing_message)
                        logger.info(f"Created new ProcessingMessage record for file {file_metadata.original_filename}")
                    
                    # 2. 立即写入数据库
                    db.commit()
                    logger.info(f"Successfully saved ProcessingMessage record for job {job_id}")
                    
                    # 3. 立即发送Kafka消息
                    kafka_service.publish_message("file.processing", message)
                    logger.info(f"Successfully sent Kafka message for job {job_id}")
                    
                    # 4. 记录成功的job
                    created_jobs.append({
                        "job_id": job_id,
                        "file_id": file_metadata.id,
                        "filename": file_metadata.original_filename
                    })
                    
                    logger.info(f"Created processing job {job_id} for file {file_metadata.original_filename}")
                    
                except Exception as e:
                    logger.error(f"Failed to create processing job for file {file_metadata.original_filename}: {e}")
                    failed_files.append({
                        "file_id": file_metadata.id,
                        "filename": file_metadata.original_filename,
                        "error": str(e)
                    })
                    continue
            
            if failed_files:
                logger.warning(f"Failed to create {len(failed_files)} processing jobs for task {task_id}")
            
            return {
                "task_id": task_id,
                "total_jobs": len(created_jobs),
                "created_jobs": created_jobs,
                "failed_files": failed_files,
                "message": f"Content processing triggered for {len(created_jobs)} files"
            }
            
        except Exception as e:
            logger.error(f"Failed to create content processing task for task {task_id}: {e}")
            raise

    def create_field_extraction_task(self, task_id: int, db: Session) -> Dict[str, Any]:
        """创建字段提取任务 - 为每个文件创建独立的Kafka任务"""
        try:
            # 验证任务状态
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise Exception("Task not found")
            
            # 查询该任务下的所有文件
            files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
            if not files:
                raise Exception(f"No files found for task {task_id}")
            
            logger.info(f"Found {len(files)} files for task {task_id}, creating individual field extraction jobs")
            
            # 为每个文件创建独立的Kafka任务
            created_jobs = []
            failed_files = []
            
            for file_metadata in files:
                try:
                    job_id = str(uuid.uuid4())
                    
                    # 创建文件级别的Kafka任务消息
                    message = {
                        "type": "field_extraction_job",
                        "job_id": job_id,
                        "task_id": task_id,
                        "file_id": file_metadata.id,
                        "s3_key": file_metadata.s3_key,
                        "file_type": file_metadata.file_type,
                        "filename": file_metadata.original_filename
                    }
                    
                    # 1. 检查是否已存在ProcessingMessage记录，如果存在则覆盖
                    existing_message = db.query(ProcessingMessage).filter(
                        ProcessingMessage.task_id == task_id,
                        ProcessingMessage.file_metadata_id == file_metadata.id,
                        ProcessingMessage.topic == "field.extraction"
                    ).first()
                    
                    if existing_message:
                        # 覆盖现有记录
                        existing_message.job_id = job_id
                        existing_message.payload = message
                        existing_message.status = "created"
                        existing_message.created_at = datetime.now()
                        existing_message.updated_at = datetime.now()
                        existing_message.consumed_at = None
                        existing_message.completed_at = None
                        existing_message.error = None
                        existing_message.attempts = 0
                        logger.info(f"Updated existing ProcessingMessage record for field extraction file {file_metadata.original_filename}")
                    else:
                        # 创建新的ProcessingMessage记录
                        processing_message = ProcessingMessage(
                            job_id=job_id,
                            task_id=task_id,
                            file_metadata_id=file_metadata.id,
                            topic="field.extraction",
                            payload=message,
                            status="created",
                            created_at=datetime.now()
                        )
                        db.add(processing_message)
                        logger.info(f"Created new ProcessingMessage record for field extraction file {file_metadata.original_filename}")
                    
                    # 2. 立即写入数据库
                    db.commit()
                    logger.info(f"Successfully saved ProcessingMessage record for field extraction job {job_id}")
                    
                    # 3. 立即发送Kafka消息
                    kafka_service.publish_message("field.extraction", message)
                    logger.info(f"Successfully sent Kafka message for field extraction job {job_id}")
                    
                    # 4. 记录成功的job
                    created_jobs.append({
                        "job_id": job_id,
                        "file_id": file_metadata.id,
                        "filename": file_metadata.original_filename
                    })
                    
                    logger.info(f"Created field extraction job {job_id} for file {file_metadata.original_filename}")
                    
                except Exception as e:
                    logger.error(f"Failed to create field extraction job for file {file_metadata.original_filename}: {e}")
                    failed_files.append({
                        "file_id": file_metadata.id,
                        "filename": file_metadata.original_filename,
                        "error": str(e)
                    })
                    continue
            
            if failed_files:
                logger.warning(f"Failed to create {len(failed_files)} field extraction jobs for task {task_id}")
            
            return {
                "task_id": task_id,
                "total_jobs": len(created_jobs),
                "created_jobs": created_jobs,
                "failed_files": failed_files,
                "message": f"Field extraction triggered for {len(created_jobs)} files"
            }
            
        except Exception as e:
            logger.error(f"Failed to create field extraction task for task {task_id}: {e}")
            raise
    
    def _extract_zip(self, zip_path: str, task_id: int, db: Session) -> Dict[str, Any]:
        """解压ZIP文件 - 只负责解压和存储，不处理内容"""
        extracted_files = []
        failed_files = []
        
        try:
            logger.info(f"Opening ZIP file: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 检查文件数量限制
                file_list = zip_ref.namelist()
                logger.info(f"ZIP file contains {len(file_list)} entries")
                
                if len(file_list) > 10000:  # 最大10000个文件
                    raise Exception("ZIP文件包含过多文件，超过限制10000")
                
                # 计算需要处理的文件总数（排除目录）
                total_files = len([f for f in zip_ref.infolist() if not f.is_dir()])
                logger.info(f"Total files to process (excluding directories): {total_files}")
                
                # 使用 tqdm 创建进度条
                from tqdm import tqdm 
                with tqdm(total=total_files, desc=f"Task {task_id} [EXTRACTING]", unit="files", 
                         bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                    
                    for file_info in zip_ref.infolist():
                        # 跳过目录
                        if file_info.is_dir():
                            continue
                        
                        # 更新进度条描述，显示当前处理的文件名
                        chinese_compatiable_filename = self._fix_filename_encoding(file_info.filename)
                        filename_display = str(chinese_compatiable_filename)[:40] + "..." if len(str(chinese_compatiable_filename)) > 40 else str(chinese_compatiable_filename)
                        pbar.set_description(f"Task {task_id} [EXTRACTING] - {filename_display}")
                        
                        try:
                            # 记录当前处理的文件信息
                            logger.info(f"Processing file: {chinese_compatiable_filename} (size: {file_info.file_size} bytes)")
                            
                            # 首先检查文件名是否有效
                            if file_info.filename is None:
                                logger.error("ZIP文件条目没有文件名，跳过此文件")
                                pbar.update(1)
                                continue
                            
                            if not str(file_info.filename).strip():
                                logger.error("ZIP文件条目文件名为空，跳过此文件")
                                pbar.update(1)
                                continue
                            
                            # 使用cp437->gbk编码转换解决中文文件名问题
                            try:
                                decoded_filename = self._fix_filename_encoding(file_info.filename)
                            except Exception as encoding_error:
                                logger.error(f"Failed to fix filename encoding for {file_info.filename}: {encoding_error}")
                                # 使用原始文件名作为备选
                                decoded_filename = str(file_info.filename)
                            
                            # 检查文件扩展名
                            file_ext = os.path.splitext(decoded_filename)[1].lower()
                            
                            if file_ext not in self.supported_extensions:
                                logger.warning(f"Skipping unsupported file: {decoded_filename} (extension: {file_ext})")
                                pbar.update(1)
                                continue
                            
                            # 检查文件大小
                            if file_info.file_size > 100 * 1024 * 1024:  # 100MB限制
                                logger.warning(f"Skipping large file: {decoded_filename} ({file_info.file_size} bytes)")
                                pbar.update(1)
                                continue
                            
                            if decoded_filename is None:
                                logger.error("decoded_filename is None, skipping this file")
                                pbar.update(1)
                                continue
                            
                            # 处理目录结构，保留原始路径信息
                            # 分割路径，最后一个部分是文件名，前面是目录路径
                            path_parts = decoded_filename.split('/')
                            if len(path_parts) > 1:
                                # 有目录结构
                                directory_path = '/'.join(path_parts[:-1])  # 目录部分
                                filename = path_parts[-1]  # 文件名部分
                                # 在临时目录中创建相应的子目录
                                full_dir_path = os.path.join(self.temp_dir, f"{task_id}_{directory_path}")
                                os.makedirs(full_dir_path, exist_ok=True)
                                temp_file_path = os.path.join(full_dir_path, filename)
                            else:
                                # 没有目录结构，直接使用文件名
                                filename = decoded_filename
                                temp_file_path = os.path.join(self.temp_dir, f"{task_id}_{filename}")
                            
                            try:
                                with zip_ref.open(file_info.filename) as source, open(temp_file_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                            except Exception as e:
                                logger.error(f"Failed to extract file {decoded_filename}: {e}")
                                # 创建FileExtractionFailure记录
                                failure_record = FileExtractionFailure(
                                    task_id=task_id,
                                    filename=decoded_filename,
                                    error=f"Extraction failed: {str(e)}",
                                    file_size=file_info.file_size
                                )
                                db.add(failure_record)
                                
                                failed_files.append({
                                    "filename": decoded_filename,
                                    "error": f"Extraction failed: {str(e)}",
                                    "size": file_info.file_size
                                })
                                pbar.update(1)
                                continue
                            
                            # 上传到MinIO
                            s3_key = f"tasks/{task_id}/extracted/{decoded_filename}"
                            
                            if minio_service.upload_file(temp_file_path, s3_key):
                                # 计算文件SHA256哈希值
                                import hashlib
                                sha256_hash = hashlib.sha256()
                                with open(temp_file_path, "rb") as f:
                                    for chunk in iter(lambda: f.read(4096), b""):
                                        sha256_hash.update(chunk)
                                file_sha256 = sha256_hash.hexdigest()
                                
                                # 创建FileMetadata记录
                                file_metadata = FileMetadata(
                                    task_id=task_id,
                                    s3_key=s3_key,
                                    original_filename=decoded_filename,
                                    relative_path=decoded_filename,  # 相对路径就是文件名
                                    file_type=file_ext,
                                    file_size=file_info.file_size,
                                    sha256=file_sha256
                                )
                                db.add(file_metadata)
                                
                                extracted_files.append({
                                    "filename": decoded_filename,
                                    "size": file_info.file_size,
                                    "s3_key": s3_key,
                                    "temp_path": temp_file_path,
                                    "file_metadata_id": file_metadata.id
                                })
                            else:
                                logger.error(f"Failed to upload file {decoded_filename} to MinIO")
                                # 创建FileExtractionFailure记录
                                failure_record = FileExtractionFailure(
                                    task_id=task_id,
                                    filename=decoded_filename,
                                    error="MinIO upload failed",
                                    file_size=file_info.file_size
                                )
                                db.add(failure_record)
                                
                                failed_files.append({
                                    "filename": decoded_filename,
                                    "error": "MinIO upload failed",
                                    "size": file_info.file_size
                                })
                                pbar.update(1)
                                continue
                            
                            # 清理临时文件
                            try:
                                os.remove(temp_file_path)
                            except:
                                pass
                            
                        except Exception as e:
                            # 使用已解码文件名（若已可用）以便日志与记录一致
                            preferred_filename = (
                                decoded_filename if 'decoded_filename' in locals() and decoded_filename else str(file_info.filename)
                            )
                            logger.error(f"Failed to process file {preferred_filename}: {e}")
                            logger.error(f"Error type: {type(e)}")
                            logger.error(f"Error details: {repr(e)}")
                            import traceback
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            
                            # 创建FileExtractionFailure记录
                            failure_record = FileExtractionFailure(
                                task_id=task_id,
                                filename=preferred_filename,
                                error=str(e),
                                file_size=file_info.file_size
                            )
                            db.add(failure_record)
                            
                            failed_files.append({
                                "filename": preferred_filename,
                                "error": str(e),
                                "size": file_info.file_size
                            })
                        
                        # 更新进度条，显示成功和失败统计
                        pbar.set_postfix({
                            'success': len(extracted_files),
                            'failed': len(failed_files)
                        })
                        pbar.update(1)
                    
                    # 进度条完成
                    pbar.set_description(f"Task {task_id} [EXTRACTING] - Completed")
                    pbar.set_postfix({
                        'success': len(extracted_files),
                        'failed': len(failed_files)
                    })
                
        except Exception as e:
            logger.error(f"Failed to extract ZIP file: {e}")
            raise
        
        # 记录失败文件统计
        if failed_files:
            logger.warning(f"ZIP extraction completed with {len(failed_files)} failed files")
            for failed_file in failed_files:
                logger.warning(f"Failed file: {failed_file['filename']}, Error: {failed_file['error']}")
        
        # 提交所有FileMetadata记录到数据库
        try:
            logger.info(f"Committing {len(extracted_files)} FileMetadata records to database...")
            db.commit()
            logger.info(f"Successfully committed {len(extracted_files)} FileMetadata records to database")
        except Exception as e:
            logger.error(f"Failed to commit FileMetadata records: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            db.rollback()
            logger.info("Database transaction rolled back")
            raise
        
        return {
            "files": extracted_files,
            "failed_files": failed_files
        }
    
    def _fix_filename_encoding(self, filename) -> str:
        """修复文件名编码问题 - 使用cp437->gbk转换"""
        # 检查filename是否为None或空
        if filename is None:
            logger.error("Filename is None")
            raise ValueError("Filename cannot be None")
        if not filename:
            logger.error("Filename is empty")
            raise ValueError("Filename cannot be empty")
        
        # 确保filename是字符串类型
        filename_str = str(filename)
        
        try:
            # 优先尝试cp437->gbk转换（解决中文文件名问题）
            result = filename_str.encode('cp437').decode('gbk')
            return result
        except (UnicodeEncodeError, UnicodeDecodeError) as e:
            logger.warning(f"cp437->gbk conversion failed: {e}")
            # 编码转换失败时回退到utf-8处理
            try:
                result = filename_str.encode('utf-8').decode('utf-8')
                return result
            except (UnicodeEncodeError, UnicodeDecodeError) as e2:
                # 如果utf-8也失败，记录错误并返回原始文件名
                logger.warning(f"utf-8 fallback also failed: {e2}")
                return filename_str
        except Exception as e:
            # 其他异常情况
            logger.error(f"Unexpected error fixing filename encoding for '{filename}': {e}")
            # 确保返回字符串
            return str(filename)
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除或替换不安全的字符"""
        # 确保输入是字符串
        if filename is None:
            logger.error("Input filename is None, returning default")
            return "unknown_file"
        
        filename_str = str(filename)
        if not filename_str.strip():
            logger.error("Input filename is empty, returning default")
            return "unknown_file"
        
        # 移除或替换不安全的字符
        unsafe_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        safe_filename = filename_str
        for char in unsafe_chars:
            safe_filename = safe_filename.replace(char, '_')
        
        # 限制文件名长度
        if len(safe_filename) > 200:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = name[:200-len(ext)] + ext
        
        return safe_filename
    
    def get_task_summary(self, task_id: int, db: Session) -> Dict[str, Any]:
        """获取任务摘要"""
        try:
            # 统计文件数量
            total_files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).count()
            classified_files = db.query(FileClassification).filter(FileClassification.task_id == task_id).count()
            # Note: content_reading_status is no longer in FileMetadata
            # We'll count unrecognized files based on classifications
            unrecognized_files = total_files - classified_files
            
            # 按分类统计
            category_stats = {}
            classifications = db.query(FileClassification).filter(FileClassification.task_id == task_id).all()
            for cls in classifications:
                category = cls.category
                if category not in category_stats:
                    category_stats[category] = 0
                category_stats[category] += 1
            
            return {
                "task_id": task_id,
                "total_files": total_files,
                "classified_files": classified_files,
                "unrecognized_files": unrecognized_files,
                "category_stats": category_stats,
                "progress_percentage": (classified_files / total_files * 100) if total_files > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get task summary: {e}")
            return {}

# 全局文件服务实例
file_service = FileService()
