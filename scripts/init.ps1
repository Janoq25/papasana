# Prepara el entorno local: crea .env con secretos aleatorios y verifica Docker.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\init.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
$example = Join-Path $root ".env.example"

function New-Secret([int]$bytes = 32) {
    $b = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return ([BitConverter]::ToString($b) -replace '-', '').ToLower()
}

if (Test-Path $envFile) {
    # Variables agregadas en fases posteriores: se completan sin tocar los secretos existentes
    $current = Get-Content $envFile -Raw
    if ($current -notmatch '(?m)^MLFLOW_DB_PASSWORD=.+') {
        Add-Content $envFile "`nMLFLOW_DB_PASSWORD=$(New-Secret)`nMLFLOW_UI_URL=http://127.0.0.1:5000"
        Write-Host ".env ya existía; se agregó MLFLOW_DB_PASSWORD." -ForegroundColor Yellow
    } else {
        Write-Host ".env ya existe; no se modifica." -ForegroundColor Yellow
    }
} else {
    $demo = "Demo-" + (New-Secret 9) + "1a"
    $content = Get-Content $example -Raw
    $content = $content -replace '(?m)^POSTGRES_PASSWORD=$', "POSTGRES_PASSWORD=$(New-Secret)"
    $content = $content -replace '(?m)^APP_DB_PASSWORD=$', "APP_DB_PASSWORD=$(New-Secret)"
    $content = $content -replace '(?m)^JWT_SECRET=$', "JWT_SECRET=$(New-Secret 48)"
    $content = $content -replace '(?m)^MINIO_ROOT_PASSWORD=$', "MINIO_ROOT_PASSWORD=$(New-Secret)"
    $content = $content -replace '(?m)^ML_SERVICE_TOKEN=$', "ML_SERVICE_TOKEN=$(New-Secret 24)"
    $content = $content -replace '(?m)^MLFLOW_DB_PASSWORD=$', "MLFLOW_DB_PASSWORD=$(New-Secret)"
    $content = $content -replace '(?m)^DEMO_USERS_PASSWORD=$', "DEMO_USERS_PASSWORD=$demo"
    [System.IO.File]::WriteAllText($envFile, $content.Replace("`r`n", "`n"))
    Write-Host ".env creado con secretos aleatorios." -ForegroundColor Green
    Write-Host "Contraseña de los usuarios demo: $demo" -ForegroundColor Cyan
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker no está en ejecución. Abra Docker Desktop y vuelva a intentarlo." -ForegroundColor Red
    exit 1
}
Write-Host "Docker está listo. Ejecute:  docker compose up -d --build" -ForegroundColor Green
