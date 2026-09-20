"""运行日志和审计日志。"""

import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name="mcp"):
    """获取统一配置的日志对象，避免重复添加 Handler。"""
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv("MCP_LOG_LEVEL", "INFO").upper())
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        log_file = os.getenv("MCP_LOG_FILE")
        if log_file:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    return logger


logger = get_logger()


def audit_event(event, **details):
    """记录不包含 API Key 和音频正文的审计信息。"""
    logger.info("audit event=%s details=%s", event, details)
