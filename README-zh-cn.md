# MCP 音频生成工具使用说明

本项目提供一个基于 Qwen Omni 兼容接口的音频理解与语音生成服务，包含两种使用方式：

- **Web 工作台**：在浏览器中上传 WAV/MP3 音频，输入提示词，查看模型文字回复并下载生成音频。
- **MCP 服务**：通过 FastMCP 向 MCP 客户端提供音频处理、任务状态查询和服务配置查询工具。

## 一、运行要求

- Python 3
- 可访问 DashScope/Qwen 兼容 API 的网络环境
- 有效的 DashScope API Key
- Windows 使用 PowerShell；Linux/macOS 使用 Bash

项目依赖只有 `fastmcp`，启动脚本会自动创建 `.venv` 并安装 `requirements.txt` 中的依赖。

## 二、快速启动

### Windows

在项目根目录 `F:\MCP_ERVERS` 打开 PowerShell，执行：

```powershell
.\start_powershell.ps1
```

脚本会：

1. 创建或复用 `.venv` 虚拟环境；
2. 安装 Python 依赖；
3. 启动 Web 服务和 MCP 服务；
4. 默认在 `http://localhost:8000` 提供 Web 工作台。

Web 服务默认只监听本机。如需局域网访问，请显式设置 `MCP_WEB_HOST=0.0.0.0`；同时建议设置 `MCP_WEB_TOKEN`，前端会从浏览器 `localStorage` 的 `mcpWebToken` 读取令牌并发送到 API。

停止服务时，在当前 PowerShell 窗口按 `Ctrl+C`。

如果 PowerShell 禁止执行脚本，可以仅对当前窗口放宽策略后重试：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start_powershell.ps1
```

### Linux/macOS

```bash
chmod +x start_on_Linux.sh
./start_on_Linux.sh
```

默认访问地址同样是 `http://localhost:8000`。如果系统缺少创建虚拟环境所需的软件包，请先安装对应的 Python venv 包，例如 Debian/Ubuntu：

```bash
sudo apt install python3-venv
```

### 手动启动

如需分别启动两个服务：

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

手动启动时建议在项目根目录执行，并设置 `PYTHONPATH` 为项目根目录。MCP 服务**默认通过 stdio** 与同机的 MCP 客户端通信，不监听端口，也不提供浏览器页面；如需供局域网内其他机器调用，可切换为 HTTP 传输（见下方「MCP 客户端配置示例」）。

## 三、首次配置

