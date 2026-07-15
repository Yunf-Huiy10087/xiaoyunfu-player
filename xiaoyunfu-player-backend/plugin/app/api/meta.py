"""
小云浮音视频处理服务 - 插件元数据路由

职责：
1. 返回插件自身的元数据（供控制端调用）
2. 声明插件支持的登录方式、搜索能力等

文件位置: plugin/app/api/meta.py
"""

from fastapi import APIRouter

from app.core.plugin_loader import get_loader
from app.utils.logger import get_logger

logger = get_logger("api.meta")
router = APIRouter(prefix="/api/v1/meta", tags=["元数据"])


@router.get("/")
async def get_meta():
    """
    获取插件元数据
    
    控制端启动时会调用此接口，获取插件的能力声明
    """
    loader = get_loader()
    all_meta = loader.get_all_meta()
    
    logger.debug(f"📋 返回元数据: {len(all_meta)} 个插件")
    
    return {
        "code": 200,
        "message": "成功",
        "data": all_meta
    }


@router.get("/{source}")
async def get_plugin_meta(source: str):
    """
    获取单个插件的元数据
    
    Args:
        source: 插件名称（如 bilibili）
    """
    loader = get_loader()
    meta = loader.get_plugin_meta(source)
    
    if not meta:
        return {
            "code": 404,
            "message": f"插件 {source} 不存在",
            "data": None
        }
    
    return {
        "code": 200,
        "message": "成功",
        "data": meta
    }