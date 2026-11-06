$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = (Get-Command python.exe).Source
try {
    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/status' -TimeoutSec 2
} catch {
    Start-Process -FilePath $pythonExecutable -ArgumentList ('"' + (Join-Path $projectDirectory 'mikro_bridge.py') + '"') -WorkingDirectory $projectDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectDirectory 'docs\bridge-output.log') -RedirectStandardError (Join-Path $projectDirectory 'docs\bridge-error.log')
    Start-Sleep -Seconds 2
}
Start-Process 'http://127.0.0.1:8765/'
