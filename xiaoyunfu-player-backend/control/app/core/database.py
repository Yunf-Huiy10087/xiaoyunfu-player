"""
小云浮音视频处理服务 - 数据库模块

职责：
1. 管理 SQLite 数据库连接
2. 创建所有表结构
3. 提供基础 CRUD 操作
4. 创建默认管理员账号

文件位置: control/app/core/database.py
"""

import sqlite3
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("database")


# ============================================================
# 1. 数据库路径
# ============================================================

# 从配置读取数据库路径
DB_PATH = settings.DB_PATH

# 确保数据库目录存在
db_dir = Path(DB_PATH).parent
db_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. 数据库连接管理
# ============================================================

_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    """
    获取数据库连接（单例模式）
    
    Returns:
        sqlite3.Connection 对象
    """
    global _connection
    
    if _connection is None:
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        logger.info(f"数据库连接已建立: {DB_PATH}")
    
    return _connection


@contextmanager
def get_cursor():
    """
    获取数据库游标的上下文管理器
    
    使用方式:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


# ============================================================
# 3. 表结构定义
# ============================================================

SCHEMA = """
-- ============================================================
-- 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 会话表（Token管理）
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- 账号绑定表（存储各平台Cookie）
-- ============================================================
CREATE TABLE IF NOT EXISTS api_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    cookie TEXT,
    account_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- 歌单表
-- ============================================================
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    is_public INTEGER DEFAULT 1,
    description TEXT DEFAULT '',
    cover_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- 歌单歌曲表
-- ============================================================
CREATE TABLE IF NOT EXISTS playlist_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,
    song_id TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    artist TEXT DEFAULT '',
    album TEXT DEFAULT '',
    cover_url TEXT DEFAULT '',
    duration INTEGER DEFAULT 0,
    added_by INTEGER,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
);

-- ============================================================
-- 上传文件表
-- ============================================================
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    file_type TEXT DEFAULT 'audio',
    title TEXT DEFAULT '',
    artist TEXT DEFAULT '',
    size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- 缓存映射表（记录哪个MD5对应哪个文件）
