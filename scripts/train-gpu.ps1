param(
    [ValidateSet('check','prepare','pilot','nested','four','publish')][string]$Mode = 'pilot',
    [string]$Source = "data/comparacion-cuatro",
    [string]$Profile = 'resnet50_nested_laptop',
    [string]$Python = "$env:USERPROFILE\.venvs\papasana312\Scripts\python.exe"
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath (Join-Path $repoRoot 'ml')
if (-not (Test-Path -LiteralPath $Python)) { throw "No existe el entorno CUDA: $Python. Consulta docs/reentrenamiento.md." }
$env:MLFLOW_TRACKING_URI = 'sqlite:///' + ((Join-Path $PWD 'mlflow.db') -replace '\\','/')
$env:MLFLOW_ENABLE_TELEMETRY = 'false'
$env:MLFLOW_DISABLE_AGENT_HINT = '1'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HOME = Join-Path $PWD 'data\cache\huggingface'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
if ($Mode -ne 'publish') {
    & $Python -X utf8 -u -m potato_blight.gpu_check
    if ($LASTEXITCODE -ne 0) { throw 'La comprobación CUDA falló.' }
}
switch ($Mode) {
    'prepare' {
        & $Python -X utf8 -u -m potato_blight.download_public
        if ($LASTEXITCODE -ne 0) { throw 'Descarga incompleta.' }
        & $Python -X utf8 -u -m potato_blight.prepare --config configs/base.yaml
        if ($LASTEXITCODE -ne 0) { throw 'Preparación fallida.' }
        & $Python -X utf8 -u -m potato_blight.eda
    }
    'pilot' {
        & $Python -X utf8 -u -m potato_blight.pilot
        if ($LASTEXITCODE -ne 0) { throw 'El piloto falló.' }
        & $Python -X utf8 -u -m potato_blight.report_pilot
    }
    'nested' { & $Python -X utf8 -u -m potato_blight.nested --config "configs/$Profile.yaml" }
    'four' { & $Python -X utf8 -u -m potato_blight.four_models }
    'publish' { & $Python -X utf8 -u -m potato_blight.publication --source $Source }
}
if ($LASTEXITCODE -ne 0) { throw 'La operación ML terminó con error.' }
