"""
小云浮音视频处理服务 - 插件端歌曲路由

职责：
1. 接收控制端的获取歌曲请求
2. 转发给对应插件获取歌曲详情

文件位置: plugin/app/api/song.py
"""

from fastapi import APIRouter, Request

from app.core.plugin_loader import get_loader
from app.utils.logger import get_logger

logger = get_logger("api.song")
router = APIRouter(prefix="/api/v1/song", tags=["歌曲"])


@router.post("/{source}")
async def plugin_song(source: str, request: Request):
    """
    插件获取歌曲接口
    
    Args:
        source: 插件名称
        request: 请求体（包含 song_id, cookie）
    
    Returns:
        歌曲详情
    """
    body = await request.json()
    song_id = body.get("song_id", "")
    cookie = body.get("cookie", "")
    
    logger.info(f"🎵 插件获取歌曲请求: source={source}, song_id={song_id}")
    
    loader = get_loader()
    plugin = loader.get(source)
    
    if not plugin:
        return {
            "code": 404,
            "message": f"插件 {source} 不存在",
            "data": None
        }
    
    try:
        song = await plugin.get_song(song_id, cookie)
        
        if not song:
            return {
                "code": 404,
                "message": "歌曲不存在",
                "data": None
            }
        
        data = {
            "id": song.id,
            "name": song.name,
            "singer": song.singer,
            "album": song.album,
            "duration": song.duration,
            "cover_url": song.cover_url,
            "raw_url": song.raw_url,
            "lyric": song.lyric,
            "tlyric": song.tlyric,
            "klyric": song.klyric,
            "need_transcode": song.need_transcode
        }
        
        logger.info(f"✅ 获取歌曲成功: {source} - {song.name}")
        
        return {
            "code": 200,
            "message": "成功",
            "data": data
        }
        
    except Exception as e:
        logger.error(f"❌ 获取歌曲异常: {source} - {e}", exc_info=True)
        return {
            "code": 500,
            "message": f"获取歌曲失败: {str(e)[:100]}",
            "data": None
        }