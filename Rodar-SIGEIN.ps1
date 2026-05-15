Param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000
)

# Descobre a pasta do projeto (onde está este script)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvActivate = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"

if (-not (Test-Path $VenvActivate)) {
    Write-Error "Ambiente virtual não encontrado em '$VenvActivate'. Crie a venv primeiro (python -m venv venv)."
    exit 1
}

Write-Host "Ativando venv..." -ForegroundColor Cyan
& $VenvActivate

Write-Host "Subindo SIGEIN com Uvicorn em http://$BindHost`:$Port ..." -ForegroundColor Green
uvicorn main:app --host $BindHost --port $Port --reload

