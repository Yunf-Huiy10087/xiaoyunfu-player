"""
小云浮音视频处理服务 - 插件客户端

职责：
1. 封装调用插件端 API 的 HTTP 客户端
2. 处理 Cookie 传递（从数据库读取默认 Cookie）
3. 统一错误处理

文件位置: control/app/services/plugin_client.py
"""

import json
from typing import Dict, Any, List, Optional

import httpx
from app.core.config import settings
from app.core.database import get_account
from app.utils.logger import get_logger

logger = get_logger("plugin_client")

# ============================================================
# 1. 默认插件端点配置
# ============================================================

# 从配置读取插件端点
PLUGIN_ENDPOINTS = settings.get_all_plugin_endpoints()
DEFAULT_PLUGIN_URL = "http://plugin:5287"


# ============================================================
# 2. Cookie 管理
# ============================================================

def get_default_cookie(user_id: int, source: str) -> str:
    """
    获取用户默认的插件 Cookie
    
    Args:
        user_id: 用户ID
        source: 插件名称（如 bilibili）
    
    Returns:
        Cookie 字符串，如果不存在返回空字符串
    """
    account = get_account(user_id, source)
    if not account:
        return ""
    return account.get("cookie", "")


# ============================================================
# 3. 插件客户端
# ============================================================

