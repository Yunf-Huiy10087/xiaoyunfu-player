"""
小云浮音视频处理服务 - 缓存管理服务

职责：
1. 后台定期清理过期缓存
2. 按容量限制清理缓存
3. 手动清理指定缓存
4. 缓存统计信息

文件位置: control/app/services/cache_service.py
"""

import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

from app.core.config import settings
from app.services.transcoder import (
    get_cache_size_mb,
    clear_cache,
    clean_expired_cache,
    clean_by_size,
    is_cached,
    get_metadata
)
from app.utils.logger import get_logger

logger = get_logger("cache_service")


# ============================================================
# 1. 缓存清理器（后台线程）
# ============================================================

class CacheCleaner:
    """
    缓存清理器（单例模式）
    
    在后台定期运行，清理过期缓存和超出容量限制的缓存
    """
    
    _instance: Optional['CacheCleaner'] = None
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
        
        # 清理配置（从 settings 读取）
        self.expire_seconds = getattr(settings, 'CACHE_EXPIRE_SECONDS', 7200)  # 默认2小时
        self.max_size_mb = getattr(settings, 'MAX_CACHE_SIZE_MB', 2048)        # 默认2GB
        self.cleanup_interval = getattr(settings, 'CACHE_CLEANUP_INTERVAL', 1800)  # 默认30分钟
        
        # 运行状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        logger.info(f"🧹 缓存清理器初始化 (过期: {self.expire_seconds}s, 最大: {self.max_size_mb}MB, 间隔: {self.cleanup_interval}s)")
    
    def start(self) -> None:
        """
        启动后台清理线程
        """
        if self._running:
            logger.warning("缓存清理器已在运行")
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(
            target=self._clean_loop,
            name="CacheCleaner",
            daemon=True
        )
        self._thread.start()
        
        logger.info("🧹 缓存清理器已启动")
    
    def stop(self) -> None:
        """
        停止后台清理线程
        """
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=10)
        
        logger.info("🧹 缓存清理器已停止")
    
    def _clean_loop(self) -> None:
        """
        清理循环（在后台线程中运行）
        """
        while not self._stop_event.is_set():
            try:
                # 等待指定间隔
                if self._stop_event.wait(self.cleanup_interval):
                    break
                
                # 执行清理
                self._do_cleanup()
                
            except Exception as e:
                logger.error(f"❌ 清理循环异常: {e}", exc_info=True)
                # 继续运行，不退出
    
    def _do_cleanup(self) -> None:
        """
        执行一次完整的清理（过期 + 容量）
        """
        logger.debug("🧹 开始清理缓存...")
        start_time = time.time()
        
        # 1. 清理过期缓存
        expired_count = clean_expired_cache(self.expire_seconds)
        if expired_count > 0:
            logger.info(f"🧹 已删除 {expired_count} 个过期缓存")
        
        # 2. 检查容量并清理
        current_size_mb = get_cache_size_mb()
        if current_size_mb > self.max_size_mb:
            logger.info(f"🧹 缓存大小 {current_size_mb:.2f}MB 超过限制 {self.max_size_mb}MB，开始清理...")
            removed_count = clean_by_size(self.max_size_mb)
            if removed_count > 0:
                new_size = get_cache_size_mb()
                logger.info(f"🧹 已删除 {removed_count} 个缓存，释放 {current_size_mb - new_size:.2f}MB (当前: {new_size:.2f}MB)")
        
        elapsed = time.time() - start_time
        if elapsed > 1.0:
            logger.debug(f"🧹 清理完成 (耗时: {elapsed:.2f}s)")
    
    def run_cleanup_now(self) -> Dict[str, Any]:
        """
        立即执行一次清理（手动触发）
        
        Returns:
            清理结果统计
        """
        logger.info("🧹 手动触发缓存清理...")
        start_time = time.time()
        
        expired_count = clean_expired_cache(self.expire_seconds)
        current_size = get_cache_size_mb()
        removed_count = 0
        
        if current_size > self.max_size_mb:
            removed_count = clean_by_size(self.max_size_mb)
        
        new_size = get_cache_size_mb()
        elapsed = time.time() - start_time
        
        result = {
            "expired_count": expired_count,
            "removed_count": removed_count,
            "size_before_mb": round(current_size, 2),
            "size_after_mb": round(new_size, 2),
            "freed_mb": round(current_size - new_size, 2),
            "elapsed_seconds": round(elapsed, 2)
        }
        
        logger.info(f"🧹 清理完成: 过期 {expired_count} 个，容量清理 {removed_count} 个，释放 {result['freed_mb']:.2f}MB")
        return result


# ============================================================
# 2. 缓存管理便捷函数
# ============================================================

def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息
    
    Returns:
        统计信息字典
    """
    cache_dir = Path(settings.CACHE_DIR)
    
    # 统计缓存项数量
    total_items = 0
    total_files = 0
    total_bytes = 0
    
    if cache_dir.exists():
        for item in cache_dir.iterdir():
            if item.is_dir():
                # 检查是否有 opus 文件
                audio_file = item / f"{item.name}.opus"
                if audio_file.exists():
                    total_items += 1
                    total_bytes += audio_file.stat().st_size
                    # 统计其他文件
                    for f in item.glob("*"):
                        if f.is_file():
                            total_files += 1
    
    total_mb = total_bytes / (1024 * 1024)
    
    return {
        "total_items": total_items,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_mb": round(total_mb, 2),
        "max_size_mb": getattr(settings, 'MAX_CACHE_SIZE_MB', 2048),
        "cache_dir": str(cache_dir)
    }


def clean_cache_by_key(cache_key: str) -> bool:
    """
    手动清理指定缓存
    
    Args:
        cache_key: 缓存键
    
    Returns:
        True 清理成功，False 不存在
    """
    if not is_cached(cache_key):
        logger.warning(f"缓存不存在: {cache_key[:8]}...")
        return False
    
    count = clear_cache(cache_key)
    if count > 0:
        logger.info(f"🧹 已清理缓存: {cache_key[:8]}...")
        return True
    return False


def clean_all_cache() -> int:
    """
    清理所有缓存（危险操作）
    
    Returns:
        清理的缓存数量
    """
    logger.warning("⚠️ 清理所有缓存...")
    count = clear_cache()
    logger.info(f"🧹 已清理全部缓存: {count} 个")
    return count


# ============================================================
# 3. 全局单例
# ============================================================

cache_cleaner = CacheCleaner()


# ============================================================
# 4. 自动启动（在导入时启动清理器）
# ============================================================

# 启动缓存清理器（默认启用）
def init_cache_service():
    """初始化缓存服务"""
    cache_cleaner.start()
    logger.info("✅ 缓存服务初始化完成")


# 是否自动启动（可通过环境变量控制）
AUTO_START = True  # 默认自动启动

if AUTO_START:
    init_cache_service()