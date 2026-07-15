"""
小云浮音视频处理服务 - 安全模块

职责：
1. 密码哈希和验证（bcrypt）
2. JWT Token 生成和验证
3. Token 过期管理

文件位置: control/app/core/security.py
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("security")

# ============================================================
# 1. 密码加密配置
# ============================================================

# bcrypt 加密上下文（自动处理盐值和哈希）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    使用 bcrypt 哈希密码
    
    Args:
        password: 明文密码
    
    Returns:
        哈希后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配
    
    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码
    
    Returns:
        True 匹配，False 不匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# 2. Token 管理（JWT）
# ============================================================

# JWT 配置
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = settings.TOKEN_EXPIRE_DAYS


def create_token(user_id: int, username: str, is_admin: bool = False) -> str:
    """
    创建 JWT Token
    
    Args:
        user_id: 用户ID
        username: 用户名
        is_admin: 是否为管理员
    
    Returns:
        JWT Token 字符串
    """
    # 过期时间
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    
    # Token 载荷（Payload）
    payload = {
        "sub": str(user_id),           # 用户ID（subject）
        "username": username,          # 用户名
        "is_admin": is_admin,          # 管理员标识
        "exp": expire,                 # 过期时间
        "iat": datetime.utcnow(),      # 签发时间
        "jti": uuid.uuid4().hex        # 唯一ID（防重放）
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Token 生成成功: user_id={user_id}, expires_at={expire}")
    return token


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码并验证 JWT Token
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        解码后的载荷字典，如果验证失败返回 None
    
    Raises:
        jwt.ExpiredSignatureError: Token 已过期
        jwt.InvalidTokenError: Token 无效
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Token 解码成功: user_id={payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token 无效: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    从 Token 中提取用户ID
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        用户ID，如果无效返回 None
    """
    payload = decode_token(token)
    if not payload:
        return None
    try:
        return int(payload.get("sub", 0))
    except (ValueError, TypeError):
        return None


def get_username_from_token(token: str) -> Optional[str]:
    """
    从 Token 中提取用户名
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        用户名，如果无效返回 None
    """
    payload = decode_token(token)
    if not payload:
        return None
    return payload.get("username")


def is_token_admin(token: str) -> bool:
    """
    检查 Token 是否为管理员
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        True 管理员，False 普通用户
    """
    payload = decode_token(token)
    if not payload:
        return False
    return payload.get("is_admin", False)


# ============================================================
# 3. Token 过期检查
# ============================================================

def is_token_expired(token: str) -> bool:
    """
    检查 Token 是否已过期
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        True 已过期，False 未过期
    """
    payload = decode_token(token)
    if not payload:
        return True
    exp = payload.get("exp")
    if not exp:
        return True
    return datetime.utcnow() > datetime.utcfromtimestamp(exp)


def get_token_expire_time(token: str) -> Optional[datetime]:
    """
    获取 Token 的过期时间
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        过期时间（datetime），如果无效返回 None
    """
    payload = decode_token(token)
    if not payload:
        return None
    exp = payload.get("exp")
    if not exp:
        return None
    return datetime.utcfromtimestamp(exp)


# ============================================================
# 4. 生成随机 Token（备用，用于非 JWT 场景）
# ============================================================

def generate_random_token(length: int = 32) -> str:
    """
    生成随机的十六进制 Token（用于 API Key 等场景）
    
    Args:
        length: Token 长度（默认32）
    
    Returns:
        十六进制 Token 字符串
    """
    return uuid.uuid4().hex[:length]


# ============================================================
# 5. 快捷函数
# ============================================================

def create_user_session(user_id: int, username: str, is_admin: bool = False) -> Dict[str, Any]:
    """
    为用户创建完整会话（Token + 用户信息）
    
    Args:
        user_id: 用户ID
        username: 用户名
        is_admin: 是否为管理员
    
    Returns:
        {
            "token": "JWT Token",
            "user_id": 1,
            "username": "admin",
            "is_admin": True,
            "expires_at": "2024-01-01 00:00:00"
        }
    """
    token = create_token(user_id, username, is_admin)
    payload = decode_token(token)
    
    return {
        "token": token,
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
        "expires_at": payload.get("exp") if payload else None
    }