class PluginClient:
    """
    插件客户端
    
    封装所有调用插件端的 HTTP 请求
    """
    
    def __init__(self, plugin_url: Optional[str] = None):
        """
        初始化插件客户端
        
        Args:
            plugin_url: 插件服务URL，默认从配置读取
        """
        self.plugin_url = plugin_url or DEFAULT_PLUGIN_URL
        self.timeout = 30
        self.logger = logger
        
        self.logger.info(f"🔌 插件客户端初始化: {self.plugin_url}")
    
    def get_plugin_url(self, source: str) -> str:
        """
        获取指定插件的端点地址
        
        Args:
            source: 插件名称
        
        Returns:
            插件URL
        """
        return PLUGIN_ENDPOINTS.get(source, self.plugin_url)
    
    # ============================================================
    # 3.1 元数据接口
    # ============================================================
    
    async def get_meta(self, source: str) -> Dict[str, Any]:
        """
        获取插件元数据
        
        Args:
            source: 插件名称
        
        Returns:
            插件元数据字典
        """
        url = f"{self.get_plugin_url(source)}/api/v1/meta"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            self.logger.error(f"⏰ 获取元数据超时: {source}")
            return {"error": "请求超时"}
        except httpx.HTTPStatusError as e:
            self.logger.error(f"❌ 获取元数据失败: {source} - {e.response.status_code}")
            return {"error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            self.logger.error(f"❌ 获取元数据异常: {source} - {e}")
            return {"error": str(e)}
    
    async def get_all_meta(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有插件的元数据
        
        Returns:
            {source: meta_dict}
        """
        result = {}
        # 从配置中获取所有插件端点
        for source in PLUGIN_ENDPOINTS.keys():
            meta = await self.get_meta(source)
            if meta and "error" not in meta:
                result[source] = meta
        return result
    
    # ============================================================
    # 3.2 认证接口
    # ============================================================
    
    async def auth(
        self,
        source: str,
        method: str,
        data: Dict[str, Any],
        user_id: int = 0
    ) -> Dict[str, Any]:
        """
        调用插件认证接口
        
        Args:
            source: 插件名称
            method: 登录方式ID
            data: 登录数据
            user_id: 用户ID（用于获取默认Cookie）
        
        Returns:
            认证结果
        """
        url = f"{self.get_plugin_url(source)}/api/v1/auth"
        
        # 如果用户已有该平台的 Cookie，传递给插件端
        cookie = get_default_cookie(user_id, source) if user_id > 0 else ""
        
        request_data = {
            "method": method,
            "data": data
        }
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                headers = {}
                if cookie:
                    headers["X-Plugin-Cookie"] = cookie
                
                resp = await client.post(
                    url,
                    json=request_data,
                    headers=headers
                )
                resp.raise_for_status()
                result = resp.json()
                self.logger.info(f"✅ 认证请求成功: {source} ({method})")
                return result
        except httpx.TimeoutException:
            self.logger.error(f"⏰ 认证超时: {source}")
            return {"success": False, "error": "请求超时"}
        except httpx.HTTPStatusError as e:
            self.logger.error(f"❌ 认证失败: {source} - {e.response.status_code}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            self.logger.error(f"❌ 认证异常: {source} - {e}")
            return {"success": False, "error": str(e)}
    
    # ============================================================
    # 3.3 搜索接口
    # ============================================================
    
    async def search(
        self,
        source: str,
        keyword: str,
        limit: int = 20,
        user_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        调用插件搜索接口
        
        Args:
            source: 插件名称
            keyword: 搜索关键词
            limit: 返回数量
            user_id: 用户ID（用于获取默认Cookie）
        
        Returns:
            搜索结果列表
        """
        url = f"{self.get_plugin_url(source)}/api/v1/search"
        
        # 获取用户在该平台的 Cookie
        cookie = get_default_cookie(user_id, source) if user_id > 0 else ""
        
        request_data = {
            "keyword": keyword,
            "limit": limit
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {}
                if cookie:
                    headers["X-Plugin-Cookie"] = cookie
                
                resp = await client.post(
                    url,
                    json=request_data,
                    headers=headers
                )
                resp.raise_for_status()
                result = resp.json()
                
                # 检查返回结果
                if result.get("code") == 200:
                    return result.get("data", [])
                else:
                    self.logger.warning(f"搜索返回错误: {source} - {result.get('message', '未知错误')}")
                    return []
        except httpx.TimeoutException:
            self.logger.error(f"⏰ 搜索超时: {source}")
            return []
        except httpx.HTTPStatusError as e:
            self.logger.error(f"❌ 搜索失败: {source} - {e.response.status_code}")
            return []
        except Exception as e:
            self.logger.error(f"❌ 搜索异常: {source} - {e}")
            return []
    
    # ============================================================
    # 3.4 获取歌曲接口
    # ============================================================
    
    async def get_song(
        self,
        source: str,
        song_id: str,
        user_id: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        调用插件获取歌曲接口
        
        Args:
            source: 插件名称
            song_id: 歌曲ID
            user_id: 用户ID（用于获取默认Cookie）
        
        Returns:
            歌曲信息字典，如果失败返回 None
        """
        url = f"{self.get_plugin_url(source)}/api/v1/song"
        
        cookie = get_default_cookie(user_id, source) if user_id > 0 else ""
        
        request_data = {
            "song_id": song_id
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {}
                if cookie:
                    headers["X-Plugin-Cookie"] = cookie
                
                resp = await client.post(
                    url,
                    json=request_data,
                    headers=headers
                )
                resp.raise_for_status()
                result = resp.json()
                
                if result.get("code") == 200:
                    return result.get("data")
                else:
                    self.logger.warning(f"获取歌曲失败: {source} - {result.get('message', '未知错误')}")
                    return None
        except httpx.TimeoutException:
            self.logger.error(f"⏰ 获取歌曲超时: {source}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"❌ 获取歌曲失败: {source} - {e.response.status_code}")
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取歌曲异常: {source} - {e}")
            return None
    
    # ============================================================
    # 3.5 获取歌词接口
    # ============================================================
    
    async def get_lyric(
        self,
        source: str,
        song_id: str,
        user_id: int = 0
    ) -> Dict[str, str]:
        """
        调用插件获取歌词接口
        
        Args:
            source: 插件名称
            song_id: 歌曲ID
            user_id: 用户ID（用于获取默认Cookie）
        
        Returns:
            歌词字典 {"lyric": "", "tlyric": "", "klyric": ""}
        """
        url = f"{self.get_plugin_url(source)}/api/v1/lyric"
        
        cookie = get_default_cookie(user_id, source) if user_id > 0 else ""
        
        request_data = {
            "song_id": song_id
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {}
                if cookie:
                    headers["X-Plugin-Cookie"] = cookie
                
                resp = await client.post(
                    url,
                    json=request_data,
                    headers=headers
                )
                resp.raise_for_status()
                result = resp.json()
                
                if result.get("code") == 200:
                    return result.get("data", {"lyric": "纯音乐", "tlyric": "", "klyric": ""})
                else:
                    return {"lyric": "纯音乐", "tlyric": "", "klyric": ""}
        except Exception as e:
            self.logger.error(f"❌ 获取歌词异常: {source} - {e}")
            return {"lyric": "纯音乐", "tlyric": "", "klyric": ""}
    
    # ============================================================
    # 3.6 批量获取（便捷方法）
    # ============================================================
    
    async def search_all(
        self,
        keyword: str,
        limit: int = 20,
        user_id: int = 0
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        搜索所有插件
        
        Args:
            keyword: 搜索关键词
            limit: 每个插件返回数量
            user_id: 用户ID
        
        Returns:
            {source: results}
        """
        result = {}
        for source in PLUGIN_ENDPOINTS.keys():
            try:
                items = await self.search(source, keyword, limit, user_id)
                if items:
                    result[source] = items
            except Exception as e:
                self.logger.error(f"搜索 {source} 失败: {e}")
        return result


# ============================================================
# 4. 全局单例
# ============================================================

plugin_client = PluginClient()