$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
& "$projectRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "$PSScriptRoot" --reload --host 127.0.0.1 --port 8000
