from app.utils.logger import setup_logger
from app.core.config import settings

# 初始化日志
logger = setup_logger("xiaoyunfu.frontend", debug=settings.DEBUG)
logger.info("🌐 前端容器启动中...")
logger.debug(f"📋 配置: WEB_PORT={settings.WEB_PORT}, MC_PORT={settings.MC_PORT}")