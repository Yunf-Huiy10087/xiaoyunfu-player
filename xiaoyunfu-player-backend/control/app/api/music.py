"""
小云浮音视频处理服务 - 音乐路由

职责：
1. 搜索音乐（调用插件端）
2. 播放音乐（缓存检查 + 转码调度）
3. 获取歌词

文件位置: control/app/api/music.py
"""

import os
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from app.core.config import settings
from app.core.database import get_account
from app.models.request import SearchRequest, PlayRequest
from app.models.response import success, error, SongResponse, PlayResponseData
from app.services.transcoder import (
    get_cache_key,
    is_cached,
    get_metadata,
    transcode_to_opus
)
from app.services.queue_service import add_to_queue, get_queue_status
from app.services.plugin_client import plugin_client
from app.api.auth import get_current_user
from app.utils.logger import get_logger

logger = get_logger("api.music")
router = APIRouter(prefix="/api/v1/music", tags=["音乐"])


# ============================================================
# 1. 辅助函数
# ============================================================

def get_audio_duration(filepath: str) -> int:
    """
    获取音频文件时长（秒）
    
    Args:
        filepath: 文件路径
    
    Returns:
        时长（秒），如果获取失败返回 0
    """
    try:
        import subprocess
        import json
        
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return 0
        data = json.loads(result.stdout)
        return int(float(data["format"]["duration"]))
    except Exception as e:
        logger.debug(f"获取音频时长失败: {e}")
        return 0


# ============================================================
# 2. 搜索
# ============================================================

