"""
小云浮音视频处理服务 - 插件端入口

职责：
1. 设置 Python 路径
2. 初始化日志
3. 加载所有插件
4. 创建 FastAPI 应用
5. 注册所有路由
6. 启动 uvicorn 服务

文件位置: plugin/main.py
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.plugin_loader import PluginLoader
from app.utils.logger import setup_logger
from app.api import meta, auth, search, song


# ============================================================
# 1. 初始化日志
# ============================================================
logger = setup_logger(
    name="xiaoyunfu.plugin",
    debug=settings.DEBUG
)
logger.info("🔌 插件端启动中...")


# ============================================================
# 2. 加载所有插件
# ============================================================
try:
    loader = PluginLoader()
    plugins = loader.load_all()
    logger.info(f"✅ 已加载 {len(plugins)} 个插件: {list(plugins.keys())}")
except Exception as e:
    logger.error(f"❌ 插件加载失败: {e}")
    sys.exit(1)


# ============================================================
# 3. 创建 FastAPI 应用
# ============================================================
app = FastAPI(
    title="小云浮音视频处理服务 - 插件端",
    version="5.0.0",
    description="音乐源插件服务，负责搜索、获取歌曲、认证等",
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

# 元数据路由（插件声明能力）
app.include_router(meta.router)

# 认证路由（处理登录）
app.include_router(auth.router)

# 搜索路由
app.include_router(search.router)

# 歌曲路由
app.include_router(song.router)

logger.info("✅ 所有路由已注册")


# ============================================================
# 5. 启动信息
# ============================================================
logger.info("=" * 50)
logger.info("🎧 小云浮音视频处理服务 - 插件端")
logger.info(f"📌 端口: {settings.PORT}")
logger.info(f"🐛 调试模式: {'开启' if settings.DEBUG else '关闭'}")
logger.info(f"📂 插件代码目录: {settings.PLUGIN_CODE_DIR}")
logger.info(f"📂 插件配置目录: {settings.PLUGIN_CONFIG_DIR}")
if plugins:
    logger.info(f"📦 已加载插件: {', '.join(plugins.keys())}")
else:
    logger.warning("⚠️ 没有加载任何插件")
logger.info("=" * 50)


# ============================================================
# 6. 启动服务
# ============================================================
if __name__ == "__main__":
    logger.info(f"🚀 插件端启动完成，监听端口: {settings.PORT}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )