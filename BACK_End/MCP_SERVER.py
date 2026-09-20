"""MCP 音频服务器：接收音频，调用 Qwen Omni，并返回生成的音频。"""

import base64
import asyncio
import json
import os
import threading
import time
import uuid
from pathlib import Path
from urllib import error, request

from fastmcp import FastMCP

from BACK_End.api_setting import Qwencloudconfig
from BACK_End.Data_Base import DataBase
from BACK_End.diary import audit_event, logger
from BACK_End.safe_Part import safe_Check


# 创建 MCP 服务器实例，客户端可以通过这个实例发现并调用工具。
mcp = FastMCP("TTS_mcp")
# 音频文件保存目录，可通过环境变量 MCP_AUDIO_DIR 自定义。
UPLOAD_DIR = Path(os.getenv("MCP_AUDIO_DIR", "audio_files"))
DATABASE_PATH = Path(os.getenv("MCP_DATABASE", "audio_tasks.db"))
MAX_PROMPT_CHARS = int(os.getenv("MCP_MAX_PROMPT_CHARS", "4000"))
MAX_RESPONSE_BYTES = int(
    os.getenv("MCP_MAX_RESPONSE_BYTES", str(50 * 1024 * 1024))
)
MAX_TEXT_CHARS = int(os.getenv("MCP_MAX_TEXT_CHARS", "20000"))
MAX_ERROR_CHARS = int(os.getenv("MCP_MAX_ERROR_CHARS", "2000"))
AUDIO_RETENTION_SECONDS = int(
    os.getenv("MCP_AUDIO_RETENTION_SECONDS", str(24 * 60 * 60))
)
MAX_AUDIO_STORAGE_BYTES = int(
    os.getenv("MCP_MAX_AUDIO_STORAGE_BYTES", str(1024 * 1024 * 1024))
)
MAX_CONCURRENT_TASKS = int(os.getenv("MCP_MAX_CONCURRENT_TASKS", "4"))
task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
audio_checker = safe_Check()
database = None
database_lock = threading.Lock()


def _get_database():
    """按需初始化数据库，避免仅导入模块就创建数据库文件。"""
    global database
    if database is None:
        with database_lock:
            if database is None:
                database = DataBase(str(DATABASE_PATH)).connect()
                database.initialize()
    return database


def _read_limited(stream, maximum):
    """Read an HTTP body without allowing an unbounded response buffer."""
    chunks = []
    total = 0
    while True:
        chunk = stream.read(min(1024 * 1024, maximum - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise RuntimeError(f"Qwen API response exceeds {maximum} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _cleanup_audio_files():
    """Remove expired files and oldest files above the storage budget."""
    if not UPLOAD_DIR.is_dir():
        return
    now = time.time()
    retained = []
    for path in UPLOAD_DIR.iterdir():
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if AUDIO_RETENTION_SECONDS >= 0 and now - stat.st_mtime > AUDIO_RETENTION_SECONDS:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            retained.append((path, stat.st_mtime, stat.st_size))
    total = sum(size for _, _, size in retained)
    for path, _, size in sorted(retained, key=lambda item: item[1]):
        if total <= MAX_AUDIO_STORAGE_BYTES:
            break
        try:
            path.unlink()
            total -= size
        except OSError:
            pass
    if database is not None:
        database.purge_older_than(AUDIO_RETENTION_SECONDS)
        database.purge_missing_inputs()


def _audio_mime_type(audio_format: str) -> str:
    """返回 OpenHanako 音频块需要的 MIME 类型。"""
    return {"wav": "audio/wav", "mp3": "audio/mpeg"}[audio_format]


def _call_qwen(
    audio_base64: str,
    audio_format: str,
    prompt: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model_name: str | None = None,
) -> dict:
    """调用 Qwen 兼容 API，将输入音频发送给模型并返回原始 JSON。"""
    config = Qwencloudconfig(api_key, base_url, model_name)
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
            body = _read_limited(response, MAX_RESPONSE_BYTES)
            return json.loads(body.decode("utf-8"))
    except error.HTTPError as exc:
        details = _read_limited(exc, MAX_ERROR_CHARS).decode("utf-8", errors="replace")
        raise RuntimeError(f"Qwen API returned HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Qwen API: {exc.reason}") from exc


def _extract_response(response: dict) -> tuple[str, str | None, str]:
    """从 Qwen 返回结果中提取文本、可选 Base64 音频和格式。"""
    # 兼容 OpenAI 风格响应，先定位第一条模型消息。
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Qwen API response: {response}") from exc

    # 文本内容用于返回模型的文字回答；音频内容用于生成文件和客户端播放。
    content = message.get("content") or ""
    text = content if isinstance(content, str) else ""
    audio = message.get("audio") or {}
    audio_base64 = audio.get("data") or None
    audio_format = audio.get("format", "wav")
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
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"prompt exceeds {MAX_PROMPT_CHARS} characters")
    async with task_semaphore:
        return await _execute_task(task_id, audio_base64, audio_format, prompt)


async def _execute_task(task_id, audio_base64, audio_format, prompt):
    """Run one task after concurrency admission control."""
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
        _cleanup_audio_files()
        input_path = UPLOAD_DIR / f"{task_id}.{normalized_format}"
        input_path.write_bytes(audio_bytes)
        _get_database().record_task(task_id, input_path, normalized_format)
        audit_event("audio_received", task_id=task_id, format=normalized_format)

        # 网络请求是阻塞操作，放到线程中执行，避免阻塞 MCP 的异步服务。
        response = await asyncio.to_thread(
            _call_qwen, audio_base64, normalized_format, prompt
        )
        text, output_base64, output_format = _extract_response(response)
        text = text[:MAX_TEXT_CHARS]
        output_path = None
        output_format = output_format.lower().lstrip(".")
        if output_base64:
            output_bytes = audio_checker.decode_base64(output_base64)
            audio_checker.validate_audio_bytes(output_bytes, output_format)
            output_path = UPLOAD_DIR / f"{task_id}_output.{output_format}"
            output_path.write_bytes(output_bytes)
        _get_database().record_task(
            task_id,
            input_path,
            normalized_format,
            status="completed",
            output_path=output_path,
            output_format=output_format if output_base64 else None,
            text=text,
        )
        audit_event("audio_completed", task_id=task_id, output_format=output_format)
        _cleanup_audio_files()
        # MCP 没有标准音频内容类型，额外提供 OpenHanako 约定的音频块。
        return {
            "task_id": task_id,
            "text": text,
            "audio": {
                "type": "audio",
                "data": output_base64,
                "mimeType": _audio_mime_type(output_format),
            } if output_base64 else None,
            "audio_base64": output_base64 or "",
            "audio_format": output_format if output_base64 else "",
            "input_path": str(input_path),
            "output_path": str(output_path) if output_path else None,
        }
    except Exception as exc:
        logger.exception("audio task failed task_id=%s", task_id)
        if input_path is not None:
            _get_database().record_task(
                task_id,
                input_path,
                normalized_format,
                status="failed",
                error=str(exc)[:MAX_ERROR_CHARS],
            )
        audit_event("audio_failed", task_id=task_id, error=str(exc)[:MAX_ERROR_CHARS])
        raise


@mcp.tool
def get_task_status(task_id: str) -> dict:
    """查询音频任务状态，不返回音频正文。"""
    # 状态查询只返回元数据，不重复传输音频正文。
    rows = _get_database().fetch_all(
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


