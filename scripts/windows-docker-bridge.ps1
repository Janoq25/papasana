param([switch]$Stop)
$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$bridgeFile = Join-Path $PSScriptRoot "windows-docker-bridge.py"
$stateDir = Join-Path $projectDir "ml/data/deployment"
$pidFile = Join-Path $stateDir "windows-bridge.pid"
if ($Stop) {
    if (Test-Path -LiteralPath $pidFile) {
        $bridgePid = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $bridgePid"
        if ($processInfo -and $processInfo.CommandLine -like "*windows-docker-bridge.py*") {
            Stop-Process -Id $bridgePid
            Write-Output "Puente local detenido."
        } else {
            Write-Output "No hay un proceso del puente asociado al PID guardado."
        }
    }
    return
}
try {
    $health = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:18080/api/health" -TimeoutSec 3
    if ($health.StatusCode -eq 200) {
        Write-Output "PapaSana ya responde en http://127.0.0.1:18080"
        return
    }
} catch {}
$pythonPath = Join-Path $env:USERPROFILE ".venvs/papasana312/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
}
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$bridge = Start-Process -FilePath $pythonPath -ArgumentList ('"' + $bridgeFile + '"') -WorkingDirectory $projectDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $stateDir "windows-bridge.out.log") -RedirectStandardError (Join-Path $stateDir "windows-bridge.err.log") -PassThru
$bridge.Id | Set-Content -LiteralPath $pidFile
Write-Output "Puente iniciado en http://127.0.0.1:18080"

