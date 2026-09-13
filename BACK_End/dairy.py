"""运行日志和审计日志。文件名保留为 dairy.py 以兼容现有项目。"""

import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name="mcp"):
    """获取统一配置的日志对象，避免重复添加 Handler。"""
    # 使用命名 Logger，避免修改应用或第三方库的全局日志配置。
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv("MCP_LOG_LEVEL", "INFO").upper())
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        # 控制台日志便于开发阶段直接观察 MCP 服务运行状态。
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        log_file = os.getenv("MCP_LOG_FILE")
        # 配置 MCP_LOG_FILE 后才写文件，避免默认在项目目录产生日志文件。
        if log_file:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    return logger


logger = get_logger()


def audit_event(event, **details):
    # 审计信息只记录任务标识和状态，不记录 API Key 或音频正文。
    """记录不包含 API Key 和音频正文的审计信息。"""
    logger.info("audit event=%s details=%s", event, details)
