[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9.-]+$')]
    [string]$ServerAddress = '47.117.150.153',

    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_-]*$')]
    [string]$RemoteUser = 'root',

    [string]$KeyPath,

    [string]$PublicBaseUrl = 'http://47.117.150.153',

    [switch]$KeepTemporaryFiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cacheRoot = Join-Path $projectRoot '.cache'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pageBuilder = Join-Path $projectRoot 'scripts\build_pressure_diffusion_3d.py'
$page = Join-Path $projectRoot 'visualization\pressure_diffusion.html'
$archive = Join-Path $projectRoot 'downloads\pressure_diffusion_trajectories.zip'
$analysisCsv = Join-Path $projectRoot 'results\diffusion_pressure\diffusion_vs_pressure.csv'
$exampleScript = Join-Path $projectRoot 'downloads\examples\analyze_mixing.py'

if (-not $KeyPath) {
    $KeyPath = Join-Path $projectRoot 'secrets\aliyun-lighthouse-rsa-20260923'
}
$KeyPath = [IO.Path]::GetFullPath($KeyPath)

foreach ($required in @($python, $pageBuilder, $analysisCsv, $exampleScript, $KeyPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file not found: $required"
    }
}

$publicUri = [uri]$PublicBaseUrl
if ($publicUri.Scheme -notin @('http', 'https') -or -not $publicUri.Host) {
    throw 'PublicBaseUrl must be an absolute HTTP or HTTPS URL.'
}
$publicBase = $PublicBaseUrl.TrimEnd('/')
$serverTarget = "$RemoteUser@$ServerAddress"
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'

New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
$tempRoot = Join-Path $cacheRoot "deploy-$stamp-$PID"
$packageRoot = Join-Path $tempRoot 'package'
$verifyRoot = Join-Path $tempRoot 'verify'
$newArchive = Join-Path $tempRoot 'pressure_diffusion_trajectories.zip'
$remoteScriptLocal = Join-Path $tempRoot 'deploy-site.sh'
$publicArchive = Join-Path $tempRoot 'public-archive.zip'
$publicCsv = Join-Path $tempRoot 'public-diffusion.csv'
New-Item -ItemType Directory -Path $tempRoot, $packageRoot | Out-Null

$remoteIndex = "/tmp/visual-lab-$stamp-index.html"
$remoteArchive = "/tmp/visual-lab-$stamp-trajectories.zip"
$remoteCsv = "/tmp/visual-lab-$stamp-diffusion.csv"
$remoteScript = "/tmp/visual-lab-$stamp-deploy.sh"
$remoteBackup = "/root/visual-lab-backups/deploy-$stamp"
$deploymentApplied = $false

$sshArgs = @(
    '-i', $KeyPath,
    '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=yes'
)

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory)][string]$Program,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$FailureMessage
    )
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)"
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Copy-RequiredFile {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Package source not found: $Source"
    }
    Copy-Item -LiteralPath $Source -Destination $Destination
}

function Build-TrajectoryPackage {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    Copy-RequiredFile `
        (Join-Path $projectRoot 'downloads\README_trajectories.md') `
        (Join-Path $packageRoot 'README.md')
    Copy-Item `
        -LiteralPath (Join-Path $projectRoot 'downloads\examples') `
        -Destination (Join-Path $packageRoot 'examples') `
        -Recurse

    $lammpsRoot = Join-Path $packageRoot 'lammps'
    $previewRoot = Join-Path $packageRoot 'preview'
    $analysisRoot = Join-Path $packageRoot 'analysis'
    New-Item -ItemType Directory -Path $lammpsRoot, $previewRoot, $analysisRoot | Out-Null

    foreach ($name in @(
        'in.lj_diffusion_pressure',
        'in.lj_diffusion_pressure_reflective_preview'
    )) {
        Copy-RequiredFile `
            (Join-Path $projectRoot "lammps\$name") `
            (Join-Path $lammpsRoot $name)
    }

    Copy-RequiredFile `
        (Join-Path $projectRoot 'results\diffusion_pressure_preview\run_manifest.json') `
        (Join-Path $previewRoot 'run_manifest.json')

    foreach ($name in @('run_manifest.json', 'summary.json', 'diffusion_vs_pressure.csv')) {
        Copy-RequiredFile `
            (Join-Path $projectRoot "results\diffusion_pressure\$name") `
            (Join-Path $analysisRoot $name)
    }

    foreach ($suffix in @('0p10', '0p20', '0p30', '0p40', '0p50')) {
        $case = "p_$suffix"
        $previewCase = Join-Path $previewRoot $case
        $analysisCase = Join-Path $analysisRoot $case
        New-Item -ItemType Directory -Path $previewCase, $analysisCase | Out-Null

        Copy-RequiredFile `
            (Join-Path $projectRoot "results\diffusion_pressure_preview\$case\trajectory.lammpstrj") `
            (Join-Path $previewCase 'trajectory.lammpstrj')

        foreach ($name in @('trajectory.lammpstrj', 'msd.csv', 'thermo.csv')) {
            Copy-RequiredFile `
                (Join-Path $projectRoot "results\diffusion_pressure\$case\$name") `
                (Join-Path $analysisCase $name)
        }
    }

    Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $newArchive -CompressionLevel Optimal
    Expand-Archive -LiteralPath $newArchive -DestinationPath $verifyRoot

    $packageFiles = Get-ChildItem -LiteralPath $verifyRoot -Recurse -File
    if ($packageFiles.Count -ne 29) {
        throw "Trajectory package must contain 29 files; found $($packageFiles.Count)."
    }
    $readme = [IO.File]::ReadAllText((Join-Path $verifyRoot 'README.md'), $utf8)
    if (-not $readme.Contains('五组压强 LJ 气体扩散轨迹数据说明')) {
        throw 'The packaged README is missing the expected Chinese heading.'
    }

    Push-Location $verifyRoot
    try {
        Invoke-NativeChecked `
            -Program $python `
            -Arguments @('examples\analyze_mixing.py', '--output', 'examples\mixing_deploy_check.csv') `
            -FailureMessage 'Packaged mixing example failed'
    }
    finally {
        Pop-Location
    }

    Copy-Item -LiteralPath $newArchive -Destination $archive -Force
}

