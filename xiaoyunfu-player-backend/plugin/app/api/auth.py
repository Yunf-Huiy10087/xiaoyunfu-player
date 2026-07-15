"""
小云浮音视频处理服务 - 插件端认证路由

职责：
1. 处理用户登录请求（转发给对应插件）
2. 支持多种登录方式（密码、二维码、短信、手动Cookie）

文件位置: plugin/app/api/auth.py
"""

from fastapi import APIRouter, Request, HTTPException

from app.core.plugin_loader import get_loader
from app.utils.logger import get_logger

logger = get_logger("api.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/{source}")
async def plugin_auth(source: str, request: Request):
    """
    插件认证接口
    
    控制端转发用户的登录请求到此接口
    
    Args:
        source: 插件名称（如 bilibili）
        request: 请求体
    
    Returns:
        认证结果
    """
    # 获取请求体
    body = await request.json()
    method = body.get("method")
    data = body.get("data", {})
    
    logger.info(f"🔐 插件认证请求: source={source}, method={method}")
    
    # 获取插件
    loader = get_loader()
    plugin = loader.get(source)
    
    if not plugin:
        logger.warning(f"⚠️ 插件不存在: {source}")
        return {
            "success": False,
            "error": f"插件 {source} 不存在"
        }
    
    # 检查插件是否支持该认证方式
    auth_methods = getattr(plugin, 'auth_methods', [])
    supported = [m.get("id") for m in auth_methods]
    
    if method not in supported:
        logger.warning(f"⚠️ 不支持的认证方式: {source} - {method}")
        return {
            "success": False,
            "error": f"不支持的认证方式: {method}"
        }
    
    try:
        # 调用插件的 auth 方法
        result = await plugin.auth(method, data)
        
        if result.get("success"):
            logger.info(f"✅ 认证成功: {source}")
        else:
            logger.warning(f"⚠️ 认证失败: {source} - {result.get('error', '未知错误')}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 认证异常: {source} - {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)[:200]
        }