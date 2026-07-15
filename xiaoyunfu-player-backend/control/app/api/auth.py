"""
小云浮音视频处理服务 - 认证路由

职责：
1. 用户登录（生成 JWT Token）
2. 用户注册
3. 修改密码
4. 获取当前用户信息
5. Token 验证依赖项（供其他路由使用）

文件位置: control/app/api/auth.py
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.database import (
    get_user_by_username,
    get_user_by_id,
    create_user,
    create_session,
    get_session_by_token,
    delete_session
)
from app.core.security import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
    get_user_id_from_token,
    create_user_session
)
from app.models.request import LoginRequest, RegisterRequest, ChangePasswordRequest
from app.models.response import success, error, LoginResponseData
from app.utils.logger import get_logger

logger = get_logger("api.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

# HTTP Bearer 认证（用于获取 Token）
security = HTTPBearer()


# ============================================================
# 1. Token 验证依赖项
# ============================================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    获取当前登录用户（依赖项）
    
    用于需要登录才能访问的路由
    
    使用方式:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user": user}
    
    Returns:
        用户信息字典
        
    Raises:
        HTTPException: Token 无效或已过期
    """
    token = credentials.credentials
    logger.debug(f"🔑 验证 Token: {token[:16]}...")
    
    # 检查 Token 是否有效
    session = get_session_by_token(token)
    if not session:
        logger.warning(f"⚠️ Token 无效或已过期: {token[:16]}...")
        raise HTTPException(status_code=401, detail="请先登录～～(′Д`)")
    
    # 获取用户信息
    user = get_user_by_id(session["user_id"])
    if not user:
        logger.warning(f"⚠️ 用户不存在: {session['user_id']}")
        raise HTTPException(status_code=401, detail="用户不存在～～(′Д`)")
    
    logger.debug(f"✅ 用户认证成功: {user['username']} (ID: {user['id']})")
    return user


async def get_current_admin(user: dict = Depends(get_current_user)):
    """
    获取当前登录的管理员用户（依赖项）
    
    用于需要管理员权限才能访问的路由
    
    Raises:
        HTTPException: 用户不是管理员
    """
    if user.get("is_admin") != 1:
        logger.warning(f"⚠️ 非管理员尝试访问管理员接口: {user['username']}")
        raise HTTPException(status_code=403, detail="需要管理员权限～～(′Д`)")
    return user


# ============================================================
# 2. 登录
# ============================================================

@router.post("/login")
async def login(request: LoginRequest):
    """
    用户登录
    
    Args:
        request: 登录请求（用户名 + 密码）
    
    Returns:
        {
            "code": 200,
            "message": "登录成功",
            "data": {
                "token": "JWT_TOKEN",
                "user_id": 1,
                "username": "admin",
                "is_admin": true
            }
        }
    
    Raises:
        HTTPException: 用户名或密码错误
    """
    logger.info(f"🔐 登录请求: username={request.username}")
    
    # 查找用户
    user = get_user_by_username(request.username)
    if not user:
        logger.warning(f"⚠️ 登录失败: 用户不存在 {request.username}")
        raise HTTPException(status_code=401, detail="用户名或密码错误～～(′Д`)")
    
    # 验证密码
    if not verify_password(request.password, user["password_hash"]):
        logger.warning(f"⚠️ 登录失败: 密码错误 {request.username}")
        raise HTTPException(status_code=401, detail="用户名或密码错误～～(′Д`)")
    
    # 生成 Token
    token_data = create_user_session(
        user_id=user["id"],
        username=user["username"],
        is_admin=bool(user["is_admin"])
    )
    
    # 保存到数据库
    create_session(
        user_id=user["id"],
        token=token_data["token"],
        expire_days=settings.TOKEN_EXPIRE_DAYS
    )
    
    logger.info(f"✅ 登录成功: {user['username']} (ID: {user['id']})")
    
    return success(
        data={
            "token": token_data["token"],
            "user_id": user["id"],
            "username": user["username"],
            "is_admin": bool(user["is_admin"])
        },
        message="登录成功"
    )


# ============================================================
# 3. 注册
# ============================================================

@router.post("/register")
async def register(request: RegisterRequest):
    """
    用户注册
    
    Args:
        request: 注册请求（用户名 + 密码）
    
    Returns:
        {
            "code": 200,
            "message": "注册成功",
            "data": {
                "user_id": 2,
                "username": "new_user"
            }
        }
    
    Raises:
        HTTPException: 用户名已存在
    """
    logger.info(f"📝 注册请求: username={request.username}")
    
    # 检查用户名是否已存在
    existing = get_user_by_username(request.username)
    if existing:
        logger.warning(f"⚠️ 注册失败: 用户名已存在 {request.username}")
        raise HTTPException(status_code=400, detail="用户名已存在～～(′Д`)")
    
    # 创建用户
    password_hash = hash_password(request.password)
    user_id = create_user(
        username=request.username,
        password_hash=password_hash,
        is_admin=0  # 普通用户
    )
    
    logger.info(f"✅ 注册成功: {request.username} (ID: {user_id})")
    
    return success(
        data={
            "user_id": user_id,
            "username": request.username
        },
        message="注册成功"
    )


# ============================================================
# 4. 修改密码
# ============================================================

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: dict = Depends(get_current_user)
):
    """
    修改密码（需要登录）
    
    Args:
        request: 修改密码请求（旧密码 + 新密码）
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "密码已修改"
        }
    
    Raises:
        HTTPException: 旧密码错误
    """
    logger.info(f"🔐 修改密码请求: {user['username']}")
    
    # 验证旧密码
    if not verify_password(request.old_password, user["password_hash"]):
        logger.warning(f"⚠️ 修改密码失败: 旧密码错误 {user['username']}")
        raise HTTPException(status_code=400, detail="旧密码错误～～(′Д`)")
    
    # 更新密码
    from app.core.database import update_user_password
    new_hash = hash_password(request.new_password)
    update_user_password(user["id"], new_hash)
    
    logger.info(f"✅ 密码修改成功: {user['username']}")
    
    return success(message="密码已修改")


# ============================================================
# 5. 获取当前用户信息
# ============================================================

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    获取当前登录用户信息（需要登录）
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "成功",
            "data": {
                "id": 1,
                "username": "admin",
                "is_admin": true,
                "created_at": "2024-01-01 00:00:00"
            }
        }
    """
    logger.debug(f"📋 获取用户信息: {user['username']}")
    
    return success(
        data={
            "id": user["id"],
            "username": user["username"],
            "is_admin": bool(user["is_admin"]),
            "created_at": user.get("created_at")
        }
    )


# ============================================================
# 6. 登出
# ============================================================

@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """
    登出（删除当前会话）
    
    Args:
        user: 当前登录用户
    
    Returns:
        {
            "code": 200,
            "message": "已登出"
        }
    """
    logger.info(f"🚪 登出请求: {user['username']}")
    
    # 删除所有会话（从数据库）
    from app.core.database import delete_all_sessions
    delete_all_sessions(user["id"])
    
    logger.info(f"✅ 登出成功: {user['username']}")
    
    return success(message="已登出")