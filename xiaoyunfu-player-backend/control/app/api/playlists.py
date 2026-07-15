"""
小云浮音视频处理服务 - 歌单路由

职责：
1. 创建/删除歌单
2. 获取歌单列表
3. 获取歌单详情（含歌曲列表）
4. 添加/移除歌曲
5. 调整歌曲顺序

文件位置: control/app/api/playlists.py
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from app.core.database import execute_query, execute_one, execute_insert, execute_update
from app.models.request import CreatePlaylistRequest, AddSongRequest
from app.models.response import success, error
from app.api.auth import get_current_user
from app.utils.logger import get_logger

logger = get_logger("api.playlists")
router = APIRouter(prefix="/api/v1/playlists", tags=["歌单"])


# ============================================================
# 1. 获取歌单列表
# ============================================================

@router.get("/")
async def list_playlists(user: dict = Depends(get_current_user)):
    """
    获取歌单列表（用户自己的 + 公开的）
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": [
                {
                    "id": 1,
                    "name": "我的歌单",
                    "user_id": 1,
                    "is_public": true,
                    "description": "描述",
                    "cover_url": "https://...",
                    "created_at": "2024-01-01 00:00:00",
                    "song_count": 10
                }
            ]
        }
    """
    logger.debug(f"📋 获取歌单列表: user={user['username']}")
    
    # 查询歌单（用户自己的 + 公开的）
    rows = execute_query(
        """
        SELECT 
            p.*,
            (SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = p.id) as song_count
        FROM playlists p
        WHERE p.user_id = ? OR p.is_public = 1
        ORDER BY p.created_at DESC
        """,
        (user["id"],)
    )
    
    return success(data=rows)


# ============================================================
# 2. 创建歌单
# ============================================================

@router.post("/")
async def create_playlist(
    request: CreatePlaylistRequest,
    user: dict = Depends(get_current_user)
):
    """
    创建歌单
    
    Args:
        request: 创建歌单请求（名称 + 是否公开 + 描述）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "创建成功",
            "data": {
                "id": 1
            }
        }
    """
    logger.info(f"📝 创建歌单: {request.name}, user={user['username']}")
    
    playlist_id = execute_insert(
        """
        INSERT INTO playlists (user_id, name, is_public, description)
        VALUES (?, ?, ?, ?)
        """,
        (user["id"], request.name, 1 if request.is_public else 0, request.description)
    )
    
    logger.info(f"✅ 歌单创建成功: ID={playlist_id}")
    
    return success(data={"id": playlist_id}, message="创建成功")


# ============================================================
# 3. 删除歌单
# ============================================================

@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: int,
    user: dict = Depends(get_current_user)
):
    """
    删除歌单（只能删除自己的）
    
    Args:
        playlist_id: 歌单ID
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "已删除"
        }
    """
    logger.info(f"🗑️ 删除歌单: ID={playlist_id}, user={user['username']}")
    
    # 检查歌单是否存在且属于当前用户
    playlist = execute_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user["id"])
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="歌单不存在或无权限～～(′Д`)")
    
    # 删除歌单（级联删除歌曲）
    execute_update("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    
    logger.info(f"✅ 歌单删除成功: ID={playlist_id}")
    
    return success(message="已删除")


# ============================================================
# 4. 获取歌单详情（含歌曲列表）
# ============================================================

@router.get("/{playlist_id}")
async def get_playlist_detail(
    playlist_id: int,
    user: dict = Depends(get_current_user)
):
    """
    获取歌单详情（包含歌曲列表）
    
    Args:
        playlist_id: 歌单ID
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": {
                "id": 1,
                "name": "我的歌单",
                "user_id": 1,
                "is_public": true,
                "description": "描述",
                "cover_url": "https://...",
                "created_at": "2024-01-01 00:00:00",
                "songs": [
                    {
                        "id": 1,
                        "song_id": "BV1xxx",
                        "source": "bilibili",
                        "title": "歌曲名称",
                        "artist": "歌手",
                        "album": "专辑",
                        "cover_url": "https://...",
                        "duration": 180,
                        "position": 0
                    }
                ]
            }
        }
    """
    logger.debug(f"📋 获取歌单详情: ID={playlist_id}, user={user['username']}")
    
    # 获取歌单基本信息
    playlist = execute_one(
        """
        SELECT * FROM playlists 
        WHERE id = ? AND (user_id = ? OR is_public = 1)
        """,
        (playlist_id, user["id"])
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="歌单不存在或无权限～～(′Д`)")
    
    # 获取歌曲列表
    songs = execute_query(
        """
        SELECT * FROM playlist_songs 
        WHERE playlist_id = ? 
        ORDER BY position ASC, created_at ASC
        """,
        (playlist_id,)
    )
    
    playlist["songs"] = songs
    playlist["song_count"] = len(songs)
    
    return success(data=playlist)


# ============================================================
# 5. 添加歌曲到歌单
# ============================================================

@router.post("/{playlist_id}/songs")
async def add_song_to_playlist(
    playlist_id: int,
    request: AddSongRequest,
    user: dict = Depends(get_current_user)
):
    """
    添加歌曲到歌单
    
    Args:
        playlist_id: 歌单ID
        request: 添加歌曲请求（歌曲信息）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "已添加"
        }
    """
    logger.info(f"📝 添加歌曲到歌单: playlist_id={playlist_id}, title={request.title}, user={user['username']}")
    
    # 检查歌单是否存在且属于当前用户
    playlist = execute_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user["id"])
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="歌单不存在或无权限～～(′Д`)")
    
    # 获取当前最大位置
    max_pos = execute_one(
        "SELECT MAX(position) as max_pos FROM playlist_songs WHERE playlist_id = ?",
        (playlist_id,)
    )
    next_pos = (max_pos.get("max_pos") or -1) + 1
    
    # 添加歌曲
    execute_insert(
        """
        INSERT INTO playlist_songs 
        (playlist_id, song_id, source, title, artist, album, cover_url, duration, added_by, position)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            playlist_id,
            request.song_id,
            request.source,
            request.title,
            request.artist,
            request.album,
            request.cover_url,
            request.duration,
            user["id"],
            next_pos
        )
    )
    
    logger.info(f"✅ 歌曲已添加到歌单: {request.title}")
    
    return success(message="已添加")


