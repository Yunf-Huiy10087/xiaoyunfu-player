"""
小云浮音视频处理服务 - 队列管理路由

职责：
1. 获取队列状态列表
2. 获取队列统计信息
3. 取消任务
4. 删除任务（物理删除）

文件位置: control/app/api/queue.py
"""

from fastapi import APIRouter, HTTPException, Depends

from app.services.queue_service import (
    queue_manager,
    get_queue_status,
    get_queue_stats
)
from app.services.transcoder import clear_cache
from app.api.auth import get_current_user
from app.utils.logger import get_logger

logger = get_logger("api.queue")
router = APIRouter(prefix="/api/v1/queue", tags=["队列"])


# ============================================================
# 1. 获取队列状态列表
# ============================================================

@router.get("/")
async def get_queue(user: dict = Depends(get_current_user)):
    """
    获取队列状态列表
    
    普通用户只能看到自己的任务，管理员可以看到所有任务
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": [
                {
                    "ck": "cache_key",
                    "name": "歌曲名称",
                    "status": "排队中/转码中/完成/失败/已取消",
                    "source": "bilibili",
                    "sid": "song_id",
                    "user_id": 1,
                    "singer": "歌手",
                    "cover_url": "https://...",
                    "duration": 180,
                    "progress": 0,
                    "error": null
                }
            ]
        }
    """
    logger.debug(f"📋 获取队列状态: user={user['username']}, is_admin={user.get('is_admin', 0)}")
    
    # 获取所有任务
    tasks = get_queue_status()
    
    # 普通用户只返回自己的任务
    if user.get("is_admin") != 1:
        tasks = [t for t in tasks if t.get("user_id") == user["id"]]
    
    return {"code": 200, "message": "成功", "data": tasks}


# ============================================================
# 2. 获取队列统计信息
# ============================================================

@router.get("/stats")
async def get_queue_stats_route(user: dict = Depends(get_current_user)):
    """
    获取队列统计信息
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": {
                "total": 10,
                "pending": 3,
                "processing": 2,
                "completed": 4,
                "failed": 1,
                "cancelled": 0
            }
        }
    """
    logger.debug(f"📊 获取队列统计: user={user['username']}")
    
    stats = get_queue_stats()
    
    return {"code": 200, "message": "成功", "data": stats}


# ============================================================
# 3. 取消任务
# ============================================================

@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """
    取消任务
    
    普通用户只能取消自己的任务，管理员可以取消任何任务
    
    Args:
        task_id: 任务ID（cache_key）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "任务已取消"
        }
    """
    logger.info(f"🗑️ 取消任务请求: task_id={task_id}, user={user['username']}")
    
    # 获取任务
    task = queue_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在～～(′Д`)")
    
    # 权限检查
    if user.get("is_admin") != 1 and task.user_id != user["id"]:
        logger.warning(f"⚠️ 用户 {user['username']} 无权取消任务 {task_id}")
        raise HTTPException(status_code=403, detail="无权操作此任务～～(′Д`)")
    
    # 取消任务
    success = queue_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="任务无法取消（可能已完成）～～(′Д`)")
    
    logger.info(f"✅ 任务已取消: {task_id} (user={user['username']})")
    
    return {"code": 200, "message": "任务已取消"}


# ============================================================
# 4. 删除任务（物理删除）
# ============================================================

@router.delete("/{task_id}/remove")
async def remove_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """
    删除任务（物理删除，同时清理缓存文件）
    
    普通用户只能删除自己的任务，管理员可以删除任何任务
    
    Args:
        task_id: 任务ID（cache_key）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "任务已删除"
        }
    """
    logger.info(f"🗑️ 删除任务请求: task_id={task_id}, user={user['username']}")
    
    # 获取任务
    task = queue_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在～～(′Д`)")
    
    # 权限检查
    if user.get("is_admin") != 1 and task.user_id != user["id"]:
        logger.warning(f"⚠️ 用户 {user['username']} 无权删除任务 {task_id}")
        raise HTTPException(status_code=403, detail="无权操作此任务～～(′Д`)")
    
    # 从队列移除
    success = queue_manager.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="任务删除失败～～(′Д`)")
    
    # 清理缓存文件
    clear_cache(task_id)
    
    logger.info(f"✅ 任务已删除: {task_id} (user={user['username']})")
    
    return {"code": 200, "message": "任务已删除"}


# ============================================================
# 5. 清空已完成任务
# ============================================================

@router.delete("/completed")
async def clear_completed_tasks(user: dict = Depends(get_current_user)):
    """
    清空已完成的任务（仅管理员）
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "已清空 5 个任务"
        }
    """
    if user.get("is_admin") != 1:
        raise HTTPException(status_code=403, detail="需要管理员权限～～(′Д`)")
    
    logger.info(f"🗑️ 管理员 {user['username']} 清空已完成任务")
    
    tasks = queue_manager.get_all_tasks()
    removed = 0
    
    for task in tasks:
        if task.status.value == "完成" or task.status.value == "已取消":
            if queue_manager.remove_task(task.task_id):
                clear_cache(task.task_id)
                removed += 1
    
    logger.info(f"✅ 已清空 {removed} 个已完成任务")
    
    return {"code": 200, "message": f"已清空 {removed} 个任务"}