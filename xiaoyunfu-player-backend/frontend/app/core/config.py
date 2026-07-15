"""
小云浮音视频处理服务 - 前端配置管理
从统一配置文件 (volumes/config/config.json) 中读取 frontend 部分的配置

文件位置: frontend/app/core/config.py
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# ============================================================
# 1. 配置路径
# ============================================================

# 配置文件路径（支持环境变量覆盖）
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.json")

# 如果本地开发没有设置环境变量，尝试相对路径
if not Path(CONFIG_PATH).exists():
    local_path = Path(__file__).parent.parent.parent.parent / "volumes" / "config" / "config.json"
    if local_path.exists():
        CONFIG_PATH = str(local_path)


# ============================================================
# 2. 配置缓存
# ============================================================

_config_cache: Optional[Dict[str, Any]] = None


def load_full_config() -> Dict[str, Any]:
    """
    加载完整配置文件
    
    Returns:
        完整配置字典
    """
    global _config_cache
    
    if _config_cache is None:
        if not Path(CONFIG_PATH).exists():
            raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config_cache = json.load(f)
    
    return _config_cache


def get_frontend_config() -> Dict[str, Any]:
    """
    获取前端的配置
    
    Returns:
        前端配置字典
    """
    full = load_full_config()
    return full.get("frontend", {})


# ============================================================
# 3. 配置对象（方便代码提示）
# ============================================================

class FrontendSettings:
    """
    前端配置对象
    使用方式：settings.WEB_PORT, settings.DEBUG, ...
    """
    
    def __init__(self):
        self._config = get_frontend_config()
    
    @property
    def WEB_PORT(self) -> int:
        """网页端口（供浏览器访问）"""
        return self._config.get("web_port", 8725)
    
    @property
    def MC_PORT(self) -> int:
        """MC服务端API端口（供Minecraft模组/插件调用）"""
        return self._config.get("mc_port", 8752)
    
    @property
    def CONTROL_URL(self) -> str:
        """控制端地址"""
        return self._config.get("control_url", "http://control:2587")
    
    @property
    def DEBUG(self) -> bool:
        return self._config.get("debug", False)


# ============================================================
# 4. 全局单例
# ============================================================

settings = FrontendSettings()