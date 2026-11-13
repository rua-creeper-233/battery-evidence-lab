param(
    [int]$Port = 8765
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
. (Join-Path $scriptRoot "python.ps1")
$pythonExe = Resolve-BatteryPython -ProjectRoot $projectRoot

if (-not $pythonExe) {
    Write-Error "未找到带 pypdf 的 Python。请在项目目录运行：python -m pip install -r requirements.txt"
    exit 1
}

$url = "http://127.0.0.1:$Port"
Write-Host "Battery Evidence Lab 正在启动：$url"
Write-Host "保持此窗口开启；按 Ctrl+C 停止。"
Push-Location $projectRoot
try {
    & $pythonExe -m battery_lab.server --port $Port
} finally {
    Pop-Location
}
