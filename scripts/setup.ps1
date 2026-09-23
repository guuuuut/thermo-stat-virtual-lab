[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirements = Join-Path $projectRoot "requirements.txt"
$msmpiRuntime = "C:\Windows\System32\msmpi.dll"

if (-not (Test-Path $msmpiRuntime)) {
    throw "Microsoft MPI runtime is missing. Run .\scripts\install_msmpi.ps1 from an elevated PowerShell first."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating isolated environment at $venvRoot"
    & $Python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the virtual environment." }
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

# Requiring binary wheels prevents an accidental local LAMMPS source build.
& $venvPython -m pip install --only-binary=:all: --requirement $requirements
if ($LASTEXITCODE -ne 0) { throw "Failed to install the Demo dependencies." }

& $venvPython -c "import lammps, numpy, matplotlib; print('Python environment OK'); print('LAMMPS Python package:', lammps.__version__)"
if ($LASTEXITCODE -ne 0) { throw "The installed environment failed its import check." }

Write-Host "Setup complete. Run .\scripts\run_demo.ps1 next."
