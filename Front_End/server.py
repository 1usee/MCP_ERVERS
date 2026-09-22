import json
import os
import sys
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from BACK_End.MCP_SERVER import MAX_ERROR_CHARS, _call_qwen, _extract_response
from BACK_End.Data_Base import DataBase
from BACK_End.runtime_config import load_config, public_config, save_config
from BACK_End.safe_Part import safe_Check

ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("MCP_AUDIO_DIR", str(PROJECT_ROOT / "audio_files")))
DATABASE_PATH = Path(os.getenv("MCP_DATABASE", str(PROJECT_ROOT / "audio_tasks.db")))
MAX_BODY_BYTES = int(os.getenv("MCP_MAX_BODY_BYTES", str(40 * 1024 * 1024)))
WEB_TOKEN = os.getenv("MCP_WEB_TOKEN", "")
HOST = os.getenv("MCP_WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_WEB_PORT", "8000"))
database = None


class WebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not WEB_TOKEN:
            return True
        if self.headers.get("X-MCP-Token") == WEB_TOKEN:
            return True
        self._send_json({"error": "未授权"}, 401)
        return False

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Content-Length 头部无效") from exc
        if length <= 0:
            raise ValueError("请求体为空")
        if length > MAX_BODY_BYTES:
            raise ValueError(f"请求体超过上限 {MAX_BODY_BYTES} 字节")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"请求体格式错误: {exc}") from exc

    def _get_database(self):
        global database
        if database is None:
            database = DataBase(str(DATABASE_PATH)).connect()
            database.initialize()
        return database

    def _record_task(self, task_id, input_path, audio_format, **kwargs):
        self._get_database().record_task(
            task_id, input_path, audio_format, **kwargs
        )

    def do_GET(self):
        if self.path.startswith("/api/") and not self._authorized():
            return
        if self.path == "/api/config":
            current = load_config()
            self._send_json({
                **public_config(current),
            })
            return
        if self.path == "/api/health/storage":
            self._check_storage()
            return
        if self.path == "/api/models":
            self._get_models()
            return
        return super().do_GET()

    def _check_storage(self):
        probe = UPLOAD_DIR / f".probe-{uuid.uuid4().hex}"
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            probe.write_bytes(b"ok")
            writable = probe.exists()
            probe.unlink(missing_ok=True)
            self._send_json({"writable": writable})
        except OSError as exc:
            # 清理探针文件；即使清理本身失败，也不应影响错误上报。
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
            # 只取 strerror（如 "Permission denied"），不要 str(exc)——
            # 后者会带上探针文件的绝对路径，泄露服务器目录结构。
            reason = exc.strerror or exc.__class__.__name__
            self._send_json({"writable": False, "error": f"音频目录不可写：{reason}"}, 500)

    def _get_models(self):
        try:
            config = load_config()
            if not config["active_api_key"]:
                raise ValueError("请先添加 API Key")
            http_request = request.Request(
                f'{config["base_url"]}/models',
                headers={"Authorization": f'Bearer {config["active_api_key"]}'},
                method="GET",
            )
            with request.urlopen(http_request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("模型接口返回格式无效")
            models = [
                str(item["id"]).strip()
                for item in payload.get("data", [])
                if isinstance(item, dict) and str(item.get("id", "")).strip()
            ]
            if not models:
                raise RuntimeError("模型接口未返回模型名称")
            self._send_json({"models": models})
        except error.HTTPError as exc:
            details = exc.read(MAX_ERROR_CHARS).decode("utf-8", errors="replace")
            self._send_json({"error": f"获取模型名称失败（HTTP {exc.code}）：{details}"}, 502)
        except error.URLError as exc:
            self._send_json({"error": f"无法连接模型服务：{exc.reason}"}, 502)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def do_POST(self):
        if self.path.startswith("/api/") and not self._authorized():
            return
        if self.path == "/api/config":
            self._update_config()
            return
        if self.path == "/api/config/api-keys":
            self._add_api_key()
            return
        if self.path == "/api/tts":
            task_id = uuid.uuid4().hex
            input_path = None
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._send_json({"error": f"请求体格式错误: {exc}"}, 400)
                return

            try:
                config = load_config()
                model = str(payload.get("model", "")).strip()
                prompt = str(payload.get("prompt", "")).strip()
                audio_base64 = str(payload.get("audioBase64", "")).strip()
                audio_format = str(payload.get("audioFormat", "wav")).strip().lower().lstrip(".")

                if not model:
                    raise ValueError("模型名称不能为空")
                if not audio_base64:
                    raise ValueError("音频内容不能为空")
                if not prompt:
                    raise ValueError("文本提示词不能为空")

                if "," in audio_base64 and audio_base64.startswith("data:"):
                    audio_base64 = audio_base64.split(",", 1)[1]

                checker = safe_Check()
                audio_bytes = checker.decode_base64(audio_base64)
                audio_format = checker.validate_audio_bytes(audio_bytes, audio_format)
                UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                input_path = UPLOAD_DIR / f"{task_id}.{audio_format}"
                input_path.write_bytes(audio_bytes)
                self._record_task(task_id, input_path, audio_format)

                if not config["active_api_key"]:
                    raise ValueError("请先在 API 设置中添加并选择 API Key")

                response = _call_qwen(
                    audio_base64,
                    audio_format,
                    prompt,
                    api_key=config["active_api_key"],
                    base_url=config["base_url"],
                    model_name=model,
                )
                text, output_base64, output_format = _extract_response(response)
                output_path = None
                output_format = output_format.lower().lstrip(".")
                if output_base64:
                    output_bytes = checker.decode_base64(output_base64)
                    output_format = checker.validate_audio_bytes(output_bytes, output_format)
                    output_path = UPLOAD_DIR / f"{task_id}_output.{output_format}"
                    output_path.write_bytes(output_bytes)
                self._record_task(
                    task_id,
                    input_path,
                    audio_format,
                    status="completed",
                    output_path=output_path,
                    output_format=output_format if output_base64 else None,
                    text=text,
                )
                self._send_json({
                    "task_id": task_id,
                    "text": text,
                    "audio_base64": output_base64,
                    "audio_format": output_format if output_base64 else "",
                    "output_path": str(output_path) if output_path else None,
                })
                return
            except Exception as exc:
                if input_path is not None:
                    self._record_task(
                        task_id,
                        input_path,
                        locals().get("audio_format", "wav"),
                        status="failed",
                        error=str(exc)[:MAX_ERROR_CHARS],
                    )
                self._send_json({"error": str(exc)}, 500)
                return

        self._send_json({"error": "Not Found"}, 404)

    def _read_payload(self):
        return self._read_json_body()

    def _update_config(self):
        try:
            payload = self._read_payload()
            current = load_config()
            if "base_url" in payload:
                current["base_url"] = payload["base_url"]
            if "active_api_key_id" in payload:
                keys = current["api_keys"]
                key_id = int(payload["active_api_key_id"])
                if key_id < 0 or key_id >= len(keys):
                    raise ValueError("API Key 不存在")
                current["active_api_key"] = keys[key_id]
            saved = save_config(current)
            self._send_json(public_config(saved))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def _add_api_key(self):
        try:
            payload = self._read_payload()
            api_key = str(payload.get("api_key", "")).strip()
            if not api_key:
                raise ValueError("API Key 不能为空")
            current = load_config()
            if api_key not in current["api_keys"]:
                current["api_keys"].append(api_key)
            current["active_api_key"] = api_key
            saved = save_config(current)
            self._send_json(public_config(saved))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def do_DELETE(self):
        if self.path.startswith("/api/") and not self._authorized():
            return
        if self.path.startswith("/api/config/api-keys/"):
            try:
                key_id = int(self.path.rsplit("/", 1)[-1])
                current = load_config()
                keys = current["api_keys"]
                if key_id < 0 or key_id >= len(keys):
                    raise ValueError("API Key 不存在")
                removed = keys.pop(key_id)
                if removed == current["active_api_key"]:
                    current["active_api_key"] = keys[0] if keys else ""
                saved = save_config(current)
                self._send_json(public_config(saved))
            except (ValueError, TypeError) as exc:
                self._send_json({"error": str(exc)}, 400)
            return
        self._send_json({"error": "Not Found"}, 404)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    print(f"Web UI started at http://{HOST}:{PORT}")
    print("Local LAN access example: http://<server-ip>:8000")
    print("Please ensure the server machine can reach the cloud Qwen API and the API Key is valid.")
    server = ThreadingHTTPServer((HOST, PORT), WebHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