-- ============================================================
CREATE TABLE IF NOT EXISTS cache_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    song_id TEXT NOT NULL,
    title TEXT,
    singer TEXT,
    duration INTEGER DEFAULT 0,
    cover_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 索引（提升查询性能）
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_api_accounts_user_platform ON api_accounts(user_id, platform);
CREATE INDEX IF NOT EXISTS idx_playlist_songs_playlist ON playlist_songs(playlist_id);
CREATE INDEX IF NOT EXISTS idx_cache_metadata_key ON cache_metadata(cache_key);
"""


# ============================================================
# 4. 初始化数据库
# ============================================================

def init_db() -> None:
    """
    初始化数据库：创建所有表 + 默认管理员
    """
    try:
        with get_cursor() as cursor:
            cursor.executescript(SCHEMA)
        logger.info("✅ 数据库表结构初始化完成")
        
        # ============================================================
        # 🔥 创建默认管理员（如果不存在）
        # ============================================================
        admin = execute_one("SELECT id FROM users WHERE username = ?", ("admin",))
        if not admin:
            from app.core.security import hash_password
            admin_hash = hash_password("Hi-world")
            execute_insert(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                ("admin", admin_hash, 1)
            )
            logger.info("✅ 已创建默认管理员: admin / Hi-world")
        else:
            logger.debug("✅ 默认管理员已存在")
        
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        raise


# ============================================================
# 5. 基础查询方法
# ============================================================

def execute_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """
    执行查询并返回结果列表（字典格式）
    
    Args:
        sql: SQL语句
        params: 参数元组
    
    Returns:
        字典列表
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def execute_one(sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """
    执行查询并返回单条结果
    
    Args:
        sql: SQL语句
        params: 参数元组
    
    Returns:
        单条结果字典，如果没有结果返回 None
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def execute_update(sql: str, params: tuple = ()) -> int:
    """
    执行更新/插入/删除操作
    
    Args:
        sql: SQL语句
        params: 参数元组
    
    Returns:
        影响的行数
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


def execute_insert(sql: str, params: tuple = ()) -> int:
    """
    执行插入操作，返回自增ID
    
    Args:
        sql: SQL语句
        params: 参数元组
    
    Returns:
        插入行的 rowid
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.lastrowid


# ============================================================
# 6. 便捷的用户管理方法
# ============================================================

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """根据用户名获取用户"""
    return execute_one(
        "SELECT id, username, password_hash, is_admin, created_at FROM users WHERE username = ?",
        (username,)
    )


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """根据用户ID获取用户"""
    return execute_one(
        "SELECT id, username, password_hash, is_admin, created_at FROM users WHERE id = ?",
        (user_id,)
    )


def create_user(username: str, password_hash: str, is_admin: int = 0) -> int:
    """创建用户"""
    return execute_insert(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, password_hash, is_admin)
    )


def update_user_password(user_id: int, new_hash: str) -> bool:
    """更新用户密码"""
    affected = execute_update(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user_id)
    )
    return affected > 0


def delete_user(user_id: int) -> bool:
    """删除用户（级联删除会清理所有关联数据）"""
    affected = execute_update(
        "DELETE FROM users WHERE id = ? AND is_admin = 0",
        (user_id,)
    )
    return affected > 0


# ============================================================
# 7. 便捷的会话管理方法
# ============================================================

def create_session(user_id: int, token: str, expire_days: int = 30) -> int:
    """创建会话"""
    return execute_insert(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, datetime('now', ?))",
        (user_id, token, f'+{expire_days} days')
    )


def get_session_by_token(token: str) -> Optional[Dict[str, Any]]:
    """根据Token获取会话（同时检查是否过期）"""
    return execute_one(
        "SELECT * FROM sessions WHERE token = ? AND expires_at > datetime('now')",
        (token,)
    )


def delete_session(token: str) -> bool:
    """删除会话（登出）"""
    affected = execute_update("DELETE FROM sessions WHERE token = ?", (token,))
    return affected > 0


def delete_all_sessions(user_id: int) -> int:
    """删除用户的所有会话"""
    return execute_update("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# ============================================================
# 8. 便捷的账号绑定方法
# ============================================================

def get_accounts_by_user(user_id: int) -> List[Dict[str, Any]]:
    """获取用户的所有绑定账号"""
    return execute_query(
        "SELECT id, platform, cookie, account_data, created_at FROM api_accounts WHERE user_id = ? ORDER BY created_at",
        (user_id,)
    )


def get_account(user_id: int, platform: str) -> Optional[Dict[str, Any]]:
    """获取用户指定平台的绑定账号"""
    return execute_one(
        "SELECT id, platform, cookie, account_data FROM api_accounts WHERE user_id = ? AND platform = ?",
        (user_id, platform)
    )


def upsert_account(user_id: int, platform: str, cookie: str = "", account_data: str = "") -> int:
    """
    插入或更新账号绑定
    
    Args:
        user_id: 用户ID
        platform: 平台名称
        cookie: Cookie字符串
        account_data: 额外数据（JSON格式）
    
    Returns:
        记录ID
    """
    existing = get_account(user_id, platform)
    if existing:
        execute_update(
            "UPDATE api_accounts SET cookie = ?, account_data = ? WHERE id = ?",
            (cookie, account_data, existing["id"])
        )
        return existing["id"]
    else:
        return execute_insert(
            "INSERT INTO api_accounts (user_id, platform, cookie, account_data) VALUES (?, ?, ?, ?)",
            (user_id, platform, cookie, account_data)
        )


def delete_account(user_id: int, platform: str) -> bool:
    """删除账号绑定"""
    affected = execute_update(
        "DELETE FROM api_accounts WHERE user_id = ? AND platform = ?",
        (user_id, platform)
    )
    return affected > 0