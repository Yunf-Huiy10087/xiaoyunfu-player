"""
小云浮音视频处理服务 - FFmpeg 转码服务

职责：
1. 将原始音频（m4a/flac/mp3）转码为 Opus 格式（64kbps）
2. 管理音频缓存（检查、保存、删除）
3. 保存元数据、封面、歌词

文件位置: control/app/services/transcoder.py
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import httpx

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("transcoder")

# ============================================================
# 1. 缓存管理
# ============================================================

def get_cache_key(source: str, song_id: str) -> str:
    """
    生成缓存键（MD5）
    
    Args:
        source: 来源（如 bilibili）
        song_id: 歌曲ID
    
    Returns:
        32位MD5字符串
    """
    raw = f"{source}_{song_id}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cache_paths(cache_key: str) -> Tuple[Path, Path, Path, Path, Path]:
    """
    获取缓存相关路径
    
    Args:
        cache_key: 缓存键（MD5）
    
    Returns:
        (cache_dir, audio_path, cover_path, lyric_path, meta_path)
    """
    cache_dir = Path(settings.CACHE_DIR) / cache_key
    return (
        cache_dir,
        cache_dir / f"{cache_key}.opus",
        cache_dir / "cover.jpg",
        cache_dir / "lyric.lrc",
        cache_dir / "info.json"
    )


def is_cached(cache_key: str) -> bool:
    """
    检查缓存是否存在且有效
    
    Args:
        cache_key: 缓存键（MD5）
    
    Returns:
        True 存在且有效，False 不存在
    """
    _, audio_path, _, _, _ = get_cache_paths(cache_key)
    return audio_path.exists() and audio_path.stat().st_size > 1024


def get_cache_size_mb() -> float:
    """
    获取缓存总大小（MB）
    
    Returns:
        总大小（MB）
    """
    cache_dir = Path(settings.CACHE_DIR)
    if not cache_dir.exists():
        return 0.0
    
    total = 0
    for item in cache_dir.iterdir():
        if item.is_dir():
            for f in item.glob("*.opus"):
                if f.is_file():
                    total += f.stat().st_size
    
    return total / (1024 * 1024)


def clear_cache(cache_key: Optional[str] = None) -> int:
    """
    清理缓存
    
    Args:
        cache_key: 指定缓存键，不指定则清理全部
    
    Returns:
        清理的文件数
    """
    cache_dir = Path(settings.CACHE_DIR)
    if not cache_dir.exists():
        return 0
    
    deleted = 0
    
    if cache_key:
        # 删除指定缓存
        target_dir = cache_dir / cache_key
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            deleted = 1
    else:
        # 删除全部缓存
        for item in cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                deleted += 1
    
    return deleted


# ============================================================
# 2. 元数据管理
# ============================================================

def save_metadata(cache_key: str, metadata: Dict[str, Any]) -> None:
    """
    保存元数据到 info.json
    
    Args:
        cache_key: 缓存键（MD5）
        metadata: 元数据字典
    """
    cache_dir, _, _, _, meta_path = get_cache_paths(cache_key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 添加时间戳
    metadata["cached_at"] = time.time()
    
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    logger.debug(f"元数据已保存: {cache_key}")


def get_metadata(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    读取元数据
    
    Args:
        cache_key: 缓存键（MD5）
    
    Returns:
        元数据字典，不存在返回 None
    """
    _, _, _, _, meta_path = get_cache_paths(cache_key)
    if not meta_path.exists():
        return None
    
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


# ============================================================
# 3. 封面下载
# ============================================================

async def download_cover(cache_key: str, cover_url: str) -> bool:
    """
    下载封面图片
    
    Args:
        cache_key: 缓存键（MD5）
        cover_url: 封面URL
    
    Returns:
        下载成功返回 True
    """
    if not cover_url:
        return False
    
    cache_dir, _, cover_path, _, _ = get_cache_paths(cache_key)
    
    if cover_path.exists():
        return True
    
    # 处理相对路径
    if cover_url.startswith("//"):
        cover_url = "https:" + cover_url
    
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(cover_url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0"
            })
            if resp.status_code == 200:
                cache_dir.mkdir(parents=True, exist_ok=True)
                with open(cover_path, 'wb') as f:
                    f.write(resp.content)
                logger.debug(f"封面下载成功: {cache_key}")
                return True
            else:
                logger.warning(f"封面下载失败: HTTP {resp.status_code}")
                return False
    except Exception as e:
        logger.error(f"封面下载异常: {e}")
        return False


# ============================================================
# 4. 歌词保存
# ============================================================

