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
            self._send_json({
                "models": [
                    "qwen-omni-turbo",
                    "qwen-omni-flash",
                    "qwen-omni-audio",
                ],
                "defaultModel": "qwen-omni-turbo",
            })
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/tts":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                self._send_json({"error": f"请求体格式错误: {exc}"}, 400)
                return

            try:
                api_key = str(payload.get("apiKey", "")).strip()
                model = str(payload.get("model", "")).strip()
                prompt = str(payload.get("prompt", "")).strip()
                audio_base64 = str(payload.get("audioBase64", "")).strip()
                audio_format = str(payload.get("audioFormat", "wav")).strip().lower().lstrip(".")

                if not api_key:
                    raise ValueError("API Key 不能为空")
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

                os.environ["DASHSCOPE_API_KEY"] = api_key
                os.environ["DASHSCOPE_AUDIO_MODEL"] = model
                config = Qwencloudconfig(api_key)
                config.model_name(model)

                response = _call_qwen(audio_base64, audio_format, prompt)
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
