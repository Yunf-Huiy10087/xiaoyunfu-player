"""
小云浮音视频处理服务 - 根路径路由

提供服务基本信息

文件位置: control/app/api/root.py
"""

from fastapi import APIRouter
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("api.root")
router = APIRouter(tags=["系统"])


@router.get("/")
async def root():
    """
    根路径 - 返回服务基本信息
    
    Returns:
        {
            "service": "小云浮音视频处理服务 - 控制端",
            "version": "5.0.0",
            "status": "running",
            "port": 2587,
            "debug": false
        }
    """
    logger.debug("📋 根路径请求")
    
    return {
        "service": "小云浮音视频处理服务 - 控制端",
        "version": "5.0.0",
        "status": "running",
        "port": settings.PORT,
        "debug": settings.DEBUG
    }