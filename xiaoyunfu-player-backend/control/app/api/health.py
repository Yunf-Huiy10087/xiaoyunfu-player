"""
小云浮音视频处理服务 - 健康检查路由

提供服务健康状态检查接口，用于容器编排系统

文件位置: control/app/api/health.py
"""

from fastapi import APIRouter
from app.core.config import settings
from app.services.transcoder import get_cache_size_mb
from app.services.queue_service import get_queue_stats
from app.utils.logger import get_logger

logger = get_logger("api.health")
router = APIRouter(tags=["系统"])


@router.get("/health")
async def health():
    """
    健康检查接口
    
    Returns:
        {
            "status": "ok",
            "port": 2587,
            "debug": false,
            "plugins": ["bilibili", "netease"],
            "queue_total": 0,
            "queue_processing": 0,
            "cache_mb": 12.34
        }
    """
    logger.debug("💓 健康检查请求")
    
    # 获取队列统计
    queue_stats = get_queue_stats()
    
    # 获取缓存大小
    cache_mb = get_cache_size_mb()
    
    return {
        "status": "ok",
        "port": settings.PORT,
        "debug": settings.DEBUG,
        "plugins": list(settings.get_all_plugin_endpoints().keys()),
        "queue_total": queue_stats.get("total", 0),
        "queue_processing": queue_stats.get("processing", 0),
        "cache_mb": round(cache_mb, 2)
    }