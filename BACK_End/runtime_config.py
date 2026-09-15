"""Web UI and MCP shared runtime configuration."""

import json
import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse


_CONFIG_LOCK = threading.RLock()
_DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def _config_path() -> Path:
    default_path = Path(__file__).resolve().parent.parent / "mcp_config.json"
    return Path(os.getenv("MCP_CONFIG_FILE", str(default_path)))


def _defaults() -> dict:
    env_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    return {
        "api_keys": [env_key] if env_key else [],
        "active_api_key": env_key,
        "base_url": os.getenv("DASHSCOPE_BASE_URL", _DEFAULT_BASE_URL).rstrip("/"),
    }


def _validate_base_url(base_url: str) -> str:
    value = str(base_url or "").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain a query or fragment")
    return value


def _normalize(config: dict) -> dict:
    api_keys = []
    for value in config.get("api_keys", []):
        key = str(value).strip()
        if key and key not in api_keys:
            api_keys.append(key)
    active = str(config.get("active_api_key", "")).strip()
    if active not in api_keys:
        active = api_keys[0] if api_keys else ""
    return {
        "api_keys": api_keys,
        "active_api_key": active,
        "base_url": _validate_base_url(
            config.get("base_url") or _DEFAULT_BASE_URL
        ),
    }


def load_config() -> dict:
    """Load shared config; environment values remain the fallback."""
    with _CONFIG_LOCK:
        path = _config_path()
        if not path.is_file():
            return _defaults()
        try:
            return _normalize(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"invalid MCP config: {path}: {exc}") from exc


def save_config(config: dict) -> dict:
    """Atomically save shared config and return its normalized form."""
    normalized = _normalize(config)
    with _CONFIG_LOCK:
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f"{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temporary:
                json.dump(normalized, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    return normalized


def public_config(config: dict | None = None) -> dict:
    """Return config safe for the browser; never return API key contents."""
    current = _normalize(config or load_config())
    return {
        "base_url": current["base_url"],
        "api_keys": [
            {
                "id": index,
                "label": f"API Key {index + 1}",
                "masked": f"{key[:4]}...{key[-4:]}",
                "active": key == current["active_api_key"],
            }
            for index, key in enumerate(current["api_keys"])
        ],
    }
