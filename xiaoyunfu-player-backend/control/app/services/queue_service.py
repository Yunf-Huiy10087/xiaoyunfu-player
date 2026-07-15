"""
小云浮音视频处理服务 - 转码队列管理服务

职责：
1. 管理转码任务队列（排队、并发控制）
2. 任务状态跟踪（排队中、转码中、完成、失败）
3. 任务生命周期管理（入队、出队、取消）
4. 与 transcoder 和数据库协同工作

文件位置: control/app/services/queue_service.py
"""

import threading
import time
from typing import Dict, Optional, List, Any, Set
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings
from app.services.transcoder import transcode_to_opus
from app.utils.logger import get_logger

logger = get_logger("queue_service")

# ============================================================
# 1. 任务状态枚举
# ============================================================

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "排队中"
    PROCESSING = "转码中"
    COMPLETED = "完成"
    FAILED = "失败"
    CANCELLED = "已取消"


@dataclass
class QueueTask:
    """队列任务"""
    task_id: str                          # 任务ID（即 cache_key）
    source: str                           # 来源
    song_id: str                          # 歌曲ID
    url: str                              # 音频URL
    title: str                            # 歌曲名称
    singer: str = ""                      # 歌手
    cover_url: str = ""                   # 封面URL
    lyric: str = ""                       # 歌词
    duration: int = 0                     # 时长（秒）
    user_id: int = 0                      # 提交任务的用户ID
    status: TaskStatus = TaskStatus.PENDING  # 任务状态
    created_at: float = field(default_factory=time.time)  # 创建时间
    started_at: Optional[float] = None    # 开始转码时间
    completed_at: Optional[float] = None  # 完成时间
    error: Optional[str] = None           # 错误信息
    progress: int = 0                     # 进度（0-100）


# ============================================================
# 2. 队列管理器
# ============================================================

