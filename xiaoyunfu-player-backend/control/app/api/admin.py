"""
小云浮音视频处理服务 - 管理员路由

职责：
1. 用户管理（列表、重置密码、删除）
2. 系统统计信息
3. 缓存管理（清理全部）

仅管理员可访问

文件位置: control/app/api/admin.py
"""

from fastapi import APIRouter, HTTPException, Depends

from app.core.database import (
    execute_query,
    execute_one,
    execute_update,
    get_user_by_id
)
from app.core.security import hash_password
from app.models.request import ResetPasswordRequest
from app.models.response import success, error
from app.services.transcoder import get_cache_size_mb, clear_cache
from app.services.queue_service import get_queue_stats
from app.api.auth import get_current_admin
from app.utils.logger import get_logger

logger = get_logger("api.admin")
router = APIRouter(prefix="/api/v1/admin", tags=["管理员"])


# ============================================================
# 1. 获取用户列表
# ============================================================

@router.get("/users")
async def list_users(admin: dict = Depends(get_current_admin)):
    """
    获取所有用户列表（仅管理员）
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": [
                {
                    "id": 1,
                    "username": "admin",
                    "is_admin": true,
                    "created_at": "2024-01-01 00:00:00"
                }
            ]
        }
    """
    logger.info(f"📋 管理员 {admin['username']} 查看用户列表")
    
    rows = execute_query(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY id"
    )
    
    return success(data=rows)


# ============================================================
# 2. 获取用户详情
# ============================================================

@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    获取用户详情（仅管理员）
    
    Args:
        user_id: 用户ID
    
    Returns:
        用户信息
    """
    logger.info(f"📋 管理员 {admin['username']} 查看用户详情: ID={user_id}")
    
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在～～(′Д`)")
    
    return success(data=user)


# ============================================================
# 3. 重置用户密码
# ============================================================

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: ResetPasswordRequest,
    admin: dict = Depends(get_current_admin)
):
    """
    重置用户密码（仅管理员）
    
    Args:
        user_id: 用户ID
        request: 新密码
        admin: 当前管理员
    
    Returns:
        {
            "code": 200,
            "message": "密码已重置"
        }
    """
    logger.info(f"🔐 管理员 {admin['username']} 重置用户密码: ID={user_id}")
    
    # 检查用户是否存在
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在～～(′Д`)")
    
    # 不能重置管理员自己的密码（通过此接口）
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能通过此接口重置自己的密码～～(′Д`)")
    
    # 更新密码
    new_hash = hash_password(request.new_password)
    execute_update(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user_id)
    )
    
    logger.info(f"✅ 用户密码已重置: ID={user_id}")
    
    return success(message="密码已重置")


# ============================================================
# 4. 删除用户
# ============================================================

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: dict = Depends(get_current_admin)
):
    """
    删除用户（仅管理员，不能删除自己，不能删除管理员）
    
    Args:
        user_id: 用户ID
        admin: 当前管理员
    
    Returns:
        {
            "code": 200,
            "message": "已删除"
        }
    """
    logger.info(f"🗑️ 管理员 {admin['username']} 删除用户: ID={user_id}")
    
    # 不能删除自己
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己～～(′Д`)")
    
    # 检查用户是否存在
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在～～(′Д`)")
    
    # 不能删除管理员
    if user.get("is_admin") == 1:
        raise HTTPException(status_code=400, detail="不能删除管理员账号～～(′Д`)")
    
    # 删除用户（级联删除会自动清理关联数据）
    execute_update("DELETE FROM users WHERE id = ?", (user_id,))
    
    logger.info(f"✅ 用户已删除: ID={user_id}")
    
    return success(message="已删除")


# ============================================================
# 5. 系统统计信息
# ============================================================

@router.get("/stats")
async def get_system_stats(admin: dict = Depends(get_current_admin)):
    """
    获取系统统计信息（仅管理员）
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": {
                "users": {
                    "total": 10,
                    "admins": 1,
                    "normal": 9
                },
                "cache": {
                    "total_mb": 123.45,
                    "max_mb": 2048
                },
                "queue": {
                    "total": 0,
                    "pending": 0,
                    "processing": 0,
                    "completed": 0,
                    "failed": 0
                }
            }
        }
    """
    logger.info(f"📊 管理员 {admin['username']} 查看系统统计")
    
    # 用户统计
    user_stats = execute_one(
        "SELECT COUNT(*) as total, SUM(is_admin) as admins FROM users"
    )
    total = user_stats.get("total", 0) or 0
    admins = user_stats.get("admins", 0) or 0
    
    # 缓存统计
    cache_mb = get_cache_size_mb()
    
    # 队列统计
    queue_stats = get_queue_stats()
    
    return success(data={
        "users": {
            "total": total,
            "admins": admins,
            "normal": total - admins
        },
        "cache": {
            "total_mb": round(cache_mb, 2),
            "max_mb": 2048  # 可从配置读取
        },
        "queue": queue_stats
    })


# ============================================================
# 6. 清理全部缓存
# ============================================================

@router.delete("/cache/all")
async def clear_all_cache(admin: dict = Depends(get_current_admin)):
    """
    清理全部缓存（仅管理员）
    
    Returns:
        {
            "code": 200,
            "message": "已删除 10 个缓存"
        }
    """
    logger.warning(f"⚠️ 管理员 {admin['username']} 清理全部缓存")
    
    count = clear_cache()
    
    logger.info(f"✅ 已清理 {count} 个缓存")
    
    return success(message=f"已删除 {count} 个缓存")


# ============================================================
# 7. 获取所有绑定的账号
# ============================================================

@router.get("/accounts")
async def list_all_accounts(admin: dict = Depends(get_current_admin)):
    """
    获取所有用户绑定的账号（仅管理员）
    
    Returns:
        所有绑定的账号列表
    """
    logger.info(f"📋 管理员 {admin['username']} 查看所有绑定账号")
    
    rows = execute_query(
        """
        SELECT 
            a.id,
            a.user_id,
            u.username,
            a.platform,
            a.created_at
        FROM api_accounts a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
        """
    )
    
    return success(data=rows)