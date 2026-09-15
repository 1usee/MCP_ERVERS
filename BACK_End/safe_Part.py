"""音频输入的格式、大小和内容安全检查。"""

import base64
import binascii
import os
from pathlib import Path


class safe_Check:
    """校验音频文件，避免未知格式或过大文件进入模型服务。"""

    ALLOWED_FORMATS = frozenset({"wav", "mp3"})

    def __init__(self, data=None, max_size=None):
        # 默认限制 25 MB，可使用 MCP_MAX_AUDIO_BYTES 调整。
        self.data = data
        self.max_size = max_size or int(
            os.getenv("MCP_MAX_AUDIO_BYTES", str(25 * 1024 * 1024))
        )

    def file_layout_check(self, file):
        """检查文件路径的存在性、扩展名和大小，并返回文件信息。"""
        # 文件路径校验用于处理已经落盘的音频。
        path = Path(file)
        if not path.is_file():
            raise ValueError(f"audio file does not exist: {path}")
        audio_format = path.suffix.lower().lstrip(".")
        if audio_format not in self.ALLOWED_FORMATS:
            raise ValueError(f"unsupported audio format: {audio_format or 'unknown'}")
        size = path.stat().st_size
        if size <= 0:
            raise ValueError("audio file is empty")
        if size > self.max_size:
            raise ValueError(f"audio file exceeds {self.max_size} bytes")
        return {"path": str(path), "format": audio_format, "size": size}

    def validate_audio_bytes(self, audio_bytes, audio_format):
        """检查内存中的音频数据，并返回规范化后的格式。"""
        # 内存校验用于 MCP 接收到的 Base64 解码结果。
        normalized_format = audio_format.lower().lstrip(".")
        if normalized_format not in self.ALLOWED_FORMATS:
            raise ValueError(f"unsupported audio format: {normalized_format}")
        if not audio_bytes:
            raise ValueError("audio data is empty")
        if len(audio_bytes) > self.max_size:
            raise ValueError(f"audio data exceeds {self.max_size} bytes")
        return normalized_format

    @staticmethod
    def decode_base64(value):
        """严格解码 Base64，统一转换为可读的参数错误。"""
        # validate=True 会拒绝包含非法字符的 Base64，而不是静默忽略。
        if not isinstance(value, str) or not value:
            raise ValueError("audio_base64 must be a non-empty string")
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError, TypeError) as exc:
            raise ValueError("audio_base64 must contain valid base64 data") from exc


class Error_Manager:
    """收集任务中的可预期错误，供日志或调用方查看。"""

    def __init__(self):
        self.errors = []

    def add(self, error):
        # 统一转换成字符串，便于写入日志或数据库。
        self.errors.append(str(error))

    def clear(self):
        self.errors.clear()

    def all(self):
        return tuple(self.errors)