class QueueManager:
    """
    队列管理器（单例模式）
    
    管理所有转码任务的并发执行和状态跟踪
    """
    
    _instance: Optional['QueueManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 任务存储
        self._tasks: Dict[str, QueueTask] = {}
        self._pending_queue: List[str] = []      # 等待队列（先进先出）
        self._processing: Set[str] = set()       # 正在转码的任务ID
        
        # 并发控制
        self._max_concurrent = 2        # 最大并发数
        self._max_pending = 6           # 最大排队数
        
        # 线程安全锁
        self._task_lock = threading.Lock()
        
        # 启动清理协程（如果还没启动）
        self._cleaner_thread = None
        
        logger.info(f"✅ 队列管理器初始化完成 (最大并发: {self._max_concurrent}, 最大排队: {self._max_pending})")
    
    # ============================================================
    # 任务管理
    # ============================================================
    
    def add_task(self, task: QueueTask) -> bool:
        """
        添加任务到队列
        
        Args:
            task: 队列任务对象
        
        Returns:
            True 添加成功，False 队列已满
        """
        with self._task_lock:
            # 检查是否已存在
            if task.task_id in self._tasks:
                existing = self._tasks[task.task_id]
                if existing.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                    logger.warning(f"任务已存在: {task.task_id} (状态: {existing.status.value})")
                    return True
            
            # 检查队列是否已满
            active_count = sum(1 for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.PROCESSING))
            if active_count >= self._max_pending:
                logger.warning(f"队列已满 ({active_count}/{self._max_pending})，拒绝任务: {task.title}")
                return False
            
            # 添加到队列
            self._tasks[task.task_id] = task
            self._pending_queue.append(task.task_id)
            task.status = TaskStatus.PENDING
            
            logger.info(f"📥 任务入队: {task.title} (队列: {len(self._pending_queue)} 排队中)")
            
            # 尝试启动处理
            self._try_process()
            
            return True
    
    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[QueueTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_user_tasks(self, user_id: int) -> List[QueueTask]:
        """获取用户的所有任务"""
        return [t for t in self._tasks.values() if t.user_id == user_id]
    
    def get_active_tasks(self) -> List[QueueTask]:
        """获取活跃任务（排队中 + 转码中）"""
        return [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)]
    
    def get_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        stats = {
            "total": len(self._tasks),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        for task in self._tasks.values():
            status = task.status
            if status == TaskStatus.PENDING:
                stats["pending"] += 1
            elif status == TaskStatus.PROCESSING:
                stats["processing"] += 1
            elif status == TaskStatus.COMPLETED:
                stats["completed"] += 1
            elif status == TaskStatus.FAILED:
                stats["failed"] += 1
            elif status == TaskStatus.CANCELLED:
                stats["cancelled"] += 1
        return stats
    
    # ============================================================
    # 任务取消和删除
    # ============================================================
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            True 取消成功，False 任务不存在或已完成
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                logger.warning(f"任务已完成，无法取消: {task_id}")
                return False
            
            # 如果是排队中的任务，直接从队列移除
            if task.status == TaskStatus.PENDING:
                if task_id in self._pending_queue:
                    self._pending_queue.remove(task_id)
            
            # 如果是转码中的任务，标记取消（正在运行的进程会在下次检查时停止）
            if task.status == TaskStatus.PROCESSING:
                self._processing.discard(task_id)
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            
            logger.info(f"🗑️ 任务已取消: {task.title} ({task_id[:8]}...)")
            
            # 尝试启动下一个任务
            self._try_process()
            
            return True
    
    def remove_task(self, task_id: str) -> bool:
        """
        从队列中移除任务（物理删除）
        
        Args:
            task_id: 任务ID
        
        Returns:
            True 删除成功，False 任务不存在
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            # 从相关集合中移除
            if task.status == TaskStatus.PENDING:
                if task_id in self._pending_queue:
                    self._pending_queue.remove(task_id)
            
            if task.status == TaskStatus.PROCESSING:
                self._processing.discard(task_id)
            
            # 删除任务
            del self._tasks[task_id]
            
            logger.info(f"🗑️ 任务已删除: {task_id[:8]}...")
            
            # 尝试启动下一个任务
            self._try_process()
            
            return True
    
    # ============================================================
    # 任务处理（核心逻辑）
    # ============================================================
    
    def _try_process(self) -> None:
        """
        尝试从队列中取出任务并启动转码
        """
        with self._task_lock:
            # 检查是否达到最大并发
            if len(self._processing) >= self._max_concurrent:
                logger.debug(f"已满并发 ({len(self._processing)}/{self._max_concurrent})")
                return
            
            # 检查是否有排队任务
            if not self._pending_queue:
                logger.debug("队列为空")
                return
            
            # 取出第一个排队任务
            task_id = self._pending_queue.pop(0)
            task = self._tasks.get(task_id)
            
            if not task:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            # 检查任务状态是否正确
            if task.status != TaskStatus.PENDING:
                logger.warning(f"任务状态异常: {task_id} (期望: PENDING, 实际: {task.status})")
                return
            
            # 启动转码
            self._start_processing(task)
    
    def _start_processing(self, task: QueueTask) -> None:
        """
        启动转码（在后台线程中执行）
        
        Args:
            task: 队列任务
        """
        task.status = TaskStatus.PROCESSING
        task.started_at = time.time()
        self._processing.add(task.task_id)
        
        logger.info(f"🚀 开始转码: {task.title} (当前并发: {len(self._processing)}/{self._max_concurrent})")
        
        # 在后台线程中执行转码
        thread = threading.Thread(
            target=self._process_task,
            args=(task,),
            daemon=True
        )
        thread.start()
    
    def _process_task(self, task: QueueTask) -> None:
        """
        执行转码（在线程中运行）
        
        Args:
            task: 队列任务
        """
        try:
            # 执行转码
            result = transcode_to_opus(
                source_url=task.url,
                source=task.source,
                song_id=task.song_id,
                title=task.title,
                singer=task.singer,
                cover_url=task.cover_url,
                lyric=task.lyric,
                duration=task.duration,
                referer=f"https://www.bilibili.com/video/{task.song_id}" if task.source == "bilibili" else "",
                user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0"
            )
            
            # 转码成功
            with self._task_lock:
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                self._processing.discard(task.task_id)
            
            logger.info(f"✅ 转码完成: {task.title} ({task.duration}s)")
            
        except Exception as e:
            # 转码失败
            error_msg = str(e)[:200]
            with self._task_lock:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                task.error = error_msg
                self._processing.discard(task.task_id)
            
            logger.error(f"❌ 转码失败: {task.title} - {error_msg}")
        
        finally:
            # 无论成功还是失败，都尝试处理下一个任务
            self._try_process()
    
    # ============================================================
    # 清理和恢复
    # ============================================================
    
    def cleanup_stale_tasks(self, timeout_seconds: int = 1800) -> int:
        """
        清理超时任务（转码超过指定时间未完成）
        
        Args:
            timeout_seconds: 超时时间（秒）
        
        Returns:
            清理的任务数
        """
        now = time.time()
        cleaned = 0
        
        with self._task_lock:
            for task_id in list(self._processing):
                task = self._tasks.get(task_id)
                if not task:
                    continue
                
                if task.started_at and (now - task.started_at) > timeout_seconds:
                    # 转码超时，标记为失败
                    self._processing.discard(task_id)
                    task.status = TaskStatus.FAILED
                    task.error = "转码超时"
                    task.completed_at = now
                    cleaned += 1
                    logger.warning(f"⏰ 任务超时: {task.title} (超过 {timeout_seconds}s)")
            
            # 清理僵尸任务（状态为 PROCESSING 但不在 processing 集合中）
            for task_id, task in list(self._tasks.items()):
                if task.status == TaskStatus.PROCESSING and task_id not in self._processing:
                    task.status = TaskStatus.FAILED
                    task.error = "任务异常中断"
                    task.completed_at = now
                    cleaned += 1
                    logger.warning(f"🧟 僵尸任务恢复: {task.title}")
        
        if cleaned > 0:
            self._try_process()
        
        return cleaned
    
    def shutdown(self) -> None:
        """关闭队列管理器（等待所有任务完成）"""
        logger.info("🛑 正在关闭队列管理器...")
        
        # 检查是否有正在运行的任务
        with self._task_lock:
            processing_count = len(self._processing)
            pending_count = len(self._pending_queue)
        
        if processing_count > 0:
            logger.info(f"⏳ 等待 {processing_count} 个任务完成...")
            
            # 等待任务完成（最多等待 300 秒）
            wait_time = 0
            while wait_time < 300:
                with self._task_lock:
                    if len(self._processing) == 0:
                        break
                time.sleep(5)
                wait_time += 5
            
            # 如果仍有任务在运行，强制取消
            with self._task_lock:
                if self._processing:
                    for task_id in list(self._processing):
                        task = self._tasks.get(task_id)
                        if task:
                            task.status = TaskStatus.CANCELLED
                        self._processing.discard(task_id)
                    logger.warning(f"强制取消 {len(self._processing)} 个任务")
        
        logger.info("✅ 队列管理器已关闭")


# ============================================================
# 3. 全局单例
# ============================================================

# 获取队列管理器实例
queue_manager = QueueManager()


# ============================================================
# 4. 便捷函数
# ============================================================

def add_to_queue(
    task_id: str,
    source: str,
    song_id: str,
    url: str,
    title: str,
    singer: str = "",
    cover_url: str = "",
    lyric: str = "",
    duration: int = 0,
    user_id: int = 0
) -> bool:
    """
    添加任务到队列的便捷函数
    
    Returns:
        True 添加成功，False 队列已满
    """
    task = QueueTask(
        task_id=task_id,
        source=source,
        song_id=song_id,
        url=url,
        title=title,
        singer=singer,
        cover_url=cover_url,
        lyric=lyric,
        duration=duration,
        user_id=user_id
    )
    return queue_manager.add_task(task)


def get_queue_status() -> List[Dict[str, Any]]:
    """获取队列状态（用于前端展示）"""
    tasks = queue_manager.get_all_tasks()
    result = []
    for task in tasks:
        result.append({
            "ck": task.task_id,
            "name": task.title,
            "status": task.status.value,
            "source": task.source,
            "sid": task.song_id,
            "user_id": task.user_id,
            "singer": task.singer,
            "cover_url": task.cover_url,
            "duration": task.duration,
            "progress": task.progress,
            "error": task.error
        })
    return result


def get_queue_stats() -> Dict[str, int]:
    """获取队列统计信息"""
    return queue_manager.get_stats()