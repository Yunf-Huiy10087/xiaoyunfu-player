"""
小云浮音视频处理服务 - 响应模型

定义所有 API 接口的统一返回格式
所有接口返回格式：{"code": 200, "message": "成功", "data": {...}}

文件位置: control/app/models/response.py
"""

from typing import Optional, Any, List, Dict, Generic, TypeVar, Union
from pydantic import BaseModel, Field

# 泛型类型变量（用于 ListResponse 和 PageResponse）
T = TypeVar('T')


# ============================================================
# 1. 统一响应基类
# ============================================================

class BaseResponse(BaseModel):
    """
    统一响应基类
    
    所有 API 接口都使用这个格式返回：
    {
        "code": 200,
        "message": "成功",
        "data": {...}
    }
    """
    code: int = Field(200, description="状态码（200=成功，其他=错误）")
    message: str = Field("成功", description="状态信息")
    data: Optional[Any] = Field(None, description="响应数据")


class SuccessResponse(BaseResponse):
    """成功响应（快捷方式）"""
    code: int = 200
    message: str = "成功"


class ErrorResponse(BaseResponse):
    """错误响应（快捷方式）"""
    code: int = 400
    message: str = "请求失败"


# ============================================================
# 2. 分页响应
# ============================================================

class PageInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")


class PageResponse(BaseResponse, Generic[T]):
    """
    分页响应
    
    返回格式：
    {
        "code": 200,
        "message": "成功",
        "data": {
            "items": [...],
            "page": 1,
            "page_size": 20,
            "total": 100,
            "total_pages": 5
        }
    }
    """
    data: Optional[Dict[str, Any]] = Field(None, description="分页数据")


class ListResponse(BaseResponse, Generic[T]):
    """
    列表响应
    
    返回格式：
    {
        "code": 200,
        "message": "成功",
        "data": [...]
    }
    """
    data: Optional[List[T]] = Field(None, description="数据列表")


# ============================================================
# 3. 认证响应
# ============================================================

class LoginResponseData(BaseModel):
    """登录响应数据"""
    token: str = Field(..., description="JWT Token")
    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    is_admin: bool = Field(False, description="是否管理员")


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    is_admin: bool = Field(False, description="是否管理员")
    created_at: Optional[str] = Field(None, description="注册时间")


# ============================================================
# 4. 音乐响应
# ============================================================

class SongResponse(BaseModel):
    """歌曲信息响应"""
    id: str = Field(..., description="歌曲ID")
    name: str = Field(..., description="歌曲名称")
    singer: str = Field(..., description="歌手")
    album: Optional[str] = Field(None, description="专辑")
    duration: int = Field(0, description="时长（秒）")
    source: str = Field(..., description="来源")
    cover_url: Optional[str] = Field(None, description="封面URL")
    url: Optional[str] = Field(None, description="播放URL")
    lyric: Optional[str] = Field(None, description="歌词（LRC格式）")
    tlyric: Optional[str] = Field(None, description="翻译歌词")


class SearchResponseData(BaseModel):
    """搜索结果响应"""
    id: str = Field(..., description="歌曲ID")
    name: str = Field(..., description="歌曲名称")
    singer: str = Field(..., description="歌手")
    album: Optional[str] = Field(None, description="专辑")
    duration: int = Field(0, description="时长（秒）")
    source: str = Field(..., description="来源")
    cover_url: Optional[str] = Field(None, description="封面URL")


class PlayResponseData(BaseModel):
    """播放响应数据"""
    id: str = Field(..., description="歌曲ID")
    name: str = Field(..., description="歌曲名称")
    singer: str = Field(..., description="歌手")
    cover_url: Optional[str] = Field(None, description="封面URL")
    duration: int = Field(0, description="时长（秒）")
    url: str = Field(..., description="播放URL")
    lyric: Optional[str] = Field(None, description="歌词（LRC格式）")
    tlyric: Optional[str] = Field(None, description="翻译歌词")
    # 队列相关
    queued: bool = Field(False, description="是否已加入队列")
    status: Optional[str] = Field(None, description="队列状态（排队中/转码中/完成/失败）")
    message: Optional[str] = Field(None, description="提示信息")


# ============================================================
# 5. 歌单响应
# ============================================================