function Get-RemoteHashes {
    param([Parameter(Mandatory)][string[]]$Paths)
    $command = 'sha256sum ' + ($Paths -join ' ')
    $lines = & ssh @sshArgs $serverTarget $command
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to read remote SHA-256 values.'
    }
    $hashes = @{}
    foreach ($line in $lines) {
        if ($line -match '^([0-9a-fA-F]{64})\s+(.+)$') {
            $hashes[$matches[2].Trim()] = $matches[1].ToLowerInvariant()
        }
    }
    return $hashes
}

function Restore-RemoteBackup {
    Write-Warning "Public verification failed; restoring $remoteBackup"
    $restore = "cp -p $remoteBackup/index.html /var/www/visual-lab/index.html && " +
        "cp -p $remoteBackup/pressure_diffusion_trajectories.zip /var/www/visual-lab/downloads/pressure_diffusion_trajectories.zip && " +
        "cp -p $remoteBackup/diffusion_vs_pressure.csv /var/www/visual-lab/results/diffusion_pressure/diffusion_vs_pressure.csv"
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @($serverTarget, $restore)) `
        -FailureMessage 'Automatic remote rollback failed'
}

try {
    Write-Host '[1/7] Building visualization HTML...'
    Invoke-NativeChecked `
        -Program $python `
        -Arguments @($pageBuilder) `
        -FailureMessage 'Visualization build failed'
    if (-not (Test-Path -LiteralPath $page -PathType Leaf)) {
        throw "Visualization output missing: $page"
    }

    Write-Host '[2/7] Rebuilding and validating trajectory package...'
    Build-TrajectoryPackage

    $localHashes = @{
        $remoteIndex = Get-Sha256 $page
        $remoteArchive = Get-Sha256 $archive
        $remoteCsv = Get-Sha256 $analysisCsv
    }

    Write-Host '[3/7] Checking SSH connectivity and remote targets...'
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @($serverTarget, "test ! -e $remoteBackup")) `
        -FailureMessage 'Remote backup path already exists or SSH failed'

    Write-Host '[4/7] Uploading HTML, ZIP, CSV, and deployment script...'
    foreach ($item in @(
        @($page, $remoteIndex),
        @($archive, $remoteArchive),
        @($analysisCsv, $remoteCsv)
    )) {
        Invoke-NativeChecked `
            -Program 'scp' `
            -Arguments ($sshArgs + @($item[0], "${serverTarget}:$($item[1])")) `
            -FailureMessage "Upload failed: $($item[0])"
    }

    $remoteDeployContent = @'
#!/bin/sh
set -eu

stamp=$1
incoming_index=$2
incoming_archive=$3
incoming_csv=$4
health_host=$5
site=/var/www/visual-lab
backup="/root/visual-lab-backups/deploy-$stamp"
index="$site/index.html"
archive="$site/downloads/pressure_diffusion_trajectories.zip"
csv="$site/results/diffusion_pressure/diffusion_vs_pressure.csv"
index_next="$index.next"
archive_next="$archive.next"
csv_next="$csv.next"
deployed=0

restore_and_cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    if [ "$status" -ne 0 ] && [ "$deployed" -eq 1 ]; then
        cp -p "$backup/index.html" "$index"
        cp -p "$backup/pressure_diffusion_trajectories.zip" "$archive"
        cp -p "$backup/diffusion_vs_pressure.csv" "$csv"
    fi
    rm -f "$index_next" "$archive_next" "$csv_next"
    exit "$status"
}
trap restore_and_cleanup EXIT HUP INT TERM

test -f "$incoming_index"
test -f "$incoming_archive"
test -f "$incoming_csv"
test -f "$index"
test -f "$archive"
test -f "$csv"
test ! -e "$backup"

