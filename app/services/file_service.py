import os
import zipfile
import shutil
import logging
import tempfile
import uuid
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.database import Task, FileMetadata
from app.services.minio_service import minio_service
from app.services.kafka_service import kafka_service

logger = logging.getLogger(__name__)

class FileService:
    """文件处理服务"""
    
    def __init__(self):
        # 使用系统临时目录
        self.temp_dir = None
    
    def __enter__(self):
        """进入上下文时创建临时目录"""
        self.temp_dir = tempfile.mkdtemp(prefix="legal_docs_")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"临时目录已清理: {self.temp_dir}")
            except Exception as e:
                logger.error(f"清理临时目录失败 {self.temp_dir}: {e}")
    
    def process_zip_upload(self, task_id: int, zip_file_path: str, project_name: str, organize_date: str, db: Session) -> Dict[str, Any]:
        """处理ZIP文件上传 - 只负责解压和存储原始文件"""
        try:
            logger.info(f"Processing ZIP upload for task {task_id}")
            
            # 1. 上传ZIP到MinIO
            zip_s3_key = f"tasks/{task_id}/uploads/original.zip"
            if not minio_service.upload_file(zip_file_path, zip_s3_key):
                raise Exception("Failed to upload ZIP to MinIO")
            
            # 2. 解压ZIP文件（只解压，不处理内容）
            extraction_result = self._extract_zip_only(zip_file_path, task_id, db)
            extracted_files = extraction_result.get("files", [])
            failed_files = extraction_result.get("failed_files", [])
            
            logger.info(f"Extracted {len(extracted_files)} files from ZIP, {len(failed_files)} files failed")
            
            # 3. 更新任务状态
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "extracted"  # 改为extracted状态
                db.commit()
            
            total_files = len(extracted_files) + len(failed_files)
            logger.info(f"Task {task_id}: {len(extracted_files)} files extracted, {len(failed_files)} extraction failures")
            
            return {
                "task_id": task_id,
                "total_files": total_files,
                "extracted_files": len(extracted_files),
                "extraction_failures": len(failed_files),
                "status": "extraction_completed_with_errors" if failed_files else "extraction_success"
            }
            
        except Exception as e:
            logger.error(f"Failed to process ZIP upload for task {task_id}: {e}")
            # 更新任务状态为失败
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                db.commit()
            raise
    
    def create_content_processing_task(self, task_id: int, db: Session) -> Dict[str, Any]:
        """创建内容处理任务 - 为每个文件创建独立的Kafka任务"""
        try:
            # 验证任务状态
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise Exception("Task not found")
            
            if task.status != "extracted":
                raise Exception(f"Task status must be 'extracted', current: {task.status}")
            
            # 查询该任务下的所有文件
            files = db.query(FileMetadata).filter(FileMetadata.task_id == task_id).all()
            if not files:
                raise Exception(f"No files found for task {task_id}")
            
            logger.info(f"Found {len(files)} files for task {task_id}, creating individual processing jobs")
            
            # 为每个文件创建独立的Kafka任务
            created_jobs = []
            for file_metadata in files:
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
                
                # 发布到Kafka队列
                kafka_service.publish_message("file.processing", message)
                
                created_jobs.append({
                    "job_id": job_id,
                    "file_id": file_metadata.id,
                    "filename": file_metadata.original_filename
                })
                
                logger.info(f"Created processing job {job_id} for file {file_metadata.original_filename}")
            
            # 更新任务状态
            task.status = "processing"
            db.commit()
            
            logger.info(f"Created {len(created_jobs)} content processing jobs for task {task_id}")
            
            return {
                "task_id": task_id,
                "total_jobs": len(created_jobs),
                "jobs": created_jobs,
                "status": "jobs_created",
                "message": f"Successfully created {len(created_jobs)} file processing jobs"
            }
            
        except Exception as e:
            logger.error(f"Failed to create content processing task for task {task_id}: {e}")
            raise
    
    def _extract_zip_only(self, zip_path: str, task_id: int, db: Session) -> Dict[str, Any]:
        """解压ZIP文件 - 只负责解压和存储，不处理内容"""
        extracted_files = []
        failed_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 检查文件数量限制
                if len(zip_ref.namelist()) > 10000:  # 最大10000个文件
                    raise Exception("ZIP文件包含过多文件，超过限制10000")
                
                # 计算需要处理的文件总数（排除目录）
                total_files = len([f for f in zip_ref.infolist() if not f.is_dir()])
                
                logger.info(f"Starting ZIP extraction for task {task_id}, total files to process: {total_files}")
                
                # 使用 tqdm 创建进度条
                from tqdm import tqdm # Added missing import
                with tqdm(total=total_files, desc=f"Task {task_id} [EXTRACTING]", unit="files", 
                         bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                    
                    for file_info in zip_ref.infolist():
                        # 跳过目录
                        if file_info.is_dir():
                            continue
                        
                        # 更新进度条描述，显示当前处理的文件名
                        filename_display = str(file_info.filename)[:40] + "..." if len(str(file_info.filename)) > 40 else str(file_info.filename)
                        pbar.set_description(f"Task {task_id} [EXTRACTING] - {filename_display}")
                        
                        try:
                            # 使用cp437->gbk编码转换解决中文文件名问题
                            decoded_filename = self._fix_filename_encoding(file_info.filename)
                            
                            # 检查文件扩展名
                            file_ext = os.path.splitext(decoded_filename)[1].lower()
                            if file_ext not in self.supported_extensions:
                                logger.warning(f"Skipping unsupported file: {decoded_filename}")
                                pbar.update(1)
                                continue
                            
                            # 检查文件大小
                            if file_info.file_size > 100 * 1024 * 1024:  # 100MB限制
                                logger.warning(f"Skipping large file: {decoded_filename} ({file_info.file_size} bytes)")
                                pbar.update(1)
                                continue
                            
                            # 解压文件到临时目录，使用安全的文件名
                            safe_filename = self._sanitize_filename(decoded_filename)
                            temp_file_path = os.path.join(self.temp_dir, f"{task_id}_{safe_filename}")
                            
                            try:
                                with zip_ref.open(file_info.filename) as source, open(temp_file_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                            except Exception as e:
                                logger.error(f"Failed to extract file {decoded_filename}: {e}")
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
                                    sha256=file_sha256,
                                    content_reading_status="pending"
                                )
                                db.add(file_metadata)
                                
                                extracted_files.append({
                                    "filename": decoded_filename,
                                    "size": file_info.file_size,
                                    "s3_key": s3_key,
                                    "temp_path": temp_file_path,
                                    "file_metadata_id": file_metadata.id
                                })
                                
                                logger.info(f"Created FileMetadata record for file {decoded_filename} (ID: {file_metadata.id})")
                            else:
                                logger.error(f"Failed to upload file {decoded_filename} to MinIO")
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
                            logger.error(f"Failed to process file {file_info.filename}: {e}")
                            failed_files.append({
                                "filename": str(file_info.filename),
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
            db.commit()
            logger.info(f"Successfully committed {len(extracted_files)} FileMetadata records to database")
        except Exception as e:
            logger.error(f"Failed to commit FileMetadata records: {e}")
            db.rollback()
            raise
        
        return {
            "files": extracted_files,
            "failed_files": failed_files
        }
    
    def _fix_filename_encoding(self, filename) -> str:
        """修复文件名编码问题 - 使用cp437->gbk转换"""
        try:
            # 优先尝试cp437->gbk转换（解决中文文件名问题）
            return filename.encode('cp437').decode('gbk')
        except:
            # 失败时回退到utf-8处理
            return filename.encode('utf-8').decode('utf-8')
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除或替换不安全的字符"""
        # 移除或替换不安全的字符
        unsafe_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        safe_filename = filename
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
            unrecognized_files = db.query(FileMetadata).filter(
                FileMetadata.task_id == task_id,
                FileMetadata.content_reading_status == "failed"
            ).count()
            
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
