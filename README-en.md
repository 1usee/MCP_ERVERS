# MCP Audio Generation Tool User Guide

This project provides an audio understanding and voice generation service based on a Qwen Omni-compatible API. It supports two usage modes:

- **Web Workbench**: Upload WAV/MP3 audio in a browser, enter a prompt, view the model's text response, and download generated audio.
- **MCP Service**: Use FastMCP to provide MCP clients with audio processing, task status queries, and service configuration queries.

## 1. Requirements

- Python 3
- Network access to the DashScope/Qwen-compatible API
- A valid DashScope API Key
- PowerShell on Windows; Bash on Linux/macOS

The project has only one Python dependency, `fastmcp`. The startup scripts automatically create a `.venv` virtual environment and install the dependencies listed in `requirements.txt`.

## 2. Quick Start

### Windows

Open PowerShell in the project root directory `F:\MCP_ERVERS` and run:

```powershell
.\start_powershell.ps1
```

The script will:

1. Create or reuse the `.venv` virtual environment.
2. Install the Python dependencies.
3. Start the Web service and MCP service.
4. Serve the Web Workbench at `http://localhost:8000` by default.

The Web service binds to localhost by default. For LAN access, explicitly set `MCP_WEB_HOST=0.0.0.0`; also set `MCP_WEB_TOKEN` when exposing it beyond the local machine. The browser client reads the token from `localStorage.mcpWebToken`.

Press `Ctrl+C` in the current PowerShell window to stop the services.

If PowerShell prevents script execution, temporarily relax the execution policy for the current window and try again:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start_powershell.ps1
```

### Linux/macOS

```bash
chmod +x start_on_Linux.sh
./start_on_Linux.sh
```

The default address is also `http://localhost:8000`. If the system does not have the package required to create Python virtual environments, install the appropriate Python venv package. For example, on Debian/Ubuntu:

```bash
sudo apt install python3-venv
```

### Manual Startup

To start the two services separately:

```powershell
# Windows
.venv\Scripts\python.exe Front_End\server.py
.venv\Scripts\python.exe BACK_End\MCP_SERVER.py
```

```bash
# Linux/macOS
.venv/bin/python Front_End/server.py
.venv/bin/python BACK_End/MCP_SERVER.py
```

When starting manually, run the commands from the project root and set `PYTHONPATH` to the project root. The MCP service normally communicates with MCP clients over **stdio** and does not provide a separate browser page.

## 3. Initial Configuration