install -d -m 700 "$backup"
cp -p "$index" "$backup/index.html"
cp -p "$archive" "$backup/pressure_diffusion_trajectories.zip"
cp -p "$csv" "$backup/diffusion_vs_pressure.csv"

install -m 644 "$incoming_index" "$index_next"
install -m 644 "$incoming_archive" "$archive_next"
install -m 644 "$incoming_csv" "$csv_next"

deployed=1
mv "$index_next" "$index"
mv "$archive_next" "$archive"
mv "$csv_next" "$csv"

systemctl is-active --quiet nginx
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/'
curl --fail --silent --show-error --output /dev/null --head --header "Host: $health_host" 'http://127.0.0.1/downloads/pressure_diffusion_trajectories.zip'
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/results/diffusion_pressure/diffusion_vs_pressure.csv'
'@
    $remoteDeployContent = $remoteDeployContent.Replace("`r`n", "`n")
    [IO.File]::WriteAllText(
        $remoteScriptLocal,
        $remoteDeployContent + "`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
    Invoke-NativeChecked `
        -Program 'scp' `
        -Arguments ($sshArgs + @($remoteScriptLocal, "${serverTarget}:$remoteScript")) `
        -FailureMessage 'Deployment-script upload failed'

    $uploadedHashes = Get-RemoteHashes @($remoteIndex, $remoteArchive, $remoteCsv)
    foreach ($path in $localHashes.Keys) {
        if (-not $uploadedHashes.ContainsKey($path) -or $uploadedHashes[$path] -ne $localHashes[$path]) {
            throw "Uploaded SHA-256 mismatch: $path"
        }
    }

    Write-Host '[5/7] Creating backups and switching files atomically...'
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @(
            $serverTarget,
            "sh $remoteScript $stamp $remoteIndex $remoteArchive $remoteCsv $ServerAddress"
        )) `
        -FailureMessage 'Remote deployment failed; server-side rollback was attempted'
    $deploymentApplied = $true

    $livePaths = @(
        '/var/www/visual-lab/index.html',
        '/var/www/visual-lab/downloads/pressure_diffusion_trajectories.zip',
        '/var/www/visual-lab/results/diffusion_pressure/diffusion_vs_pressure.csv'
    )
    $liveHashes = Get-RemoteHashes $livePaths
    foreach ($comparison in @(
        @($livePaths[0], $localHashes[$remoteIndex]),
        @($livePaths[1], $localHashes[$remoteArchive]),
        @($livePaths[2], $localHashes[$remoteCsv])
    )) {
        if (-not $liveHashes.ContainsKey($comparison[0]) -or $liveHashes[$comparison[0]] -ne $comparison[1]) {
            throw "Live SHA-256 mismatch: $($comparison[0])"
        }
    }

    Write-Host '[6/7] Verifying public page and downloads...'
    try {
        $pageResponse = Invoke-WebRequest -Uri "$publicBase/" -TimeoutSec 45
        if ([int]$pageResponse.StatusCode -ne 200 -or -not $pageResponse.Content.Contains('六面反射墙')) {
            throw 'Public page did not return the expected visualization.'
        }

        Invoke-WebRequest `
            -Uri "$publicBase/downloads/pressure_diffusion_trajectories.zip" `
            -OutFile $publicArchive `
            -TimeoutSec 180
        if ((Get-Sha256 $publicArchive) -ne (Get-Sha256 $archive)) {
            throw 'Public trajectory ZIP SHA-256 mismatch.'
        }

        Invoke-WebRequest `
            -Uri "$publicBase/results/diffusion_pressure/diffusion_vs_pressure.csv" `
            -OutFile $publicCsv `
            -TimeoutSec 60
        if ((Get-Sha256 $publicCsv) -ne (Get-Sha256 $analysisCsv)) {
            throw 'Public CSV SHA-256 mismatch.'
        }
    }
    catch {
        Restore-RemoteBackup
        $deploymentApplied = $false
        throw
    }

    Write-Host '[7/7] Deployment complete.'
    Write-Host "Page: $publicBase/"
    Write-Host "ZIP SHA-256: $(Get-Sha256 $archive)"
    Write-Host "CSV SHA-256: $(Get-Sha256 $analysisCsv)"
    Write-Host "Remote backup: $remoteBackup"
}
finally {
    $cleanupCommand = "rm -f -- $remoteIndex $remoteArchive $remoteCsv $remoteScript"
    & ssh @sshArgs $serverTarget $cleanupCommand 2>$null | Out-Null

    if (-not $KeepTemporaryFiles -and (Test-Path -LiteralPath $tempRoot)) {
        $resolvedCache = (Resolve-Path -LiteralPath $cacheRoot).Path
        $resolvedTemp = (Resolve-Path -LiteralPath $tempRoot).Path
        if (-not $resolvedTemp.StartsWith($resolvedCache + [IO.Path]::DirectorySeparatorChar)) {
            throw "Unsafe temporary cleanup target: $resolvedTemp"
        }
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