def save_lyric(cache_key: str, lyric_text: str) -> bool:
    """
    保存歌词到 lyric.lrc
    
    Args:
        cache_key: 缓存键（MD5）
        lyric_text: 歌词文本（LRC格式）
    
    Returns:
        保存成功返回 True
    """
    if not lyric_text:
        return False
    
    cache_dir, _, _, lyric_path, _ = get_cache_paths(cache_key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    with open(lyric_path, 'w', encoding='utf-8') as f:
        f.write(lyric_text)
    
    logger.debug(f"歌词已保存: {cache_key} ({len(lyric_text)} 字符)")
    return True


# ============================================================
# 5. FFmpeg 转码（核心）
# ============================================================

async def transcode_to_opus(
    source_url: str,
    source: str,
    song_id: str,
    title: str = "",
    singer: str = "",
    cover_url: str = "",
    lyric: str = "",
    duration: int = 0,
    referer: str = "",
    user_agent: str = "Mozilla/5.0"
) -> str:
    """
    下载并转码为 Opus 格式
    
    Args:
        source_url: 原始音频URL
        source: 来源
        song_id: 歌曲ID
        title: 歌曲标题
        singer: 歌手
        cover_url: 封面URL
        lyric: 歌词（LRC格式）
        duration: 时长（秒）
        referer: 请求来源（用于防盗链）
        user_agent: 用户代理
    
    Returns:
        cache_key: 缓存键（MD5）
    
    Raises:
        RuntimeError: 转码失败时抛出
    """
    start_time = time.time()
    cache_key = get_cache_key(source, song_id)
    
    logger.info(f"🎯 开始转码: {title} ({source}, {duration}s)")
    
    # 检查缓存是否已存在
    if is_cached(cache_key):
        logger.info(f"💾 缓存已存在，跳过转码: {cache_key[:8]}...")
        return cache_key
    
    # 获取路径
    cache_dir, audio_path, _, _, _ = get_cache_paths(cache_key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 构建 FFmpeg 命令
    cmd = [
        "ffmpeg",
        "-y",                       # 覆盖输出
        "-hide_banner",             # 隐藏版本信息
        "-loglevel", "error",       # 只输出错误
        "-protocol_whitelist", "http,https,tcp,tls,crypto",
        "-user_agent", user_agent,
    ]
    
    if referer:
        cmd.extend(["-headers", f"Referer: {referer}"])
    
    cmd.extend([
        "-i", source_url,
        "-c:a", "libopus",          # Opus 编码器
        "-b:a", "64k",              # 比特率 64kbps
        "-vbr", "on",               # 可变比特率
        "-compression_level", "10", # 最高压缩
        "-vn",                      # 不处理视频
        str(audio_path)
    ])
    
    logger.debug(f"🔧 FFmpeg 命令: {' '.join(cmd[:3])} ... -i {source_url[:50]}...")
    
    try:
        # 执行转码
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="ignore")[:300]
            logger.error(f"❌ FFmpeg 转码失败: {err_msg}")
            raise RuntimeError(f"FFmpeg 转码失败: {err_msg}")
        
        # 验证输出
        if not audio_path.exists() or audio_path.stat().st_size < 1024:
            logger.error(f"❌ 转码后文件无效: {audio_path}")
            raise RuntimeError("转码后文件无效或为空")
        
        elapsed = time.time() - start_time
        logger.info(f"✅ 转码完成: {audio_path.name} ({audio_path.stat().st_size} bytes, {elapsed:.1f}s)")
        
    except asyncio.TimeoutError:
        logger.error(f"⏰ 转码超时 (超过7200秒): {title}")
        raise RuntimeError("转码超时")
    except FileNotFoundError:
        logger.error("❌ FFmpeg 未安装，请确保系统已安装 ffmpeg")
        raise RuntimeError("FFmpeg 未安装")
    except Exception as e:
        logger.error(f"💥 转码异常: {e}", exc_info=True)
        # 清理可能生成的无效文件
        if audio_path.exists():
            audio_path.unlink()
        raise
    
    # 保存元数据
    metadata = {
        "source": source,
        "song_id": song_id,
        "title": title,
        "singer": singer,
        "duration": duration,
        "cover_url": cover_url,
    }
    save_metadata(cache_key, metadata)
    
    # 下载封面
    if cover_url:
        await download_cover(cache_key, cover_url)
    
    # 保存歌词
    if lyric:
        save_lyric(cache_key, lyric)
    
    return cache_key


# ============================================================
# 6. 缓存清理（过期清理 + 容量清理）
# ============================================================

def clean_expired_cache(expire_seconds: int = 7200) -> int:
    """
    清理过期缓存
    
    Args:
        expire_seconds: 过期时间（秒）
    
    Returns:
        清理的文件数
    """
    cache_dir = Path(settings.CACHE_DIR)
    if not cache_dir.exists():
        return 0
    
    now = time.time()
    deleted = 0
    
    for item in cache_dir.iterdir():
        if not item.is_dir():
            continue
        
        audio_file = item / f"{item.name}.opus"
        if audio_file.exists():
            mtime = audio_file.stat().st_mtime
            if now - mtime > expire_seconds:
                shutil.rmtree(item, ignore_errors=True)
                deleted += 1
                logger.debug(f"🧹 过期删除: {item.name}")
    
    return deleted


def clean_by_size(max_size_mb: int = 2048) -> int:
    """
    按容量清理（保留最近使用的缓存）
    
    Args:
        max_size_mb: 最大容量（MB）
    
    Returns:
        清理的文件数
    """
    cache_dir = Path(settings.CACHE_DIR)
    if not cache_dir.exists():
        return 0
    
    # 收集所有缓存项及其修改时间
    items = []
    for item in cache_dir.iterdir():
        if not item.is_dir():
            continue
        audio_file = item / f"{item.name}.opus"
        if audio_file.exists():
            items.append((item, audio_file.stat().st_mtime))
    
    # 按修改时间排序（旧的在前）
    items.sort(key=lambda x: x[1])
    
    # 计算当前总大小
    total_bytes = 0
    for item, _ in items:
        for f in item.glob("*"):
            if f.is_file():
                total_bytes += f.stat().st_size
    
    max_bytes = max_size_mb * 1024 * 1024
    deleted = 0
    
    for item, _ in items:
        if total_bytes <= max_bytes:
            break
        # 删除这个缓存
        size = sum(f.stat().st_size for f in item.glob("*") if f.is_file())
        shutil.rmtree(item, ignore_errors=True)
        total_bytes -= size
        deleted += 1
        logger.debug(f"🧹 容量删除: {item.name} ({size / 1024 / 1024:.1f}MB)")
    
    return deleted