1. Open `http://localhost:8000`.
2. Click **API Settings** in the upper-right corner.
3. Confirm or change the Qwen-compatible API address in **Base URL**. The default is:
   `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
4. Enter an API Key and click **Add**.
5. If multiple keys are saved, use the radio buttons to select the key for current requests.
6. Return to the workbench and select a model. The built-in models are:
   - `qwen-omni-turbo`
   - `qwen-omni-flash`
   - `qwen-omni-audio`
   - A custom model name

The configuration is saved to `mcp_config.json` in the project root. This file contains the API Keys themselves and must not be committed to a repository or exposed to other users.

## 4. Using the Web Workbench

1. Upload a WAV or MP3 file.
2. Enter a prompt, for example:

   ```text
   Please understand the content of this audio, summarize it in Chinese first, and then answer using natural speech.
   ```

3. Click **Send Request**.
4. View the model's text response on the right. If the model returns audio, click **Save Audio File** to download it.
5. Click **Clear** to reset the current input and results.

The server encodes the audio as Base64 and sends it to Qwen through an OpenAI Chat Completions-compatible interface. The requested output audio format is WAV by default.

## 5. MCP Client Integration

The MCP service entry point is `BACK_End/MCP_SERVER.py`. It provides the following tools:

### `execute`

Receives audio and calls Qwen.

Parameters:

- `audio_base64`: The Base64 content of the audio file. Do not include the `data:...;base64,` prefix.
- `audio_format`: The audio format. Supported formats are `wav` and `mp3`; the default is `wav`.
- `prompt`: The prompt sent to the model.

The return value contains:

- `task_id`: The task identifier.
- `text`: The text returned by the model.
- `audio_base64`: The Base64 content of the generated audio.
- `audio_format`: The format of the generated audio.
- `input_path` and `output_path`: The paths where the service stores the files.
- `audio`: An audio block containing `type`, `data`, and `mimeType`, provided when the model returns audio.

### `get_task_status`

Queries the task status, input/output paths, text, error information, and timestamps by `task_id`. It does not return the audio content again.

### `get_service_config`

Queries the Base URL, region, model name, and whether an API Key is configured. This tool never returns the API Key itself.

### MCP Client Configuration Examples

Windows client configuration example:

```json
{
  "mcpServers": {
    "tts-mcp": {
      "command": "F:\\MCP_ERVERS\\.venv\\Scripts\\python.exe",
      "args": ["F:\\MCP_ERVERS\\BACK_End\\MCP_SERVER.py"]
    }
  }
}
```

Linux/macOS client configuration example:

```json
{
  "mcpServers": {
    "tts-mcp": {
      "command": "/absolute/path/MCP_ERVERS/.venv/bin/python",
      "args": ["/absolute/path/MCP_ERVERS/BACK_End/MCP_SERVER.py"]
    }
  }
}
```

Before starting the MCP client, configure an API Key. You can add one in the Web settings page or provide an initial key through an environment variable:

```powershell
$env:DASHSCOPE_API_KEY = "your API Key"
```

```bash
export DASHSCOPE_API_KEY="your API Key"
```

## 6. Configuration Options

All configuration options are set through environment variables. Defaults are used when variables are not set.

| Environment variable | Default value | Description |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | Empty | Initial API Key when `mcp_config.json` does not exist |
| `DASHSCOPE_BASE_URL` | DashScope International compatible endpoint | Initial Base URL |
| `DASHSCOPE_AUDIO_MODEL` | `qwen-omni-turbo` | Default model used by MCP requests |
| `DASHSCOPE_AUDIO_VOICE` | `Cherry` | Voice used for generated speech |
| `DASHSCOPE_REGION` | `cn-beijing` | Service region identifier |
| `MCP_CONFIG_FILE` | `mcp_config.json` in the project root | Shared configuration file used by Web and MCP services |
| `MCP_WEB_HOST` | `0.0.0.0` | Web listening address |
| `MCP_WEB_PORT` | `8000` | Web listening port |
| `MCP_AUDIO_DIR` | `audio_files` | Directory for input and output audio |
| `MCP_DATABASE` | `audio_tasks.db` | SQLite task database path |
| `MCP_MAX_AUDIO_BYTES` | `25 MB` | Maximum size of one input or output audio file in bytes |
| `MCP_MAX_PROMPT_CHARS` | `4000` | Maximum MCP prompt length |
| `MCP_MAX_TEXT_CHARS` | `20000` | Maximum length of model text to store and return |
| `MCP_MAX_RESPONSE_BYTES` | `50 MB` | Maximum size of a normal Qwen response |
| `MCP_MAX_ERROR_CHARS` | `2000` | Maximum length of a single error message |
| `MCP_MAX_CONCURRENT_TASKS` | `4` | Maximum number of MCP tasks processed concurrently |
| `MCP_AUDIO_RETENTION_SECONDS` | `86400` | Audio retention period, 24 hours by default |
| `MCP_MAX_AUDIO_STORAGE_BYTES` | `1 GB` | Maximum total size of the audio directory |
| `MCP_LOG_LEVEL` | `INFO` | Log level |
| `MCP_LOG_FILE` | Empty | Optional log file path; enables rotating file logging when set |

For example, to use port 9000 and store audio in a specified directory on Windows:

```powershell
$env:MCP_WEB_PORT = "9000"
$env:MCP_AUDIO_DIR = "D:\MCPAudio"
.\start_powershell.ps1
```

## 7. Files and Data

- `Front_End/index.html`, `app.js`, and `style.css`: Browser workbench.
- `Front_End/server.py`: Static page server and Web API.
- `BACK_End/MCP_SERVER.py`: FastMCP service and audio task processing flow.
- `BACK_End/safe_Part.py`: Base64, format, and size validation.
- `BACK_End/runtime_config.py`: Shared configuration read/write for Web and MCP services.
- `BACK_End/Data_Base.py`: SQLite task metadata persistence.
- `audio_files/`: Runtime directory for input and output audio.
- `audio_tasks.db`: Task status database. The database stores only paths and task metadata, not audio binary data or API Keys.
- `mcp_config.json`: Local configuration file containing API Keys. Protect this file carefully.

The SQLite table is created automatically when the service starts. Audio files are cleaned up according to the retention period. If the directory exceeds `MCP_MAX_AUDIO_STORAGE_BYTES`, the oldest files are deleted first.

## 8. Security Recommendations

1. Do not commit `mcp_config.json`, API Keys, or generated audio files to a public repository.
2. The Web service listens on all network interfaces by default. Use a firewall or reverse proxy to restrict access when enabling LAN access.
3. Do not expose the unauthenticated Web port directly to the public Internet.
4. Use a dedicated, low-privilege API Key in production and rotate it regularly.
5. If file logging is enabled, restrict access to the log files. Logs should not contain API Keys or audio content.

## 9. Troubleshooting

### The page cannot be opened

Confirm that `Front_End/server.py` is running and use the port printed by the startup script. If `MCP_WEB_PORT` was changed, access the new port.

### The service reports that no API Key is configured

Add and select a key in **API Settings**, or set `DASHSCOPE_API_KEY` before starting the service. If `mcp_config.json` already exists, its active key configuration takes precedence over the environment variable.

### The audio format is not supported

The current security validation accepts only `wav` and `mp3`. Convert the audio to one of these formats and upload it again.

### The Qwen API returns a network or HTTP error

Check the Base URL, API Key, model name, and network connection. The Base URL must be a complete HTTP/HTTPS URL and must not contain a query string or fragment.

### The MCP client cannot start the service

Check that the Python path and `MCP_SERVER.py` path in the configuration are absolute paths. Also confirm that `.venv` was created successfully and that `fastmcp` is installed.

### How to view runtime logs

Logs are written to the console by default. Set `MCP_LOG_FILE` to additionally write rotating logs to a file, for example:

```powershell
$env:MCP_LOG_FILE = "logs\mcp.log"
```

## 10. Stopping, Upgrading, and Cleaning Up

Stop the startup script to terminate the Web and MCP child processes. To upgrade dependencies, run this command from the project root:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade
```

On Linux/macOS, use:

```bash
.venv/bin/python -m pip install -r requirements.txt --upgrade
```

To clean up historical runtime data, stop the services first, then delete the audio files in `audio_files/` and the `audio_tasks.db` database. Deleting `mcp_config.json` also removes the locally stored API Key configuration. You can configure the service again through an environment variable or the Web settings page.
