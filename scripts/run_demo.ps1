[CmdletBinding()]
param(
    [double]$Temperature = 1.2,
    [double]$Density = 0.8,
    [ValidateRange(2, 12)][int]$Cells = 4,
    [ValidateRange(1, 2147483646)][int]$Seed = 20260824,
    [ValidateRange(0, 10000000)][int]$EquilSteps = 5000,
    [ValidateRange(1, 10000000)][int]$ProdSteps = 10000,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$lmp = Join-Path $projectRoot ".venv\Scripts\lmp.exe"
$resultsRoot = Join-Path $projectRoot "results"

if (-not (Test-Path $venvPython) -or -not (Test-Path $lmp)) {
    throw "LAMMPS environment is missing. Run .\scripts\setup.ps1 first."
}
if ($Temperature -le 0.0) { throw "Temperature must be positive." }
if ($Density -le 0.0 -or $Density -gt 1.4) { throw "For this LJ Demo, Density must be in (0, 1.4]." }

New-Item -ItemType Directory -Force -Path $resultsRoot | Out-Null
$helpText = & $lmp -help 2>&1
$versionLine = $helpText | Where-Object { $_ -match "Large-scale Atomic/Molecular" } | Select-Object -First 1
if (-not $versionLine) { $versionLine = "LAMMPS executable version could not be detected" }
$versionLine | Set-Content -Encoding UTF8 (Join-Path $resultsRoot "lammps_version.txt")

function Invoke-LammpsCase {
    param([string]$Name, [string]$InputFile)

    $caseRoot = if ($ValidateOnly) {
        Join-Path (Join-Path $resultsRoot "validation") $Name
    } else {
        Join-Path $resultsRoot $Name
    }
    New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null
    $inputPath = (Resolve-Path (Join-Path $projectRoot $InputFile)).Path
    $arguments = @(
        "-in", $inputPath,
        "-log", "log.lammps",
        "-screen", "screen.txt",
        "-var", "temperature", $Temperature.ToString([Globalization.CultureInfo]::InvariantCulture),
        "-var", "density", $Density.ToString([Globalization.CultureInfo]::InvariantCulture),
        "-var", "cells", $Cells,
        "-var", "seed", $Seed,
        "-var", "equil_steps", $EquilSteps,
        "-var", "prod_steps", $ProdSteps
    )
    if ($ValidateOnly) { $arguments = @("-skiprun") + $arguments }

    Write-Host "Running $Name ..."
    Push-Location $caseRoot
    try {
        & $lmp @arguments
        if ($LASTEXITCODE -ne 0) { throw "LAMMPS case '$Name' failed. See $caseRoot\screen.txt" }
    }
    finally {
        Pop-Location
    }
}

Invoke-LammpsCase -Name "nve" -InputFile "lammps\in.lj_nve"
Invoke-LammpsCase -Name "nvt" -InputFile "lammps\in.lj_nvt"

if ($ValidateOnly) {
    Write-Host "Both input scripts passed LAMMPS parsing in -skiprun mode."
    exit 0
}

& $venvPython (Join-Path $PSScriptRoot "analyze_results.py") --results $resultsRoot --target-temperature $Temperature
if ($LASTEXITCODE -ne 0) { throw "Post-processing or physical smoke checks failed." }

Write-Host "Demo complete. Open results\comparison.png and results\summary.json."
