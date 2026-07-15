"""
小云浮音视频处理服务 - 插件端搜索路由

职责：
1. 接收控制端的搜索请求
2. 转发给对应插件执行搜索

文件位置: plugin/app/api/search.py
"""

from fastapi import APIRouter, Request

from app.core.plugin_loader import get_loader
from app.utils.logger import get_logger

logger = get_logger("api.search")
router = APIRouter(prefix="/api/v1/search", tags=["搜索"])


@router.post("/{source}")
async def plugin_search(source: str, request: Request):
    """
    插件搜索接口
    
    Args:
        source: 插件名称
        request: 请求体（包含 keyword, limit, cookie）
    
    Returns:
        搜索结果
    """
    body = await request.json()
    keyword = body.get("keyword", "")
    limit = body.get("limit", 20)
    cookie = body.get("cookie", "")
    
    logger.info(f"🔍 插件搜索请求: source={source}, keyword={keyword}")
    
    # 获取插件
    loader = get_loader()
    plugin = loader.get(source)
    
    if not plugin:
        return {
            "code": 404,
            "message": f"插件 {source} 不存在",
            "data": []
        }
    
    try:
        results = await plugin.search(keyword, limit, cookie)
        
        # 转换结果为字典列表
        data = []
        for r in results:
            data.append({
                "id": r.id,
                "name": r.name,
                "singer": r.singer,
                "album": r.album,
                "duration": r.duration,
                "cover_url": r.cover_url
            })
        
        logger.info(f"✅ 搜索完成: {source} - {len(data)} 条结果")
        
        return {
            "code": 200,
            "message": "成功",
            "data": data
        }
        
    except Exception as e:
        logger.error(f"❌ 搜索异常: {source} - {e}", exc_info=True)
        return {
            "code": 500,
            "message": f"搜索失败: {str(e)[:100]}",
            "data": []
        }