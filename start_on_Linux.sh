#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "Python 3 was not found. Install Python and add it to PATH." >&2
    exit 1
fi

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Creating Python virtual environment..."
    if ! "$PYTHON" -m venv "$PROJECT_ROOT/.venv"; then
        echo "Unable to create the virtual environment. Install python3-venv and retry." >&2
        exit 1
    fi
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Failed to create Python virtual environment: $VENV_PYTHON" >&2
    exit 1
fi

echo "Installing Python dependencies..."
"$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt"

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
WEB_PORT="${MCP_WEB_PORT:-8000}"

cleanup() {
    trap - EXIT INT TERM
    [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
    [[ -n "${MCP_PID:-}" ]] && kill "$MCP_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$VENV_PYTHON" "$PROJECT_ROOT/Front_End/server.py" &
WEB_PID=$!
"$VENV_PYTHON" "$PROJECT_ROOT/BACK_End/MCP_SERVER.py" &
MCP_PID=$!

echo "Web UI: http://localhost:$WEB_PORT"
if [[ "${MCP_WEB_HOST:-127.0.0.1}" == "0.0.0.0" ]]; then
    echo "Web UI LAN: http://<server-ip>:$WEB_PORT (MCP_WEB_TOKEN is recommended)"
else
    echo "Web UI is local-only by default; set MCP_WEB_HOST=0.0.0.0 for LAN access."
fi
echo "MCP service started. Press Ctrl+C to stop the project."

wait -n "$WEB_PID" "$MCP_PID"