param(
  [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$McpRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Python) {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) { $Python = $pythonCommand.Source }
}
if (-not $Python) {
  throw "Python 3.11+ was not found. Pass -Python with the Python executable path."
}

& $Python -m venv (Join-Path $McpRoot ".venv")
$venvPython = Join-Path $McpRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $McpRoot "requirements.txt")
Write-Host "MCP environment installed at $McpRoot\.venv"
Write-Host "Copy .env.example to .env and fill NAS credentials before starting."

