$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$node = "C:\Users\SSAFY\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$python = "python"
$logs = Join-Path $root "logs"

if (Test-Path (Join-Path $root ".venv\Scripts\python.exe")) {
  $python = (Resolve-Path (Join-Path $root ".venv\Scripts\python.exe")).Path
}

New-Item -ItemType Directory -Path $logs -Force | Out-Null

Write-Host "Starting HEOGAONV3 backend on http://127.0.0.1:4100"
Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList @(
  "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "4100"
) -WorkingDirectory (Join-Path $root "backend") `
  -RedirectStandardOutput (Join-Path $logs "backend.out.log") `
  -RedirectStandardError (Join-Path $logs "backend.err.log")

Write-Host "Starting HEOGAONV3 frontend on http://127.0.0.1:3103"
Start-Process -WindowStyle Hidden -FilePath $node -ArgumentList @(
  ".\node_modules\next\dist\bin\next", "start", "--hostname", "127.0.0.1", "--port", "3103"
) -WorkingDirectory $root `
  -RedirectStandardOutput (Join-Path $logs "frontend.out.log") `
  -RedirectStandardError (Join-Path $logs "frontend.err.log")

Write-Host "Open http://127.0.0.1:3103"