class PlaylistResponse(BaseModel):
    """歌单响应"""
    id: int = Field(..., description="歌单ID")
    name: str = Field(..., description="歌单名称")
    user_id: int = Field(..., description="创建者ID")
    is_public: bool = Field(True, description="是否公开")
    description: Optional[str] = Field(None, description="描述")
    cover_url: Optional[str] = Field(None, description="封面URL")
    created_at: str = Field(..., description="创建时间")
    song_count: Optional[int] = Field(0, description="歌曲数量")


class PlaylistSongResponse(BaseModel):
    """歌单歌曲响应"""
    id: int = Field(..., description="记录ID")
    playlist_id: int = Field(..., description="歌单ID")
    song_id: str = Field(..., description="歌曲ID")
    source: str = Field(..., description="来源")
    title: str = Field(..., description="歌曲名称")
    artist: str = Field(..., description="艺术家")
    album: Optional[str] = Field(None, description="专辑")
    cover_url: Optional[str] = Field(None, description="封面URL")
    duration: int = Field(0, description="时长（秒）")
    position: int = Field(0, description="排序位置")


# ============================================================
# 6. 上传响应
# ============================================================

class UploadFileResponse(BaseModel):
    """上传文件响应"""
    filename: str = Field(..., description="文件名")
    title: str = Field(..., description="标题")
    size: int = Field(..., description="文件大小（字节）")
    file_type: str = Field(..., description="文件类型")


# ============================================================
# 7. 队列响应
# ============================================================

class QueueTaskResponse(BaseModel):
    """队列任务响应"""
    ck: str = Field(..., description="缓存键")
    name: str = Field(..., description="歌曲名称")
    status: str = Field(..., description="状态（排队中/转码中/完成/失败）")
    source: str = Field(..., description="来源")
    sid: str = Field(..., description="歌曲ID")
    user_id: int = Field(..., description="用户ID")
    singer: Optional[str] = Field(None, description="歌手")
    cover_url: Optional[str] = Field(None, description="封面URL")
    duration: int = Field(0, description="时长（秒）")


# ============================================================
# 8. 插件响应
# ============================================================

class PluginMethodField(BaseModel):
    """插件登录方式字段"""
    name: str = Field(..., description="字段名")
    label: str = Field(..., description="显示名称")
    type: str = Field(..., description="字段类型（text/password/textarea/hidden）")
    required: bool = Field(True, description="是否必填")
    placeholder: Optional[str] = Field(None, description="占位符")


class PluginMethod(BaseModel):
    """插件登录方式"""
    id: str = Field(..., description="方式ID")
    name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    fields: List[PluginMethodField] = Field(default_factory=list, description="字段列表")


class PluginMetaResponse(BaseModel):
    """插件元数据响应"""
    source: str = Field(..., description="来源名称")
    display_name: str = Field(..., description="显示名称")
    version: str = Field(..., description="版本号")
    author: str = Field(..., description="作者")
    icon: str = Field("link", description="图标名称")
    auth_methods: List[PluginMethod] = Field(default_factory=list, description="登录方式")
    cookie_format: str = Field("", description="Cookie格式说明")


# ============================================================
# 9. 账号绑定响应
# ============================================================

class AccountResponse(BaseModel):
    """账号绑定响应"""
    id: int = Field(..., description="记录ID")
    platform: str = Field(..., description="平台名称")
    is_default: bool = Field(False, description="是否默认搜索源")


# ============================================================
# 10. 健康检查响应
# ============================================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="状态（ok/error）")
    port: Optional[int] = Field(None, description="监听端口")
    debug: Optional[bool] = Field(None, description="调试模式")
    plugins: Optional[List[str]] = Field(None, description="已加载插件列表")
    queue_size: Optional[int] = Field(None, description="队列大小")
    cache_mb: Optional[float] = Field(None, description="缓存大小（MB）")


# ============================================================
# 11. 辅助函数
# ============================================================

def success(data: Any = None, message: str = "成功") -> dict:
    """
    生成成功响应
    
    Args:
        data: 响应数据
        message: 成功信息
    
    Returns:
        响应字典
    """
    return {
        "code": 200,
        "message": message,
        "data": data
    }


def error(message: str = "请求失败", code: int = 400) -> dict:
    """
    生成错误响应
    
    Args:
        message: 错误信息
        code: 错误码
    
    Returns:
        响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": None
    }


def page_data(items: List[Any], page: int, page_size: int, total: int) -> dict:
    """
    生成分页数据
    
    Args:
        items: 数据列表
        page: 当前页码
        page_size: 每页数量
        total: 总记录数
    
    Returns:
        分页数据字典
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }