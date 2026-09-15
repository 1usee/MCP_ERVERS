"""MCP 音频服务器：接收音频，调用 Qwen Omni，并返回生成的音频。"""

import base64
import asyncio
import json
import os
import uuid
from pathlib import Path
from urllib import error, request

from fastmcp import FastMCP

from BACK_End.api_setting import Qwencloudconfig
from BACK_End.Data_Base import DataBase
from BACK_End.dairy import audit_event, logger
from BACK_End.safe_Part import safe_Check


# 创建 MCP 服务器实例，客户端可以通过这个实例发现并调用工具。
mcp = FastMCP("TTS_mcp")
# 音频文件保存目录，可通过环境变量 MCP_AUDIO_DIR 自定义。
UPLOAD_DIR = Path(os.getenv("MCP_AUDIO_DIR", "audio_files"))
DATABASE_PATH = Path(os.getenv("MCP_DATABASE", "audio_tasks.db"))
# 这些对象在服务启动时初始化，供所有 MCP 工具复用。
audio_checker = safe_Check()
database = DataBase(str(DATABASE_PATH)).connect()
database.initialize()


def _audio_mime_type(audio_format: str) -> str:
    """返回 OpenHanako 音频块需要的 MIME 类型。"""
    return {"wav": "audio/wav", "mp3": "audio/mpeg"}[audio_format]


def _call_qwen(audio_base64: str, audio_format: str, prompt: str) -> dict:
    """调用 Qwen 兼容 API，将输入音频发送给模型并返回原始 JSON。"""
    config = Qwencloudconfig()
    api_key = config.get_api()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")

    # 按照 OpenAI 兼容接口格式组织音频和文本请求。
    payload = {
        "model": config.model_name(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:audio/{audio_format};base64,{audio_base64}",
                            "format": audio_format,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "modalities": ["text", "audio"],
        "audio": {
            "voice": os.getenv("DASHSCOPE_AUDIO_VOICE", "Cherry"),
            "format": "wav",
        },
    }
    # 将 JSON 请求体编码为 HTTP 请求需要的字节数据。
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        f"{config.base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    # 使用标准库发送 POST 请求，避免阻塞 MCP 的异步事件循环。
    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Qwen API returned HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Qwen API: {exc.reason}") from exc


def _extract_response(response: dict) -> tuple[str, str, str]:
    """从 Qwen 返回结果中提取文本、Base64 音频和音频格式。"""
    # 兼容 OpenAI 风格响应，先定位第一条模型消息。
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Qwen API response: {response}") from exc

    # 文本内容用于返回模型的文字回答；音频内容用于生成文件和客户端播放。
    content = message.get("content") or ""
    text = content if isinstance(content, str) else ""
    audio = message.get("audio") or {}
    audio_base64 = audio.get("data", "")
    audio_format = audio.get("format", "wav")
    if not audio_base64:
        raise RuntimeError("Qwen API response did not contain audio data")
    return text, audio_base64, audio_format


@mcp.tool
async def execute(
    audio_base64: str,
    audio_format: str = "wav",
    prompt: str = "请理解这段音频，并用语音回答。",
) -> dict:
    """接收 Base64 音频，调用 Qwen，并返回生成的音频和文字结果。"""
    # 一个任务 ID 同时用于数据库记录、输入文件和输出文件的关联。
    task_id = uuid.uuid4().hex
    input_path = None
    normalized_format = audio_format.lower().lstrip(".")
    try:
        # 安全模块统一负责 Base64 解码、格式限制和文件大小限制。
        audio_bytes = audio_checker.decode_base64(audio_base64)
        normalized_format = audio_checker.validate_audio_bytes(
            audio_bytes, normalized_format
        )

        # 文件存储模块当前由音频目录和唯一任务 ID 组成，避免文件名冲突。
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        input_path = UPLOAD_DIR / f"{task_id}.{normalized_format}"
        input_path.write_bytes(audio_bytes)
        database.record_task(task_id, input_path, normalized_format)
        audit_event("audio_received", task_id=task_id, format=normalized_format)

        # 网络请求是阻塞操作，放到线程中执行，避免阻塞 MCP 的异步服务。
        response = await asyncio.to_thread(
            _call_qwen, audio_base64, normalized_format, prompt
        )
        text, output_base64, output_format = _extract_response(response)
        output_bytes = audio_checker.decode_base64(output_base64)
        output_format = output_format.lower().lstrip(".")
        audio_checker.validate_audio_bytes(output_bytes, output_format)

        output_path = UPLOAD_DIR / f"{task_id}_output.{output_format}"
        output_path.write_bytes(output_bytes)
        database.record_task(
            task_id,
            input_path,
            normalized_format,
            status="completed",
            output_path=output_path,
            output_format=output_format,
            text=text,
        )
        audit_event("audio_completed", task_id=task_id, output_format=output_format)
        # MCP 没有标准音频内容类型，额外提供 OpenHanako 约定的音频块。
        return {
            "task_id": task_id,
            "text": text,
            "audio": {
                "type": "audio",
                "data": output_base64,
                "mimeType": _audio_mime_type(output_format),
            },
            "audio_base64": output_base64,
            "audio_format": output_format,
            "input_path": str(input_path),
            "output_path": str(output_path),
        }
    except Exception as exc:
        logger.exception("audio task failed task_id=%s", task_id)
        if input_path is not None:
            database.record_task(
                task_id,
                input_path,
                normalized_format,
                status="failed",
                error=str(exc),
            )
        audit_event("audio_failed", task_id=task_id, error=str(exc))
        raise


@mcp.tool
def get_task_status(task_id: str) -> dict:
    """查询音频任务状态，不返回音频正文。"""
    # 状态查询只返回元数据，不重复传输音频正文。
    rows = database.fetch_all(
        """
        SELECT task_id, input_path, output_path, input_format, output_format,
               status, text, error, created_at, finished_at
        FROM audio_tasks WHERE task_id = ?
        """,
        (task_id,),
    )
    if not rows:
        raise ValueError(f"task not found: {task_id}")
    columns = (
        "task_id", "input_path", "output_path", "input_format", "output_format",
        "status", "text", "error", "created_at", "finished_at",
    )
    return dict(zip(columns, rows[0]))


@mcp.tool
def get_service_config() -> dict:
    """返回服务配置摘要，不暴露 API Key。"""
    # 配置摘要经过 as_dict 处理，不会泄露 API Key。
    return Qwencloudconfig().as_dict()


if __name__ == "__main__":
    # 直接运行本文件时启动 MCP 服务；通常使用 stdio 与 MCP 客户端通信。
    mcp.run()


