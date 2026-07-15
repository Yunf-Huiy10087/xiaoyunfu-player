"""
小云浮音视频处理服务 - 插件管理路由

职责：
1. 获取所有插件列表（元数据）
2. 获取单个插件元数据
3. 插件登录认证（转发给插件端）
4. 刷新插件列表

文件位置: control/app/api/plugins.py
"""

from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends

from app.core.config import settings
from app.core.database import upsert_account
from app.models.request import PluginAuthRequest
from app.models.response import success, error, PluginMetaResponse
from app.services.plugin_client import plugin_client
from app.api.auth import get_current_user
from app.utils.logger import get_logger

logger = get_logger("api.plugins")
router = APIRouter(prefix="/api/v1/plugins", tags=["插件"])


# ============================================================
# 1. 获取所有插件列表
# ============================================================

@router.get("/")
async def list_plugins(user: dict = Depends(get_current_user)):
    """
    获取所有插件列表（元数据）
    
    前端根据此接口返回的数据动态生成登录界面
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": {
                "plugins": [
                    {
                        "source": "bilibili",
                        "display_name": "哔哩哔哩",
                        "version": "2.1.0",
                        "author": "小云浮团队",
                        "icon": "bilibili",
                        "auth_methods": [
                            {
                                "id": "qr_code",
                                "name": "二维码扫码",
                                "description": "使用B站APP扫码登录",
                                "fields": []
                            },
                            {
                                "id": "password",
                                "name": "账号密码",
                                "fields": [
                                    {"name": "username", "label": "手机号/邮箱", "type": "text", "required": true},
                                    {"name": "password", "label": "密码", "type": "password", "required": true}
                                ]
                            }
                        ],
                        "cookie_format": "SESSDATA=xxx; bili_jct=xxx"
                    }
                ]
            }
        }
    """
    logger.debug(f"📋 获取插件列表: user={user['username']}")
    
    # 从插件端获取所有插件的元数据
    plugins_data = await plugin_client.get_all_meta()
    
    # 转换为前端需要的格式
    plugins = []
    for source, meta in plugins_data.items():
        if isinstance(meta, dict) and "error" not in meta:
            plugins.append({
                "source": meta.get("source", source),
                "display_name": meta.get("display_name", source),
                "version": meta.get("version", "1.0.0"),
                "author": meta.get("author", "未知"),
                "icon": meta.get("icon", "link"),
                "auth_methods": meta.get("auth_methods", []),
                "cookie_format": meta.get("cookie_format", "")
            })
    
    return success(data={"plugins": plugins})


# ============================================================
# 2. 获取单个插件元数据
# ============================================================

@router.get("/{source}")
async def get_plugin_meta(
    source: str,
    user: dict = Depends(get_current_user)
):
    """
    获取单个插件元数据
    
    Args:
        source: 插件名称
        user: 当前登录用户
    
    Returns:
        插件元数据
    """
    logger.debug(f"📋 获取插件元数据: source={source}, user={user['username']}")
    
    meta = await plugin_client.get_meta(source)
    
    if not meta or "error" in meta:
        raise HTTPException(status_code=404, detail=f"插件 {source} 不存在～～(′Д`)")
    
    return success(data=meta)


# ============================================================
# 3. 插件登录认证
# ============================================================