1. 打开 `http://localhost:8000`。
2. 点击右上角 **API 设置**。
3. 在 **Base URL** 中确认或修改 Qwen 兼容接口地址。默认值为：
   `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
4. 输入 API Key，点击 **添加**。
5. 如果保存了多个 Key，通过单选框选择当前使用的 Key。
6. 点击 **获取模型名称**，从当前 Base URL 获取可用模型列表。
7. 返回工作台，选择已获取的模型；也可以选择并填写自定义模型名称。

配置会保存到项目根目录的 `mcp_config.json`。该文件包含 API Key 本身，不应提交到代码仓库或暴露给其他用户。

## 四、使用 Web 工作台

1. 上传一个 WAV 或 MP3 文件。
2. 输入提示词，例如：

   ```text
   请理解这段音频内容，先用中文总结，再用自然语音回答。
   ```

3. 点击 **发送请求**。
4. 在右侧查看模型文字回复；如果模型返回音频，可点击 **保存音频文件** 下载。
5. 点击 **清空** 可重置当前输入和结果。

服务端会把音频编码为 Base64，通过兼容 OpenAI Chat Completions 的接口发送给 Qwen。生成音频默认请求 WAV 格式。

## 五、MCP 客户端接入

MCP 服务入口为 `BACK_End/MCP_SERVER.py`，提供以下工具：

### `execute`

接收音频并调用 Qwen。

参数：

- `audio_base64`：音频文件的 Base64 内容，不要包含 `data:...;base64,` 前缀。
- `audio_format`：音频格式，支持 `wav` 和 `mp3`，默认 `wav`。
- `prompt`：发送给模型的提示词。

返回值包含：

- `task_id`：任务标识；
- `text`：模型返回的文字；
- `audio_base64`：生成音频的 Base64 内容；
- `audio_format`：生成音频格式；
- `input_path`、`output_path`：服务端保存路径；
- `audio`：包含 `type`、`data` 和 `mimeType` 的音频块（模型返回音频时提供）。

### `get_task_status`

根据 `task_id` 查询任务状态、输入输出路径、文字、错误信息和时间戳，不重复返回音频正文。

### `get_service_config`

查询 Base URL、区域、模型名称以及是否已配置 API Key。该工具不会返回 API Key 内容。

### MCP 客户端配置示例

#### 方式一：stdio（默认，MCP 服务与客户端在同一台机器）

Windows 客户端配置示例：

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

Linux/macOS 客户端配置示例：

```json
{
  "mcpServers": {
    "tts-mcp": {
      "command": "/绝对路径/MCP_ERVERS/.venv/bin/python",
      "args": ["/绝对路径/MCP_ERVERS/BACK_End/MCP_SERVER.py"]
    }
  }
}
```

此方式由客户端亲自启动 MCP 进程，两者通过标准输入输出通信。

#### 方式二：HTTP（跨机器，MCP 服务部署在局域网服务器上）

如果你的 MCP 服务运行在局域网内另一台服务器上，先在该服务器上以 HTTP 传输启动：

```bash
# Linux/macOS —— 在服务器上执行
MCP_TRANSPORT=http \
MCP_SERVER_HOST=0.0.0.0 \
MCP_SERVER_PORT=9000 \
MCP_AUDIO_DIR=/var/lib/mcp-audio \
.venv/bin/python BACK_End/MCP_SERVER.py
```

```powershell
# Windows —— 在服务器上执行
$env:MCP_TRANSPORT = "http"
$env:MCP_SERVER_HOST = "0.0.0.0"
$env:MCP_SERVER_PORT = "9000"
$env:MCP_AUDIO_DIR = "D:\MCPAudio"
.venv\Scripts\python.exe BACK_End\MCP_SERVER.py
```

然后在客户端配置中改填 URL：

```json
{
  "mcpServers": {
    "tts-mcp": {
      "url": "http://192.168.1.50:9000/mcp"
    }
  }
}
```

说明：

- 端点路径固定为 `/mcp`，不要省略。
- 端口默认 `9000`，**不要与 Web 工作台的 `8000` 混用**，两者是两个独立服务。
- 跨机器部署时建议显式设置 `MCP_AUDIO_DIR` 为绝对路径，避免音频文件写入预期之外的位置。
- 局域网中其他机器能否访问，还取决于服务器防火墙与该端口放行情况。

> **⚠️ 安全警告：HTTP 传输不提供任何身份校验。** 任何能访问该端口的机器都可以调用本服务的全部工具，并消耗你配置的 API Key 额度。因此：
>
> - 不要把 `MCP_SERVER_HOST=0.0.0.0` 的端口直接暴露到公网；
> - 在局域网内也应通过防火墙限制来源 IP，或使用带 IP 白名单 / 访问控制的反向代理；
> - 建议为该服务使用专用的低权限 API Key 并设置消费限额。
>
> 若只需自己使用，更安全的做法是保持默认的 `127.0.0.1` 并借助 SSH 端口转发访问。

启动 MCP 客户端前，需要先配置 API Key。可以在 Web 设置页添加，也可以通过环境变量提供初始 Key：

```powershell
$env:DASHSCOPE_API_KEY = "你的 API Key"
```

```bash
export DASHSCOPE_API_KEY="你的 API Key"
```

## 六、配置项

所有配置项均通过环境变量设置。未设置时使用默认值。

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 空 | 没有 `mcp_config.json` 时的初始 API Key |
| `DASHSCOPE_BASE_URL` | DashScope 国际站兼容地址 | 初始 Base URL |
| `DASHSCOPE_AUDIO_MODEL` | `qwen-omni-turbo` | MCP 请求使用的默认模型 |
| `DASHSCOPE_AUDIO_VOICE` | `Cherry` | 生成语音音色 |
| `DASHSCOPE_REGION` | `cn-beijing` | 服务区域标识 |
| `MCP_CONFIG_FILE` | 项目根目录 `mcp_config.json` | Web 与 MCP 共用的配置文件路径 |
| `MCP_WEB_HOST` | `127.0.0.1` | Web 监听地址（默认仅本机，局域网访问需显式设为 `0.0.0.0`） |
| `MCP_WEB_PORT` | `8000` | Web 监听端口 |
| `MCP_AUDIO_DIR` | `audio_files` | 输入、输出音频保存目录 |
| `MCP_DATABASE` | `audio_tasks.db` | SQLite 任务数据库路径 |
| `MCP_MAX_AUDIO_BYTES` | `25 MB` | 单个输入或输出音频的最大字节数 |
| `MCP_MAX_PROMPT_CHARS` | `4000` | MCP 提示词最大长度 |
| `MCP_MAX_TEXT_CHARS` | `20000` | 保存和返回的模型文字最大长度 |
| `MCP_MAX_RESPONSE_BYTES` | `50 MB` | Qwen 正常响应最大大小 |
| `MCP_MAX_ERROR_CHARS` | `2000` | 单条错误信息最大长度 |
| `MCP_MAX_CONCURRENT_TASKS` | `4` | MCP 同时处理的任务数 |
| `MCP_TRANSPORT` | `stdio` | MCP 传输方式；设为 `http` 后监听网络端口，供局域网客户端连接 |
| `MCP_SERVER_HOST` | `127.0.0.1` | MCP HTTP 模式的监听地址（仅 `MCP_TRANSPORT=http` 时生效） |
| `MCP_SERVER_PORT` | `9000` | MCP HTTP 模式的监听端口（仅 `MCP_TRANSPORT=http` 时生效） |
| `MCP_AUDIO_RETENTION_SECONDS` | `86400` | 音频文件保留时间，默认 24 小时 |
| `MCP_MAX_AUDIO_STORAGE_BYTES` | `1 GB` | 音频目录最大总容量 |
| `MCP_LOG_LEVEL` | `INFO` | 日志等级 |
| `MCP_LOG_FILE` | 空 | 可选日志文件路径；设置后启用滚动文件日志 |

例如，Windows 上使用 9000 端口并把音频保存到指定目录：

```powershell
$env:MCP_WEB_PORT = "9000"
$env:MCP_AUDIO_DIR = "D:\MCPAudio"
.\start_powershell.ps1
```

## 七、文件和数据说明

- `Front_End/index.html`、`app.js`、`style.css`：浏览器工作台。
- `Front_End/server.py`：静态页面服务器和 Web API。
- `BACK_End/MCP_SERVER.py`：FastMCP 服务及音频任务处理流程。
- `BACK_End/safe_Part.py`：Base64、格式和大小校验。
- `BACK_End/runtime_config.py`：Web 与 MCP 共用配置读写。
- `BACK_End/Data_Base.py`：SQLite 任务元数据持久化。
- `audio_files/`：运行时生成的输入、输出音频目录。
- `audio_tasks.db`：任务状态数据库；数据库只保存路径和任务元数据，不保存音频二进制和 API Key。
- `mcp_config.json`：本地配置文件，包含 API Key，应妥善保护。

服务启动时会自动创建 SQLite 表。音频文件会按保留时间清理；如果目录超过 `MCP_MAX_AUDIO_STORAGE_BYTES`，会优先删除较早的文件。

## 八、安全建议

1. 不要把 `mcp_config.json`、API Key 或生成的音频文件提交到公共仓库。
2. Web 服务默认只监听本机（`127.0.0.1`）。如需局域网或公网访问，应显式设置 `MCP_WEB_HOST=0.0.0.0`，并同时配置 `MCP_WEB_TOKEN`、防火墙或反向代理来限制来源。
3. 不要把未加认证的 Web 端口直接暴露到公网。
4. 生产环境应使用专用的低权限 API Key，并定期轮换。
5. 若日志写入文件，请限制日志文件访问权限；日志不应记录 API Key 或音频正文。

## 九、常见问题

### 页面打不开

确认 `Front_End/server.py` 正在运行，并访问启动脚本输出的端口。若修改了 `MCP_WEB_PORT`，请使用新端口访问。

### 提示没有 API Key

在 **API 设置** 中添加并选中一个 Key，或在启动服务前设置 `DASHSCOPE_API_KEY`。如果已经有 `mcp_config.json`，它的活动 Key 配置优先于环境变量。

### 提示音频格式不支持

当前安全校验只接受 `wav` 和 `mp3`。请转换音频格式后重新上传。

### Qwen API 返回网络或 HTTP 错误

检查 Base URL、API Key、模型名称和网络连接。Base URL 必须是完整的 HTTP/HTTPS 地址，且不能包含查询字符串或片段。

### MCP 客户端无法启动服务

检查配置中的 Python 路径和 `MCP_SERVER.py` 路径是否为绝对路径，并确认 `.venv` 已成功创建且已安装 `fastmcp`。

### 如何查看运行日志

默认日志输出到控制台。设置 `MCP_LOG_FILE` 后会额外写入滚动日志文件，例如：

```powershell
$env:MCP_LOG_FILE = "logs\mcp.log"
```

## 十、停止、升级与清理

停止启动脚本即可结束 Web 和 MCP 子进程。升级依赖时，在项目根目录执行：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade
```

Linux/macOS 使用：

```bash
.venv/bin/python -m pip install -r requirements.txt --upgrade
```

如果要清理历史运行数据，可在停止服务后删除 `audio_files/` 中的音频和 `audio_tasks.db`。删除 `mcp_config.json` 会同时移除本地保存的 API Key 配置；之后可重新通过环境变量或 Web 设置页配置。