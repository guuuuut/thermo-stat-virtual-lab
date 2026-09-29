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
$analysisGenerator = Join-Path $projectRoot 'scripts\generate_pressure_analysis.py'
$pageBuilder = Join-Path $projectRoot 'scripts\build_pressure_diffusion_3d.py'
$analysisPageBuilder = Join-Path $projectRoot 'scripts\build_pressure_analysis_page.py'
$page = Join-Path $projectRoot 'visualization\pressure_diffusion.html'
$analysisPage = Join-Path $projectRoot 'visualization\pressure_analysis.html'
$archive = Join-Path $projectRoot 'downloads\pressure_diffusion_trajectories.zip'
$analysisCsv = Join-Path $projectRoot 'results\diffusion_pressure\diffusion_vs_pressure.csv'

if (-not $KeyPath) {
    $KeyPath = Join-Path $projectRoot 'secrets\aliyun-lighthouse-rsa-20260923'
}
$KeyPath = [IO.Path]::GetFullPath($KeyPath)

foreach ($required in @(
    $python,
    $analysisGenerator,
    $pageBuilder,
    $analysisPageBuilder,
    $analysisCsv,
    $KeyPath
)) {
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
$remoteAnalysisPage = "/tmp/visual-lab-$stamp-analysis.html"
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

    foreach ($name in @(
        'run_manifest.json',
        'summary.json',
        'diffusion_vs_pressure.csv',
        'msd_theory_curves.csv',
        'speed_distribution.csv'
    )) {
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
    $packagedCode = @(
        Get-ChildItem -LiteralPath $verifyRoot -Recurse -File -Filter '*.py'
    )
    if ($packagedCode.Count -ne 0) {
        throw 'Trajectory package must not contain complete Python source files.'
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
        "cp -p $remoteBackup/diffusion_vs_pressure.csv /var/www/visual-lab/results/diffusion_pressure/diffusion_vs_pressure.csv && " +
        "if test -f $remoteBackup/analysis-page.existed; then " +
        "cp -p $remoteBackup/pressure_analysis.html /var/www/visual-lab/pressure_analysis.html; " +
        "else rm -f /var/www/visual-lab/pressure_analysis.html; fi"
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @($serverTarget, $restore)) `
        -FailureMessage 'Automatic remote rollback failed'
}

try {
    Write-Host '[1/8] Generating MSD, diffusion, and speed-distribution analyses...'
    Invoke-NativeChecked `
        -Program $python `
        -Arguments @($analysisGenerator) `
        -FailureMessage 'Pressure analysis generation failed'

    Write-Host '[2/8] Building visualization and analysis HTML pages...'
    Invoke-NativeChecked `
        -Program $python `
        -Arguments @($pageBuilder) `
        -FailureMessage 'Visualization build failed'
    Invoke-NativeChecked `
        -Program $python `
        -Arguments @($analysisPageBuilder) `
        -FailureMessage 'Analysis-page build failed'
    if (-not (Test-Path -LiteralPath $page -PathType Leaf)) {
        throw "Visualization output missing: $page"
    }
    if (-not (Test-Path -LiteralPath $analysisPage -PathType Leaf)) {
        throw "Analysis-page output missing: $analysisPage"
    }

    Write-Host '[3/8] Rebuilding and validating trajectory package...'
    Build-TrajectoryPackage

    $localHashes = @{
        $remoteIndex = Get-Sha256 $page
        $remoteAnalysisPage = Get-Sha256 $analysisPage
        $remoteArchive = Get-Sha256 $archive
        $remoteCsv = Get-Sha256 $analysisCsv
    }

    Write-Host '[4/8] Checking SSH connectivity and remote targets...'
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @($serverTarget, "test ! -e $remoteBackup")) `
        -FailureMessage 'Remote backup path already exists or SSH failed'

    Write-Host '[5/8] Uploading both HTML pages, ZIP, CSV, and deployment script...'
    foreach ($item in @(
        @($page, $remoteIndex),
        @($analysisPage, $remoteAnalysisPage),
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
incoming_analysis=$3
incoming_archive=$4
incoming_csv=$5
health_host=$6
site=/var/www/visual-lab
backup="/root/visual-lab-backups/deploy-$stamp"
index="$site/index.html"
analysis="$site/pressure_analysis.html"
archive="$site/downloads/pressure_diffusion_trajectories.zip"
csv="$site/results/diffusion_pressure/diffusion_vs_pressure.csv"
index_next="$index.next"
analysis_next="$analysis.next"
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
        if [ -f "$backup/analysis-page.existed" ]; then
            cp -p "$backup/pressure_analysis.html" "$analysis"
        else
            rm -f "$analysis"
        fi
    fi
    rm -f "$index_next" "$analysis_next" "$archive_next" "$csv_next"
    exit "$status"
}
trap restore_and_cleanup EXIT HUP INT TERM

test -f "$incoming_index"
test -f "$incoming_analysis"
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
if [ -f "$analysis" ]; then
    cp -p "$analysis" "$backup/pressure_analysis.html"
    touch "$backup/analysis-page.existed"
fi

install -m 644 "$incoming_index" "$index_next"
install -m 644 "$incoming_analysis" "$analysis_next"
install -m 644 "$incoming_archive" "$archive_next"
install -m 644 "$incoming_csv" "$csv_next"

deployed=1
mv "$index_next" "$index"
mv "$analysis_next" "$analysis"
mv "$archive_next" "$archive"
mv "$csv_next" "$csv"

systemctl is-active --quiet nginx
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/'
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/pressure_analysis.html'
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

    $uploadedHashes = Get-RemoteHashes @(
        $remoteIndex,
        $remoteAnalysisPage,
        $remoteArchive,
        $remoteCsv
    )
    foreach ($path in $localHashes.Keys) {
        if (-not $uploadedHashes.ContainsKey($path) -or $uploadedHashes[$path] -ne $localHashes[$path]) {
            throw "Uploaded SHA-256 mismatch: $path"
        }
    }

    Write-Host '[6/8] Creating backups and switching files atomically...'
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @(
            $serverTarget,
            "sh $remoteScript $stamp $remoteIndex $remoteAnalysisPage $remoteArchive $remoteCsv $ServerAddress"
        )) `
        -FailureMessage 'Remote deployment failed; server-side rollback was attempted'
    $deploymentApplied = $true

    $livePaths = @(
        '/var/www/visual-lab/index.html',
        '/var/www/visual-lab/pressure_analysis.html',
        '/var/www/visual-lab/downloads/pressure_diffusion_trajectories.zip',
        '/var/www/visual-lab/results/diffusion_pressure/diffusion_vs_pressure.csv'
    )
    $liveHashes = Get-RemoteHashes $livePaths
    foreach ($comparison in @(
        @($livePaths[0], $localHashes[$remoteIndex]),
        @($livePaths[1], $localHashes[$remoteAnalysisPage]),
        @($livePaths[2], $localHashes[$remoteArchive]),
        @($livePaths[3], $localHashes[$remoteCsv])
    )) {
        if (-not $liveHashes.ContainsKey($comparison[0]) -or $liveHashes[$comparison[0]] -ne $comparison[1]) {
            throw "Live SHA-256 mismatch: $($comparison[0])"
        }
    }

    Write-Host '[7/8] Verifying public pages and downloads...'
    try {
        $pageResponse = Invoke-WebRequest -Uri "$publicBase/" -TimeoutSec 45
        if ([int]$pageResponse.StatusCode -ne 200 -or -not $pageResponse.Content.Contains('六面反射墙')) {
            throw 'Public page did not return the expected visualization.'
        }
        $analysisResponse = Invoke-WebRequest -Uri "$publicBase/pressure_analysis.html" -TimeoutSec 45
        if (
            [int]$analysisResponse.StatusCode -ne 200 -or
            -not $analysisResponse.Content.Contains('Maxwell 理论') -or
            -not $analysisResponse.Content.Contains('均方位移与扩散模型')
        ) {
            throw 'Public analysis page did not return the expected content.'
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

    Write-Host '[8/8] Deployment complete.'
    Write-Host "Page: $publicBase/"
    Write-Host "Analysis: $publicBase/pressure_analysis.html"
    Write-Host "ZIP SHA-256: $(Get-Sha256 $archive)"
    Write-Host "CSV SHA-256: $(Get-Sha256 $analysisCsv)"
    Write-Host "Remote backup: $remoteBackup"
}
finally {
    $cleanupCommand = "rm -f -- $remoteIndex $remoteAnalysisPage $remoteArchive $remoteCsv $remoteScript"
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