@router.post("/{source}/auth")
async def plugin_auth(
    source: str,
    request: PluginAuthRequest,
    user: dict = Depends(get_current_user)
):
    """
    插件登录认证
    
    用户提交登录信息后，控制端转发给插件端处理
    
    Args:
        source: 插件名称
        request: 认证请求（method + data）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "绑定成功",
            "data": {
                "cookie": "SESSDATA=xxx",
                "user_info": {"username": "xxx"}
            }
        }
    """
    logger.info(f"🔐 插件认证请求: source={source}, method={request.method}, user={user['username']}")
    
    # 调用插件端认证接口
    result = await plugin_client.auth(
        source=source,
        method=request.method,
        data=request.data,
        user_id=user["id"]
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="认证服务不可用～～(′Д`)")
    
    # 检查认证结果
    if result.get("success"):
        # 登录成功，保存 Cookie 到数据库
        cookie = result.get("cookie", "")
        user_info = result.get("user_info", {})
        
        if cookie:
            # 保存到数据库
            upsert_account(
                user_id=user["id"],
                platform=source,
                cookie=cookie,
                account_data=user_info
            )
            logger.info(f"✅ 插件认证成功: {source}, user={user['username']}")
            return success(
                data={
                    "cookie": cookie[:20] + "...",
                    "user_info": user_info
                },
                message="绑定成功"
            )
        else:
            # 登录成功但没有返回 Cookie（可能是二维码扫码状态）
            logger.info(f"⏳ 插件认证等待中: {source}, user={user['username']}")
            return success(
                data=result,
                message=result.get("message", "等待确认")
            )
    else:
        # 认证失败
        error_msg = result.get("error", "认证失败")
        logger.warning(f"⚠️ 插件认证失败: {source}, error={error_msg}")
        raise HTTPException(status_code=400, detail=f"{error_msg}～～(′Д`)")


# ============================================================
# 4. 刷新插件列表
# ============================================================

@router.post("/refresh")
async def refresh_plugins(user: dict = Depends(get_current_user)):
    """
    刷新插件列表（重新获取元数据）
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "刷新成功",
            "data": {
                "plugins": ["bilibili", "netease"]
            }
        }
    """
    logger.info(f"🔄 刷新插件列表: user={user['username']}")
    
    # 重新获取所有插件的元数据
    plugins_data = await plugin_client.get_all_meta()
    
    plugins = list(plugins_data.keys())
    
    logger.info(f"✅ 插件列表刷新成功: {len(plugins)} 个插件")
    
    return success(
        data={"plugins": plugins},
        message=f"刷新成功，共 {len(plugins)} 个插件"
    )


# ============================================================
# 5. 获取用户已绑定的账号
# ============================================================

@router.get("/accounts")
async def get_user_accounts(user: dict = Depends(get_current_user)):
    """
    获取当前用户已绑定的所有账号
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": [
                {
                    "id": 1,
                    "platform": "bilibili",
                    "cookie": "SESSDATA=xxx...",
                    "account_data": {"username": "xxx"},
                    "created_at": "2024-01-01 00:00:00"
                }
            ]
        }
    """
    logger.debug(f"📋 获取用户账号: user={user['username']}")
    
    from app.core.database import execute_query
    
    accounts = execute_query(
        "SELECT id, platform, cookie, account_data, created_at FROM api_accounts WHERE user_id = ?",
        (user["id"],)
    )
    
    # 脱敏处理（只显示 Cookie 的前20个字符）
    for acc in accounts:
        if acc.get("cookie"):
            acc["cookie"] = acc["cookie"][:30] + "..."
    
    return success(data=accounts)


# ============================================================
# 6. 删除用户绑定的账号
# ============================================================

@router.delete("/accounts/{account_id}")
async def delete_user_account(
    account_id: int,
    user: dict = Depends(get_current_user)
):
    """
    删除用户绑定的账号
    
    Args:
        account_id: 账号ID
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "已删除"
        }
    """
    logger.info(f"🗑️ 删除用户账号: account_id={account_id}, user={user['username']}")
    
    from app.core.database import execute_update, execute_one
    
    # 检查账号是否属于当前用户
    account = execute_one(
        "SELECT id FROM api_accounts WHERE id = ? AND user_id = ?",
        (account_id, user["id"])
    )
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在或无权限～～(′Д`)")
    
    # 删除账号
    execute_update("DELETE FROM api_accounts WHERE id = ?", (account_id,))
    
    logger.info(f"✅ 账号已删除: ID={account_id}, user={user['username']}")
    
    return success(message="已删除")