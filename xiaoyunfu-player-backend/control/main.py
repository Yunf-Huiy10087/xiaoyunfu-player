"""
小云浮音视频处理服务 - 控制端入口

职责：
1. 设置 Python 路径
2. 初始化日志
3. 初始化数据库
4. 创建 FastAPI 应用
5. 注册所有路由
6. 启动 uvicorn 服务

文件位置: control/main.py
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.utils.logger import setup_logger
from app.api import root, health, auth, music, playlists, admin, queue, plugins


# ============================================================
# 1. 初始化日志
# ============================================================
logger = setup_logger(
    name="xiaoyunfu.control",
    debug=settings.DEBUG
)
logger.info("🚀 控制端启动中...")


# ============================================================
# 2. 初始化数据库
# ============================================================
try:
    init_db()
    logger.info("✅ 数据库初始化完成")
except Exception as e:
    logger.error(f"❌ 数据库初始化失败: {e}")
    sys.exit(1)


# ============================================================
# 3. 创建 FastAPI 应用
# ============================================================
app = FastAPI(
    title="小云浮音视频处理服务 - 控制端",
    version="5.0.0",
    description="音视频转码、队列管理、用户认证、歌单管理",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
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
# 4. 注册路由
# ============================================================
logger.info("📋 注册路由...")

# 系统路由
app.include_router(root.router)
app.include_router(health.router)

# 认证路由
app.include_router(auth.router)

# 业务路由
app.include_router(music.router)
app.include_router(playlists.router)

# 管理路由
app.include_router(admin.router)

# 队列路由
app.include_router(queue.router)

# 插件路由
app.include_router(plugins.router)

logger.info("✅ 所有路由已注册")


# ============================================================
# 5. 启动信息
# ============================================================
logger.info("=" * 50)
logger.info("🎧 小云浮音视频处理服务 - 控制端")
logger.info(f"📌 端口: {settings.PORT}")
logger.info(f"🐛 调试模式: {'开启' if settings.DEBUG else '关闭'}")
logger.info(f"🗄️  数据库: {settings.DB_PATH}")
logger.info(f"📂 上传目录: {settings.UPLOAD_DIR}")
logger.info(f"📂 缓存目录: {settings.CACHE_DIR}")
logger.info("=" * 50)


# ============================================================
# 6. 启动服务
# ============================================================
if __name__ == "__main__":
    logger.info(f"🚀 控制端启动完成，监听端口: {settings.PORT}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )