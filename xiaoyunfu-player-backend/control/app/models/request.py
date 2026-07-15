"""
小云浮音视频处理服务 - 请求模型

定义所有 API 接口的请求体数据结构
使用 Pydantic 进行数据验证

文件位置: control/app/models/request.py
"""

import re
from typing import Optional, List
from pydantic import BaseModel, Field, validator


# ============================================================
# 1. 认证相关
# ============================================================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名", min_length=2, max_length=20)
    password: str = Field(..., description="密码", min_length=4, max_length=100)
    
    @validator('username')
    def validate_username(cls, v):
        """用户名：只允许中文、英文、数字、下划线、横线"""
        pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9_-]{2,20}$'
        if not re.match(pattern, v):
            raise ValueError('用户名只允许中文、英文、数字、下划线、横线，长度2-20')
        return v


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., description="用户名", min_length=2, max_length=20)
    password: str = Field(..., description="密码", min_length=4, max_length=100)
    
    @validator('username')
    def validate_username(cls, v):
        pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9_-]{2,20}$'
        if not re.match(pattern, v):
            raise ValueError('用户名只允许中文、英文、数字、下划线、横线，长度2-20')
        return v


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码", min_length=4)
    new_password: str = Field(..., description="新密码", min_length=4, max_length=100)


class ResetPasswordRequest(BaseModel):
    """重置密码请求（管理员）"""
    new_password: str = Field(..., description="新密码", min_length=4, max_length=100)


# ============================================================
# 2. 音乐相关
# ============================================================

class SearchRequest(BaseModel):
    """搜索请求"""
    keyword: str = Field(..., description="搜索关键词", min_length=1)
    source: str = Field("all", description="来源（all/netease/bilibili/kuwo/qq/local）")
    limit: int = Field(20, description="返回数量", ge=1, le=100)


class PlayRequest(BaseModel):
    """播放请求"""
    id: str = Field(..., description="歌曲ID")
    source: str = Field(..., description="来源（netease/bilibili/kuwo/qq/local）")


# ============================================================
# 3. 歌单相关
# ============================================================

class CreatePlaylistRequest(BaseModel):
    """创建歌单请求"""
    name: str = Field(..., description="歌单名称", min_length=1, max_length=100)
    is_public: bool = Field(True, description="是否公开")
    description: str = Field("", description="描述", max_length=500)


class UpdatePlaylistRequest(BaseModel):
    """更新歌单请求"""
    name: Optional[str] = Field(None, description="歌单名称", min_length=1, max_length=100)
    is_public: Optional[bool] = Field(None, description="是否公开")
    description: Optional[str] = Field(None, description="描述", max_length=500)


class AddSongRequest(BaseModel):
    """添加歌曲到歌单请求"""
    song_id: str = Field(..., description="歌曲ID")
    source: str = Field(..., description="来源")
    title: str = Field(..., description="歌曲名称")
    artist: str = Field("", description="艺术家")
    album: str = Field("", description="专辑")
    cover_url: str = Field("", description="封面URL")
    duration: int = Field(0, description="时长（秒）", ge=0)


# ============================================================
# 4. 上传相关
# ============================================================

class UploadUrlRequest(BaseModel):
    """URL上传请求"""
    url: str = Field(..., description="文件URL")
    title: str = Field("", description="自定义标题", max_length=100)
    
    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL必须以 http:// 或 https:// 开头')
        return v


# ============================================================
# 5. 插件相关
# ============================================================

class PluginAuthRequest(BaseModel):
    """插件认证请求"""
    source: str = Field(..., description="插件名称")
    method: str = Field(..., description="登录方式ID")
    data: dict = Field(default_factory=dict, description="登录数据")


class PluginSearchRequest(BaseModel):
    """插件搜索请求"""
    keyword: str = Field(..., description="搜索关键词", min_length=1)
    limit: int = Field(20, description="返回数量", ge=1, le=100)
    cookie: str = Field("", description="Cookie")


class PluginSongRequest(BaseModel):
    """插件获取歌曲请求"""
    song_id: str = Field(..., description="歌曲ID")
    cookie: str = Field("", description="Cookie")


# ============================================================
# 6. 账号绑定相关
# ============================================================

class BindAccountRequest(BaseModel):
    """绑定账号请求"""
    platform: str = Field(..., description="平台名称（bilibili/netease/kuwo/qq）")
    cookie: str = Field(..., description="Cookie", min_length=1)
    is_default: bool = Field(False, description="是否设为默认搜索源")


# ============================================================
# 7. B站相关
# ============================================================

class BilibiliPagesRequest(BaseModel):
    """B站分P请求"""
    bvid: str = Field(..., description="BV号")


# ============================================================
# 8. 队列相关
# ============================================================

class QueueTaskRequest(BaseModel):
    """队列任务请求"""
    task_id: str = Field(..., description="任务ID")
    action: str = Field(..., description="操作（pause/resume/cancel）")


# ============================================================
# 9. 分页相关（通用）
# ============================================================

class PageRequest(BaseModel):
    """分页请求"""
    page: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页数量", ge=1, le=100)