@router.post("/search")
async def search(
    request: SearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    搜索音乐
    
    Args:
        request: 搜索请求（关键词 + 来源 + 数量）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": [
                {
                    "id": "song_id",
                    "name": "歌曲名称",
                    "singer": "歌手",
                    "album": "专辑",
                    "duration": 180,
                    "source": "bilibili",
                    "cover_url": "https://..."
                }
            ]
        }
    """
    keyword = request.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="请输入关键词～～(′Д`)")
    
    logger.info(f"🔍 搜索请求: keyword={keyword}, source={request.source}, user={user['username']}")
    
    # 处理来源
    sources = []
    if request.source == "all":
        # 获取所有已配置的插件
        sources = list(settings.get_all_plugin_endpoints().keys())
        # 加上本地音乐
        sources.append("local")
    elif request.source == "local":
        sources = ["local"]
    else:
        sources = [request.source]
    
    results = []
    
    for source in sources:
        if source == "local":
            # 本地音乐搜索
            upload_dir = Path(settings.UPLOAD_DIR)
            if upload_dir.exists():
                for f in upload_dir.iterdir():
                    if f.is_file() and not f.name.startswith("tmp_"):
                        if keyword.lower() in f.name.lower():
                            duration = get_audio_duration(str(f))
                            results.append({
                                "id": f.name,
                                "name": f.stem,
                                "singer": "本地音乐",
                                "album": "",
                                "duration": duration,
                                "source": "local",
                                "cover_url": ""
                            })
            continue
        
        # 插件搜索
        try:
            items = await plugin_client.search(
                source=source,
                keyword=keyword,
                limit=request.limit,
                user_id=user["id"]
            )
            if items:
                for item in items:
                    item["source"] = source
                results.extend(items)
                logger.debug(f"✅ {source} 返回 {len(items)} 条结果")
        except Exception as e:
            logger.error(f"❌ 搜索 {source} 失败: {e}")
            continue
    
    # 去重（按 id + source 去重）
    seen = set()
    unique_results = []
    for item in results:
        key = f"{item.get('id')}_{item.get('source')}"
        if key not in seen:
            seen.add(key)
            unique_results.append(item)
    
    logger.info(f"✅ 搜索完成: 共 {len(unique_results)} 条结果")
    
    return success(data=unique_results)


# ============================================================
# 3. 播放
# ============================================================

@router.post("/play")
async def play(
    request: PlayRequest,
    user: dict = Depends(get_current_user)
):
    """
    播放音乐
    
    流程：
    1. 如果是本地文件，直接返回文件路径
    2. 如果是插件歌曲，检查缓存
    3. 缓存命中 → 直接返回音频URL
    4. 缓存未命中 → 判断时长
       - 短歌 (< 32分钟) → 同步转码
       - 长歌 (>= 32分钟) → 加入后台队列
    
    Args:
        request: 播放请求（歌曲ID + 来源）
        user: 当前登录用户
    
    Returns:
        播放响应（包含音频URL或队列状态）
    """
    logger.info(f"▶️ 播放请求: id={request.id}, source={request.source}, user={user['username']}")
    
    # ============================================================
    # 情况1: 本地文件
    # ============================================================
    if request.source == "local":
        decoded_id = urllib.parse.unquote(request.id)
        fpath = Path(settings.UPLOAD_DIR) / os.path.basename(decoded_id)
        
        if not fpath.exists():
            raise HTTPException(status_code=404, detail="文件不存在～～(′Д`)")
        
        duration = get_audio_duration(str(fpath))
        
        return success(data={
            "id": request.id,
            "name": fpath.stem,
            "singer": "本地音乐",
            "cover_url": "",
            "duration": duration,
            "url": f"/api/uploads/{request.id}",
            "lyric": "本地音乐，暂无歌词",
            "tlyric": "",
            "queued": False
        })
    
    # ============================================================
    # 情况2: 插件歌曲
    # ============================================================
    source = request.source
    song_id = request.id
    
    # 检查插件是否存在
    if source not in settings.get_all_plugin_endpoints():
        raise HTTPException(status_code=400, detail=f"不支持的来源: {source}～～(′Д`)")
    
    # 获取歌曲信息
    song_info = await plugin_client.get_song(
        source=source,
        song_id=song_id,
        user_id=user["id"]
    )
    
    if not song_info:
        raise HTTPException(status_code=404, detail="未找到歌曲～～(′Д`)")
    
    # 生成缓存键
    cache_key = get_cache_key(source, song_id)
    
    # 检查队列状态
    queue_tasks = get_queue_status()
    existing = next((t for t in queue_tasks if t.get("ck") == cache_key), None)
    
    if existing:
        status = existing.get("status")
        if status in ("排队中", "转码中"):
            logger.info(f"⏳ 任务已在队列中: {cache_key[:8]}... ({status})")
            return success(data={
                "id": song_id,
                "name": song_info.get("name", ""),
                "singer": song_info.get("singer", ""),
                "cover_url": song_info.get("cover_url", ""),
                "duration": song_info.get("duration", 0),
                "url": "",
                "lyric": song_info.get("lyric", ""),
                "tlyric": song_info.get("tlyric", ""),
                "queued": True,
                "status": status,
                "message": f"该任务已在队列中处理～～～o(≧口≦)o"
            })
    
    # 检查缓存
    if is_cached(cache_key):
        logger.info(f"💾 缓存命中: {cache_key[:8]}...")
        
        metadata = get_metadata(cache_key) or {}
        
        # 构建播放URL
        audio_url = f"/api/download/{cache_key}"
        
        return success(data={
            "id": song_id,
            "name": metadata.get("title", song_info.get("name", "")),
            "singer": metadata.get("singer", song_info.get("singer", "")),
            "cover_url": metadata.get("cover_url", song_info.get("cover_url", "")),
            "duration": metadata.get("duration", song_info.get("duration", 0)),
            "url": audio_url,
            "lyric": song_info.get("lyric", "纯音乐"),
            "tlyric": song_info.get("tlyric", ""),
            "queued": False
        })
    
    # ============================================================
    # 缓存未命中：需要转码
    # ============================================================
    duration = song_info.get("duration", 0)
    raw_url = song_info.get("raw_url", "")
    
    if not raw_url:
        raise HTTPException(status_code=404, detail="无法获取音频链接～～(′Д`)")
    
    # 判断时长：1920秒 = 32分钟
    if duration < 1920:
        # 短歌：同步转码
        logger.info(f"🔄 短歌同步转码: {song_info.get('name')} ({duration}s)")
        
        try:
            cache_key = await transcode_to_opus(
                source_url=raw_url,
                source=source,
                song_id=song_id,
                title=song_info.get("name", ""),
                singer=song_info.get("singer", ""),
                cover_url=song_info.get("cover_url", ""),
                lyric=song_info.get("lyric", ""),
                duration=duration,
                referer=f"https://www.bilibili.com/video/{song_id}" if source == "bilibili" else "",
                user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0"
            )
            
            audio_url = f"/api/download/{cache_key}"
            
            logger.info(f"✅ 同步转码完成: {song_info.get('name')}")
            
            return success(data={
                "id": song_id,
                "name": song_info.get("name", ""),
                "singer": song_info.get("singer", ""),
                "cover_url": song_info.get("cover_url", ""),
                "duration": duration,
                "url": audio_url,
                "lyric": song_info.get("lyric", "纯音乐"),
                "tlyric": song_info.get("tlyric", ""),
                "queued": False
            })
            
        except Exception as e:
            logger.error(f"❌ 同步转码失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="转码失败～～(′Д`)")
    
    else:
        # 长歌：加入后台队列
        logger.info(f"⏳ 长歌入队: {song_info.get('name')} ({duration}s)")
        
        success_queue = add_to_queue(
            task_id=cache_key,
            source=source,
            song_id=song_id,
            url=raw_url,
            title=song_info.get("name", ""),
            singer=song_info.get("singer", ""),
            cover_url=song_info.get("cover_url", ""),
            lyric=song_info.get("lyric", ""),
            duration=duration,
            user_id=user["id"]
        )
        
        if success_queue:
            return success(data={
                "id": song_id,
                "name": song_info.get("name", ""),
                "singer": song_info.get("singer", ""),
                "cover_url": song_info.get("cover_url", ""),
                "duration": duration,
                "url": "",
                "lyric": song_info.get("lyric", ""),
                "tlyric": song_info.get("tlyric", ""),
                "queued": True,
                "status": "排队中",
                "message": "已加入后台处理队列～～～o(≧口≦)o"
            })
        else:
            raise HTTPException(status_code=400, detail="已超出处理队列，请稍候再试～～(′Д`)")


# ============================================================
# 4. 获取歌词
# ============================================================

@router.post("/lyric")
async def get_lyric(
    request: PlayRequest,
    user: dict = Depends(get_current_user)
):
    """
    获取歌词
    
    Args:
        request: 请求（歌曲ID + 来源）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": {
                "lyric": "LRC格式歌词",
                "tlyric": "翻译歌词",
                "klyric": "罗马音歌词"
            }
        }
    """
    logger.info(f"📝 获取歌词请求: id={request.id}, source={request.source}, user={user['username']}")
    
    # 本地文件不返回歌词
    if request.source == "local":
        return success(data={
            "lyric": "本地音乐，暂无歌词",
            "tlyric": "",
            "klyric": ""
        })
    
    # 检查插件是否存在
    if request.source not in settings.get_all_plugin_endpoints():
        raise HTTPException(status_code=400, detail=f"不支持的来源: {request.source}～～(′Д`)")
    
    try:
        lyric_data = await plugin_client.get_lyric(
            source=request.source,
            song_id=request.id,
            user_id=user["id"]
        )
        
        return success(data=lyric_data)
        
    except Exception as e:
        logger.error(f"❌ 获取歌词失败: {e}", exc_info=True)
        return success(data={
            "lyric": "纯音乐",
            "tlyric": "",
            "klyric": ""
        })