# ============================================================
# 6. 从歌单移除歌曲
# ============================================================

@router.delete("/{playlist_id}/songs/{song_id}")
async def remove_song_from_playlist(
    playlist_id: int,
    song_id: int,
    user: dict = Depends(get_current_user)
):
    """
    从歌单移除歌曲（只能删除自己的歌单中的歌曲）
    
    Args:
        playlist_id: 歌单ID
        song_id: 歌曲记录ID（playlist_songs 表中的 id）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "已移除"
        }
    """
    logger.info(f"🗑️ 从歌单移除歌曲: playlist_id={playlist_id}, song_id={song_id}, user={user['username']}")
    
    # 检查歌单是否存在且属于当前用户
    playlist = execute_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user["id"])
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="歌单不存在或无权限～～(′Д`)")
    
    # 删除歌曲
    affected = execute_update(
        "DELETE FROM playlist_songs WHERE id = ? AND playlist_id = ?",
        (song_id, playlist_id)
    )
    if affected == 0:
        raise HTTPException(status_code=404, detail="歌曲不存在～～(′Д`)")
    
    logger.info(f"✅ 歌曲已从歌单移除: ID={song_id}")
    
    return success(message="已移除")


# ============================================================
# 7. 调整歌曲顺序
# ============================================================

@router.put("/{playlist_id}/songs/reorder")
async def reorder_songs(
    playlist_id: int,
    song_ids: List[int],
    user: dict = Depends(get_current_user)
):
    """
    调整歌曲顺序
    
    Args:
        playlist_id: 歌单ID
        song_ids: 歌曲ID列表（按新顺序排列）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "顺序已调整"
        }
    """
    logger.info(f"🔄 调整歌曲顺序: playlist_id={playlist_id}, count={len(song_ids)}, user={user['username']}")
    
    # 检查歌单是否存在且属于当前用户
    playlist = execute_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user["id"])
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="歌单不存在或无权限～～(′Д`)")
    
    # 更新每个歌曲的位置
    for position, song_id in enumerate(song_ids):
        execute_update(
            "UPDATE playlist_songs SET position = ? WHERE id = ? AND playlist_id = ?",
            (position, song_id, playlist_id)
        )
    
    logger.info(f"✅ 歌曲顺序已调整: playlist_id={playlist_id}")
    
    return success(message="顺序已调整")