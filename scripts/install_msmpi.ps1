[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$runtimeDll = "C:\Windows\System32\msmpi.dll"
if (Test-Path $runtimeDll) {
    Write-Host "MS-MPI runtime is already installed: $runtimeDll"
    exit 0
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$downloadRoot = Join-Path $projectRoot ".cache"
$installer = Join-Path $downloadRoot "msmpisetup.exe"
$uri = "https://download.microsoft.com/download/a/5/2/a5207ca5-1203-491a-8fb8-906fd68ae623/msmpisetup.exe"
$expectedSha256 = "C305CE3F05D142D519F8DD800D83A4B894FC31BCAD30512CEFB557FEACCBE8B4"

New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
Write-Host "Downloading Microsoft MPI runtime ..."
Invoke-WebRequest -Uri $uri -OutFile $installer

$actualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
if ($actualSha256 -ne $expectedSha256) {
    throw "MS-MPI installer hash mismatch: $actualSha256"
}

Write-Host "Installing Microsoft MPI runtime (SDK is not required) ..."
$process = Start-Process -FilePath $installer -ArgumentList "-unattend" -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "MS-MPI installation failed with exit code $($process.ExitCode)."
}
if (-not (Test-Path $runtimeDll)) {
    throw "MS-MPI installer completed, but $runtimeDll was not found. Reopen PowerShell or restart Windows, then retry."
}

Write-Host "MS-MPI runtime installed successfully."
