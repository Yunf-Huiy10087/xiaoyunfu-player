"""
小云浮音视频处理服务 - 插件基类定义
所有音乐源插件必须继承此类并实现所有抽象方法

文件位置: plugin/app/base.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ============================================================
# 1. 数据结构定义
# ============================================================

@dataclass
class SearchResult:
    """
    搜索结果条目
    
    当用户搜索歌曲时，插件返回的列表中的每一项
    """
    id: str                          # 歌曲唯一ID（在对应平台上的ID）
    name: str                        # 歌曲名称
    singer: str                      # 歌手/UP主名称
    album: str = ""                  # 专辑名称（可选）
    duration: int = 0                # 歌曲时长（秒）
    source: str = ""                 # 来源（由插件自动填入）
    cover_url: str = ""              # 封面图片URL


@dataclass
class SongInfo:
    """
    歌曲详情（包含播放链接）
    
    当用户点击播放时，插件返回的完整歌曲信息
    """
    id: str                          # 歌曲唯一ID
    name: str                        # 歌曲名称
    singer: str                      # 歌手/UP主
    album: str = ""                  # 专辑名称
    duration: int = 0                # 歌曲时长（秒）
    source: str = ""                 # 来源（由插件自动填入）
    cover_url: str = ""              # 封面图片URL
    raw_url: str = ""                # 原始音频URL（m4a / flac / mp3）
    lyric: str = ""                  # 歌词（LRC格式）
    tlyric: str = ""                 # 翻译歌词
    klyric: str = ""                 # 罗马音歌词
    need_transcode: bool = True      # 是否需要转码为Opus


# ============================================================
# 2. 插件基类（所有插件必须继承）
# ============================================================

class MusicSourcePlugin(ABC):
    """
    音乐源插件基类
    
    所有插件必须：
    1. 继承这个类
    2. 设置类变量（source, display_name, version, author）
    3. 实现所有抽象方法（search, get_song, auth）
    
    插件文件示例：volumes/plugin/codes/bilibili.py
    """
    
    # ============================================================
    # 2.1 插件元数据（必填！）
    # ============================================================
    
    # 插件唯一标识（也是控制端调用时的名称）
    # 例如: "bilibili", "netease", "kuwo", "qq"
    source: str = "unknown"
    
    # 在网页上显示的名称
    display_name: str = "未知音乐源"
    
    # 插件版本号
    version: str = "1.0.0"
    
    # 插件作者
    author: str = "未知作者"
    
    # 图标名称（前端用来显示对应图标）
    icon: str = "link"
    
    
    # ============================================================
    # 2.2 登录方式声明（必填！）
    # ============================================================
    
    # 声明这个插件支持哪些登录方式
    # 控制端会根据这个信息，让前端动态生成登录界面
    #
    # 格式：
    # [
    #     {
    #         "id": "password",          # 登录方式ID
    #         "name": "账号密码",         # 显示名称
    #         "description": "输入账号和密码登录",
    #         "fields": [                # 需要用户填的字段
    #             {"name": "username", "label": "用户名", "type": "text", "required": True},
    #             {"name": "password", "label": "密码", "type": "password", "required": True}
    #         ]
    #     },
    #     {
    #         "id": "qr_code",
    #         "name": "二维码扫码",
    #         "description": "使用APP扫码登录",
    #         "fields": []               # 不需要用户填任何东西
    #     },
    #     {
    #         "id": "manual",
    #         "name": "手动粘贴Cookie",
    #         "fields": [
    #             {"name": "cookie", "label": "Cookie", "type": "textarea", "required": True}
    #         ]
    #     }
    # ]
    auth_methods: List[Dict[str, Any]] = []
    
    # Cookie格式说明（显示给用户看，告诉他Cookie长什么样）
    cookie_format: str = "key1=value1; key2=value2"
    
    
    # ============================================================
    # 2.3 抽象方法（子类必须实现！）
    # ============================================================
    
    @abstractmethod
    async def search(self, keyword: str, limit: int = 20, cookie: str = "") -> List[SearchResult]:
        """
        搜索歌曲
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
            cookie: 控制端传来的Cookie（用于需要登录才能搜索的平台）
        
        Returns:
            SearchResult 列表
        """
        pass
    
    
    @abstractmethod
    async def get_song(self, song_id: str, cookie: str = "") -> Optional[SongInfo]:
        """
        获取歌曲详情（包含播放链接）
        
        Args:
            song_id: 歌曲ID（由 search 方法返回的 id）
            cookie: 控制端传来的Cookie
        
        Returns:
            SongInfo 对象，如果获取失败返回 None
        """
        pass
    
    
    @abstractmethod
    async def get_lyric(self, song_id: str, cookie: str = "") -> Dict[str, str]:
        """
        获取歌词（可选实现）
        
        Args:
            song_id: 歌曲ID
            cookie: 控制端传来的Cookie
        
        Returns:
            {"lyric": "LRC格式歌词", "tlyric": "翻译歌词", "klyric": "罗马音歌词"}
            如果没有歌词，返回 {"lyric": "纯音乐", "tlyric": "", "klyric": ""}
        """
        # 默认返回"纯音乐"，子类可以覆盖此方法实现真正的歌词获取
        return {"lyric": "纯音乐", "tlyric": "", "klyric": ""}
    
    
    @abstractmethod
    async def auth(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理登录请求
        
        控制端收到用户登录请求后，会转发给插件的这个方法
        
        Args:
            method: 登录方式ID（对应 auth_methods 里的 id）
            data: 用户填写的表单数据
        
        Returns:
            登录成功时:
                {"success": True, "cookie": "SESSDATA=xxx; bili_jct=xxx", "user_info": {...}}
            登录失败时:
                {"success": False, "error": "错误信息"}
            需要继续轮询时（如二维码）:
                {"status": "waiting", "message": "请扫描二维码", "qrcode_key": "xxx"}
        """
        pass
    
    
    # ============================================================
    # 2.4 可选：工具方法
    # ============================================================
    
    @staticmethod
    def clean_html(text: str) -> str:
        """
        清理HTML标签（给子类使用的工具方法）
        
        很多平台的API返回的标题包含HTML标签（如 <em>周杰伦</em>）
        这个方法可以去掉这些标签
        """
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace("&quot;", '"').replace("&#39;", "'")
        text = text.replace("&amp;", "&").replace("&lt;", "<")
        text = text.replace("&gt;", ">").replace("&nbsp;", " ")
        return text