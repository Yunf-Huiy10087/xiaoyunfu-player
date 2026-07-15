"""
小云浮音视频处理服务 - 网页路由

职责：
1. 返回前端页面 (index.html)
2. 提供前端静态文件入口

文件位置: frontend/app/api/web.py
"""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

router = APIRouter(tags=["网页"])


@router.get("/")
async def index():
    """
    返回前端页面
    """
    html_path = Path(__file__).parent.parent.parent / "static" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>前端页面未找到</h1><p>请检查 static/index.html 是否存在</p>")


@router.get("/favicon.ico")
async def favicon():
    """返回 favicon"""
    ico_path = Path(__file__).parent.parent.parent / "static" / "favicon.ico"
    if ico_path.exists():
        return FileResponse(ico_path)
    return HTMLResponse("", status_code=204)


@router.get("/health")
async def health():
    """前端容器健康检查"""
    return {
        "status": "ok",
        "service": "前端容器",
        "static_dir": str(Path(__file__).parent.parent.parent / "static")
    }