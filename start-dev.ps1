$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeBin = "C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$pnpm = "C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd"
$backend = Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --app-dir `"$projectRoot\backend`" --host 127.0.0.1 --port 8000" -WorkingDirectory $projectRoot -PassThru
$env:PATH = "$nodeBin;$env:PATH"
$frontend = Start-Process -FilePath $pnpm -ArgumentList "dev" -WorkingDirectory "$projectRoot\frontend" -PassThru
Write-Host "Backend PID: $($backend.Id)"
Write-Host "Frontend PID: $($frontend.Id)"
Write-Host "Open http://127.0.0.1:5173"
