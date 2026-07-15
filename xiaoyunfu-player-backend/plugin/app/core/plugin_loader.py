"""
小云浮音视频处理服务 - 插件加载器

职责：
1. 扫描 plugins/codes/ 目录下的所有 .py 文件
2. 动态导入并实例化插件
3. 管理插件生命周期

文件位置: plugin/app/core/plugin_loader.py
"""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from app.base import MusicSourcePlugin
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("plugin_loader")


class PluginLoader:
    """
    插件加载器
    
    加载 volumes/plugin/codes/ 目录下的所有 .py 文件，
    每个文件必须包含一个名为 Plugin 的类，继承自 MusicSourcePlugin
    
    使用方式:
        loader = PluginLoader()
        loader.load_all()
        bilibili_plugin = loader.get("bilibili")
        plugins = loader.get_all()
    """
    
    def __init__(self):
        """初始化加载器"""
        self.plugins: Dict[str, MusicSourcePlugin] = {}
        self.plugin_classes: Dict[str, Type[MusicSourcePlugin]] = {}
        self.load_errors: Dict[str, str] = {}
        
        # 从配置读取插件目录
        self.code_dir = Path(settings.PLUGIN_CODE_DIR)
        self.config_dir = Path(settings.PLUGIN_CONFIG_DIR)
        
        logger.info(f"📂 插件代码目录: {self.code_dir}")
        logger.info(f"📂 插件配置目录: {self.config_dir}")
    
    def load_all(self) -> Dict[str, MusicSourcePlugin]:
        """
        加载所有插件
        
        Returns:
            插件实例字典 {source_name: plugin_instance}
        """
        self.plugins = {}
        self.load_errors = {}
        
        if not self.code_dir.exists():
            logger.warning(f"⚠️ 插件目录不存在: {self.code_dir}")
            return self.plugins
        
        # 扫描所有 .py 文件
        py_files = list(self.code_dir.glob("*.py"))
        logger.info(f"📦 发现 {len(py_files)} 个 Python 文件")
        
        for py_file in py_files:
            if py_file.name.startswith("__"):
                continue
            self._load_plugin_file(py_file)
        
        # 加载完成后输出统计信息
        if self.load_errors:
            logger.warning(f"⚠️ {len(self.load_errors)} 个插件加载失败")
            for source, error in self.load_errors.items():
                logger.warning(f"   ❌ {source}: {error}")
        
        if self.plugins:
            logger.info(f"✅ 成功加载 {len(self.plugins)} 个插件: {list(self.plugins.keys())}")
        else:
            logger.warning("⚠️ 没有加载到任何插件")
        
        return self.plugins
    
    def _load_plugin_file(self, py_file: Path):
        """
        加载单个插件文件
        
        Args:
            py_file: .py 文件路径
        """
        module_name = py_file.stem  # 文件名（不含 .py）
        
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(
                f"plugins.{module_name}",
                py_file
            )
            if not spec or not spec.loader:
                self.load_errors[module_name] = "无法创建模块规范"
                return
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugins.{module_name}"] = module
            spec.loader.exec_module(module)
            
            # 查找 Plugin 类
            if not hasattr(module, "Plugin"):
                self.load_errors[module_name] = "缺少 Plugin 类"
                return
            
            plugin_class = getattr(module, "Plugin")
            
            # 验证是否继承自 MusicSourcePlugin
            if not inspect.isclass(plugin_class):
                self.load_errors[module_name] = "Plugin 不是类"
                return
            
            if not issubclass(plugin_class, MusicSourcePlugin):
                self.load_errors[module_name] = "Plugin 未继承 MusicSourcePlugin"
                return
            
            # 检查是否设置了 source 属性
            if not plugin_class.source or plugin_class.source == "unknown":
                self.load_errors[module_name] = "Plugin 未设置 source 属性"
                return
            
            # 实例化插件
            plugin_instance = plugin_class()
            
            # 如果有配置目录，加载插件自身配置
            self._load_plugin_config(plugin_instance)
            
            # 注册插件
            self.plugins[plugin_instance.source] = plugin_instance
            self.plugin_classes[plugin_instance.source] = plugin_class
            
            logger.info(
                f"✅ 加载插件: {plugin_instance.display_name} "
                f"v{plugin_instance.version} by {plugin_instance.author}"
            )
            
        except ImportError as e:
            self.load_errors[module_name] = f"导入错误: {e}"
            logger.error(f"❌ 导入插件 {module_name} 失败: {e}")
        except Exception as e:
            self.load_errors[module_name] = str(e)
            logger.error(f"❌ 加载插件 {module_name} 异常: {e}", exc_info=True)
    
    def _load_plugin_config(self, plugin: MusicSourcePlugin):
        """
        为插件加载配置文件
        
        Args:
            plugin: 插件实例
        """
        source = plugin.source
        config_file = self.config_dir / f"{source}.json"
        
        if config_file.exists():
            try:
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                # 将配置注入到插件实例
                if hasattr(plugin, 'config'):
                    plugin.config = config_data
                else:
                    # 如果插件没有 config 属性，动态添加
                    setattr(plugin, 'config', config_data)
                logger.debug(f"📋 加载插件配置: {source} ({config_file})")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ 插件配置解析失败 {source}: {e}")
        else:
            # 配置文件不存在，使用空配置
            if not hasattr(plugin, 'config'):
                setattr(plugin, 'config', {})
            logger.debug(f"📋 插件 {source} 无配置文件，使用默认配置")
    
    # ============================================================
    # 查询方法
    # ============================================================
    
    def get(self, source: str) -> Optional[MusicSourcePlugin]:
        """
        根据来源名称获取插件
        
        Args:
            source: 插件来源名称（如 "bilibili"）
        
        Returns:
            插件实例，如果不存在返回 None
        """
        return self.plugins.get(source)
    
    def get_all(self) -> Dict[str, MusicSourcePlugin]:
        """
        获取所有插件
        
        Returns:
            所有插件字典
        """
        return self.plugins
    
    def get_names(self) -> List[str]:
        """
        获取所有插件名称列表
        
        Returns:
            插件名称列表
        """
        return list(self.plugins.keys())
    
    def get_plugin_meta(self, source: str) -> Optional[Dict[str, Any]]:
        """
        获取插件的元数据
        
        Args:
            source: 插件来源名称
        
        Returns:
            元数据字典，包含 display_name, version, author, auth_methods 等
        """
        plugin = self.get(source)
        if not plugin:
            return None
        
        return {
            "source": plugin.source,
            "display_name": plugin.display_name,
            "version": plugin.version,
            "author": plugin.author,
            "icon": getattr(plugin, 'icon', 'link'),
            "auth_methods": getattr(plugin, 'auth_methods', []),
            "cookie_format": getattr(plugin, 'cookie_format', '')
        }
    
    def get_all_meta(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有插件的元数据
        
        Returns:
            {source: meta_dict}
        """
        return {
            source: self.get_plugin_meta(source)
            for source in self.plugins.keys()
        }
    
    def is_loaded(self, source: str) -> bool:
        """
        检查插件是否已加载
        
        Args:
            source: 插件来源名称
        
        Returns:
            True 已加载，False 未加载
        """
        return source in self.plugins
    
    def reload(self, source: str) -> bool:
        """
        重新加载指定插件
        
        Args:
            source: 插件来源名称
        
        Returns:
            True 重新加载成功，False 失败
        """
        # 重新加载单个插件
        # 先找到对应的文件
        for py_file in self.code_dir.glob("*.py"):
            if py_file.stem == source or py_file.stem == source:
                # 从缓存中移除旧实例
                if source in self.plugins:
                    del self.plugins[source]
                if source in self.plugin_classes:
                    del self.plugin_classes[source]
                if source in self.load_errors:
                    del self.load_errors[source]
                
                # 重新加载
                self._load_plugin_file(py_file)
                return self.is_loaded(source)
        
        logger.warning(f"⚠️ 未找到插件文件: {source}")
        return False
    
    def reload_all(self) -> Dict[str, MusicSourcePlugin]:
        """
        重新加载所有插件
        
        Returns:
            所有插件实例
        """
        logger.info("🔄 重新加载所有插件...")
        # 清空现有插件
        self.plugins = {}
        self.plugin_classes = {}
        self.load_errors = {}
        # 重新加载
        return self.load_all()