import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from BACK_End.MCP_SERVER import _call_qwen, _extract_response
from BACK_End.api_setting import Qwencloudconfig
from BACK_End.runtime_config import load_config, public_config, save_config
from BACK_End.safe_Part import safe_Check

ROOT = Path(__file__).resolve().parent
HOST = os.getenv("MCP_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_WEB_PORT", "8000"))


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

    def do_GET(self):
        if self.path == "/api/config":
            current = load_config()
            self._send_json({
                "models": ["qwen-omni-turbo", "qwen-omni-flash", "qwen-omni-audio"],
                "defaultModel": "qwen-omni-turbo",
                **public_config(current),
            })
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/config":
            self._update_config()
            return
        if self.path == "/api/config/api-keys":
            self._add_api_key()
            return
        if self.path == "/api/tts":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
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
                self._send_json({
                    "text": text,
                    "audio_base64": output_base64,
                    "audio_format": output_format.lower().lstrip("."),
                })
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
                return

        self._send_json({"error": "Not Found"}, 404)

    def _read_payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

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
