$ErrorActionPreference = "Stop"
$McpRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $McpRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  throw "MCP environment not installed. Run .\install.ps1 first."
}
$env:PYTHONPATH = $McpRoot
& $Python -m nas_deploy_mcp.server

