"""
小云浮音视频处理服务 - API 代理路由

职责：
1. 转发所有 /api/* 请求到控制端 (2587)
2. 处理认证头透传
3. 统一错误处理

文件位置: frontend/app/api/proxy.py
"""

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("api.proxy")
router = APIRouter(tags=["代理"])

# 创建 HTTP 客户端（复用连接）
client = httpx.AsyncClient(
    timeout=60.0,
    follow_redirects=True,
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=100)
)


@router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_to_control(path: str, request: Request):
    """
    代理转发所有 /api/* 请求到控制端
    
    Args:
        path: API 路径
        request: 原始请求对象
    """
    # 构建目标 URL
    target_url = f"{settings.CONTROL_URL}/api/{path}"
    
    # 获取请求体
    body = await request.body()
    
    # 构建请求头（透传 Authorization）
    headers = dict(request.headers)
    # 移除 Host 头，避免冲突
    headers.pop("host", None)
    
    try:
        logger.debug(f"🔄 转发: {request.method} /api/{path} -> {target_url}")
        
        # 发送请求到控制端
        resp = await client.request(
            method=request.method,
            url=target_url,
            params=dict(request.query_params),
            headers=headers,
            content=body if body else None
        )
        
        # 返回响应
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )
        
    except httpx.TimeoutException:
        logger.error(f"⏰ 代理超时: {target_url}")
        return JSONResponse(
            status_code=504,
            content={"code": 504, "message": "控制端服务超时～～(′Д`)"}
        )
    except httpx.ConnectError:
        logger.error(f"🔌 连接失败: {target_url}")
        return JSONResponse(
            status_code=503,
            content={"code": 503, "message": "控制端服务不可用，请稍后重试～～(′Д`)"}
        )
    except Exception as e:
        logger.error(f"❌ 代理异常: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"代理服务异常: {str(e)[:80]}～～(′Д`)"}
        )


@router.on_event("shutdown")
async def shutdown():
    """关闭 HTTP 客户端"""
    await client.aclose()