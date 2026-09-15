$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = "py"
    $PythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = "python"
    $PythonArgs = @()
} else {
    throw "Python 3 was not found. Install Python and add it to PATH."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating Python virtual environment..."
    & $Python @PythonArgs -m venv ".venv"
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Failed to create Python virtual environment: $VenvPython"
}

Write-Host "Installing Python dependencies..."
& $VenvPython -m pip install -r "requirements.txt"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Python dependencies."
}

$env:PYTHONPATH = $ProjectRoot
$WebPort = if ($env:MCP_WEB_PORT) { $env:MCP_WEB_PORT } else { "8000" }
$WebProcess = Start-Process -FilePath $VenvPython `
    -ArgumentList @("Front_End\server.py") `
    -WorkingDirectory $ProjectRoot `
    -NoNewWindow `
    -PassThru
$McpProcess = Start-Process -FilePath $VenvPython `
    -ArgumentList @("BACK_End\MCP_SERVER.py") `
    -WorkingDirectory $ProjectRoot `
    -NoNewWindow `
    -PassThru

try {
    Write-Host "Web UI: http://localhost:$WebPort"
    Write-Host "Web UI LAN: http://<server-ip>:$WebPort"
    Write-Host "MCP service started. Press Ctrl+C to stop the project."
    Wait-Process -Id $WebProcess.Id
} finally {
    foreach ($Process in @($WebProcess, $McpProcess)) {
        if ($Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force
        }
    }
}