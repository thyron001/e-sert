# Demo de e-sert en un comando (Windows PowerShell). Usa el .venv de la demo o del backend si existe.
#   .\demo\demo.ps1                # remoto (VPS) con caída automática a local
#   .\demo\demo.ps1 --local        # plan B sin internet
$ErrorActionPreference = "Stop"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($Venv in @((Join-Path $Aqui ".venv"), (Join-Path $Aqui "..\backend\.venv"))) {
    $Activar = Join-Path $Venv "Scripts\Activate.ps1"
    if (Test-Path $Activar) { . $Activar; break }
}
python (Join-Path $Aqui "demo.py") @args
exit $LASTEXITCODE
