"""
小云浮音视频处理服务 - 插件端配置管理
从统一配置文件 (volumes/config/config.json) 中读取 plugin 部分的配置

文件位置: plugin/app/core/config.py
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


def get_plugin_config() -> Dict[str, Any]:
    """
    获取插件端的配置
    
    Returns:
        插件端配置字典
    """
    full = load_full_config()
    return full.get("plugin", {})


# ============================================================
# 3. 配置对象（方便代码提示）
# ============================================================

class PluginSettings:
    """
    插件端配置对象
    使用方式：settings.PORT, settings.DEBUG, ...
    """
    
    def __init__(self):
        self._config = get_plugin_config()
    
    @property
    def PORT(self) -> int:
        return self._config.get("port", 5287)
    
    @property
    def DEBUG(self) -> bool:
        return self._config.get("debug", False)
    
    @property
    def PLUGIN_CODE_DIR(self) -> str:
        """
        插件代码目录（存放 *.py 插件文件）
        对应 volumes/plugin/codes/
        """
        return self._config.get("plugin_code_dir", "/app/plugin/codes")
    
    @property
    def PLUGIN_CONFIG_DIR(self) -> str:
        """
        插件配置目录（存放 *.json 插件配置文件）
        对应 volumes/plugin/configs/
        """
        return self._config.get("plugin_config_dir", "/app/plugin/configs")
    
    def get_plugin_config_path(self, source: str) -> str:
        """
        获取指定插件的配置文件路径
        
        Args:
            source: 插件名称（如 "bilibili"）
        
        Returns:
            插件配置文件的完整路径
        """
        return os.path.join(self.PLUGIN_CONFIG_DIR, f"{source}.json")


# ============================================================
# 4. 全局单例
# ============================================================

settings = PluginSettings()