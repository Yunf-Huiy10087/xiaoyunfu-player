"""
小云浮音视频处理服务 - 前端容器入口

职责：
1. 设置 Python 路径
2. 初始化日志
3. 创建 FastAPI 应用
4. 挂载静态文件
5. 注册所有路由（网页、MC API、代理）
6. 启动双端口服务（8725 网页 + 8752 MC API）

文件位置: frontend/main.py
"""

import sys
import subprocess
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.utils.logger import setup_logger
from app.api import web, mc_api, proxy


# ============================================================
# 1. 初始化日志
# ============================================================
logger = setup_logger(
    name="xiaoyunfu.frontend",
    debug=settings.DEBUG
)
logger.info("🌐 前端容器启动中...")
logger.debug(f"📋 配置: WEB_PORT={settings.WEB_PORT}, MC_PORT={settings.MC_PORT}")


# ============================================================
# 2. 创建 FastAPI 应用
# ============================================================
app = FastAPI(
    title="小云浮音视频处理服务 - 前端容器",
    version="5.0.0",
    description="网页服务 + MC服务端专用API + API代理",
    docs_url=None,  # 前端容器不暴露文档
    redoc_url=None
)

# 添加 CORS 中间件（允许跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

logger.info("✅ FastAPI 应用已创建")


# ============================================================
# 3. 挂载静态文件
# ============================================================
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"📂 静态文件已挂载: {static_dir}")
else:
    logger.warning(f"⚠️ 静态文件目录不存在: {static_dir}")


# ============================================================
# 4. 注册路由
# ============================================================
logger.info("📋 注册路由...")

# 网页路由（返回前端页面）
app.include_router(web.router)

# MC服务端专用API路由
app.include_router(mc_api.router)

# 代理路由（转发 /api/* 到控制端）
app.include_router(proxy.router)

logger.info("✅ 所有路由已注册")


# ============================================================
# 5. 启动信息
# ============================================================
logger.info("=" * 50)
logger.info("🎧 小云浮音视频处理服务 - 前端容器")
logger.info(f"🌐 网页端口: {settings.WEB_PORT}")
logger.info(f"🎮 MC API端口: {settings.MC_PORT}")
logger.info(f"🐛 调试模式: {'开启' if settings.DEBUG else '关闭'}")
logger.info(f"🔗 控制端地址: {settings.CONTROL_URL}")
logger.info("=" * 50)


# ============================================================
# 6. 启动服务（双端口）
# ============================================================
if __name__ == "__main__":
    import time
    
    logger.info(f"🚀 前端容器启动完成")
    logger.info(f"   🌐 网页访问: http://localhost:{settings.WEB_PORT}")
    logger.info(f"   🎮 MC API: http://localhost:{settings.MC_PORT}")
    
    # 启动两个进程分别监听两个端口
    # 网页服务 (8725)
    subprocess.Popen([
        "uvicorn", "main:app", 
        "--host", "0.0.0.0", 
        "--port", str(settings.WEB_PORT),
        "--log-level", "debug" if settings.DEBUG else "info"
    ])
    logger.info(f"✅ 网页服务已启动: 端口 {settings.WEB_PORT}")
    
    # MC API服务 (8752)
    subprocess.Popen([
        "uvicorn", "main:app", 
        "--host", "0.0.0.0", 
        "--port", str(settings.MC_PORT),
        "--log-level", "debug" if settings.DEBUG else "info"
    ])
    logger.info(f"✅ MC API服务已启动: 端口 {settings.MC_PORT}")
    
    # 保持主进程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 收到退出信号，停止服务")