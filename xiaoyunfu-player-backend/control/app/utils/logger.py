"""
小云浮音视频处理服务 - 控制端日志配置

文件位置: control/app/utils/logger.py
"""

import logging
import sys
from typing import Optional


# ============================================================
# 1. 日志格式
# ============================================================

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ============================================================
# 2. 日志配置函数
# ============================================================

def setup_logger(
    name: str = "xiaoyunfu.control",
    debug: bool = False,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    配置并返回日志记录器
    
    Args:
        name: 日志记录器名称
        debug: 是否开启调试模式（DEBUG级别）
        log_file: 日志文件路径（可选）
    
    Returns:
        配置好的 Logger 对象
    """
    # 设置日志级别
    level = logging.DEBUG if debug else logging.INFO
    
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 创建控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，添加文件 handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)
    
    return logger


# ============================================================
# 3. 获取日志记录器（快捷方式）
# ============================================================

def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 子模块名称（如 "api.auth"）
    
    Returns:
        Logger 对象
    """
    if name:
        full_name = f"xiaoyunfu.control.{name}"
    else:
        full_name = "xiaoyunfu.control"
    
    return logging.getLogger(full_name)


# ============================================================
# 4. 默认日志记录器
# ============================================================

# 默认创建控制台日志，INFO级别
logger = setup_logger()