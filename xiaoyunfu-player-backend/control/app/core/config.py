"""
小云浮音视频处理服务 - 控制端配置管理
从统一配置文件 (volumes/config/config.json) 中读取 control 部分的配置

文件位置: control/app/core/config.py
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
        
        with open(CONFIG_PATH, 'r', encoding='utf-8-sig') as f:
            _config_cache = json.load(f)
    
    return _config_cache


def get_control_config() -> Dict[str, Any]:
    """
    获取控制端的配置
    
    Returns:
        控制端配置字典
    """
    full = load_full_config()
    return full.get("control", {})


# ============================================================
# 3. 配置对象（方便代码提示）
# ============================================================

class ControlSettings:
    """
    控制端配置对象
    使用方式：settings.PORT, settings.DEBUG, ...
    """
    
    def __init__(self):
        self._config = get_control_config()
    
    @property
    def PORT(self) -> int:
        return self._config.get("port", 2587)
    
    @property
    def DEBUG(self) -> bool:
        return self._config.get("debug", False)
    
    @property
    def DB_PATH(self) -> str:
        return self._config.get("db_path", "/app/data/db/xiaoyunfu.db")
    
    @property
    def UPLOAD_DIR(self) -> str:
        return self._config.get("upload_dir", "/app/uploads")
    
    @property
    def CACHE_DIR(self) -> str:
        return self._config.get("cache_dir", "/app/cache")
    
    @property
    def SECRET_KEY(self) -> str:
        return self._config.get("secret_key", "change-me-in-production")
    
    @property
    def TOKEN_EXPIRE_DAYS(self) -> int:
        return self._config.get("token_expire_days", 30)
    
    def get_plugin_endpoint(self, source: str) -> str:
        """
        获取指定插件的端点地址
        
        Args:
            source: 插件名称（如 "bilibili"）
        
        Returns:
            插件服务的URL
        """
        endpoints = self._config.get("plugin_endpoints", {})
        return endpoints.get(source, f"http://plugin:5287")
    
    def get_all_plugin_endpoints(self) -> Dict[str, str]:
        """获取所有插件的端点地址"""
        return self._config.get("plugin_endpoints", {})


# ============================================================
# 4. 全局单例
# ============================================================

settings = ControlSettings()