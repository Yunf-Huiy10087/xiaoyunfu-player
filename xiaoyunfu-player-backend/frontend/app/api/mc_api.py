"""
小云浮音视频处理服务 - MC 服务端专用 API

职责：
1. 为 Minecraft 服务端提供专用接口
2. 简化调用格式（兼容 MC 插件）
3. 返回 MC 友好的数据格式

文件位置: frontend/app/api/mc_api.py
"""

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("api.mc")
router = APIRouter(prefix="/mc", tags=["MC服务端API"])

# HTTP 客户端
client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mc_api_proxy(path: str, request: Request):
    """
    MC 服务端专用 API 代理
    
    转发 /mc/* 请求到控制端的 /api/v1/*（简化 URL）
    同时做格式转换，使 MC 插件更容易解析
    """
    target_url = f"{settings.CONTROL_URL}/api/v1/{path}"
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    
    try:
        logger.debug(f"🎮 MC API: {request.method} /mc/{path} -> {target_url}")
        
        resp = await client.request(
            method=request.method,
            url=target_url,
            params=dict(request.query_params),
            headers=headers,
            content=body if body else None
        )
        
        # 尝试解析 JSON 并转换为 MC 友好格式
        try:
            data = resp.json()
            # 如果是标准格式，直接返回
            if isinstance(data, dict) and "code" in data:
                return JSONResponse(
                    status_code=resp.status_code,
                    content=data
                )
            # 否则包装成 MC 格式
            return JSONResponse(
                status_code=resp.status_code,
                content={
                    "success": resp.status_code == 200,
                    "data": data
                }
            )
        except:
            # 非 JSON 响应，直接透传
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
            
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"success": False, "error": "服务超时～～(′Д`)"}
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": "控制端服务不可用～～(′Д`)"}
        )
    except Exception as e:
        logger.error(f"❌ MC API 异常: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)[:80]}
        )


@router.get("/health")
async def mc_health():
    """MC API 健康检查"""
    return {"status": "ok", "service": "MC API", "control": settings.CONTROL_URL}