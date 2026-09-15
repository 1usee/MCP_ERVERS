"""Qwen API 配置、区域和模型管理。"""

import os

from BACK_End.runtime_config import load_config


class Qwencloudconfig:
    """为 MCP 服务统一提供 API Key、请求地址和模型配置。"""

    def __init__(self, api_key=None, base_url=None, model_name=None):
        runtime = load_config()
        # 显式参数用于单次请求，否则使用网页配置的当前 API Key。
        self.api_key = api_key or runtime["active_api_key"]
        self.base_url = (base_url or runtime["base_url"]).rstrip("/")
        # 区域和模型名称用于配置管理和请求构造。
        self.region = os.getenv("DASHSCOPE_REGION", "cn-beijing")
        self._model_name = model_name or os.getenv(
            "DASHSCOPE_AUDIO_MODEL", "qwen-omni-turbo"
        )

    def get_api(self):
        # 只由服务内部读取 API Key，不能通过配置摘要对外返回。
        """返回 API Key；没有配置时返回 None。"""
        return self.api_key

    def model_name(self, model_name=None):
        # 不传参数时读取模型，传入参数时更新当前模型。
        """读取或更新模型名称。"""
        if model_name is not None:
            model_name = model_name.strip()
            if not model_name:
                raise ValueError("model_name cannot be empty")
            self._model_name = model_name
        return self._model_name

    def set_region(self, region):
        # 区域不能为空，避免产生无效的服务配置。
        """更新服务区域并返回新的区域。"""
        region = region.strip()
        if not region:
            raise ValueError("region cannot be empty")
        self.region = region
        return self.region

    def as_dict(self):
        # 该摘要可以提供给 MCP 客户端，不包含真实密钥。
        """返回不包含 API Key 的安全配置摘要。"""
        return {
            "base_url": self.base_url,
            "region": self.region,
            "model": self._model_name,
            "has_api_key": bool(self.api_key),
        }




    