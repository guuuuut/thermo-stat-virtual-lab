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
$learningPage = Join-Path $projectRoot 'visualization\learning.html'
$homeworkBuilder = Join-Path $projectRoot 'scripts\build_homework_materials.py'
$homeworkPage = Join-Path $projectRoot 'visualization\homework.html'
$homeworkArchive = Join-Path $projectRoot 'downloads\homework_20261027.zip'
$mainPageMarker = '<meta name="visual-lab-page" content="pressure-diffusion-v1">'
$learningPageMarker = '<meta name="visual-lab-page" content="learning-guide-v1">'
$homeworkPageMarker = '<meta name="visual-lab-page" content="homework-six-choice-v1">'
$packageReadmeMarker = '<!-- visual-lab-package: pressure-diffusion-v1 -->'
$archive = Join-Path $projectRoot 'downloads\pressure_diffusion_trajectories.zip'

if (-not $KeyPath) {
    $KeyPath = Join-Path $projectRoot 'secrets\aliyun-lighthouse-rsa-20260923'
}
$KeyPath = [IO.Path]::GetFullPath($KeyPath)

foreach ($required in @(
    $python,
    $pageBuilder,
    $homeworkBuilder,
    $learningPage,
    $KeyPath
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file not found: $required"
    }
}

$learningSource = [IO.File]::ReadAllText($learningPage, [Text.Encoding]::UTF8)
if (-not $learningSource.Contains($learningPageMarker)) {
    throw "Learning page marker is missing: $learningPageMarker"
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
$publicHomeworkArchive = Join-Path $tempRoot 'public-homework.zip'
New-Item -ItemType Directory -Path $tempRoot, $packageRoot | Out-Null

$remoteIndex = "/tmp/visual-lab-$stamp-index.html"
$remoteLearningPage = "/tmp/visual-lab-$stamp-learning.html"
$remoteArchive = "/tmp/visual-lab-$stamp-trajectories.zip"
$remoteHomeworkPage = "/tmp/visual-lab-$stamp-homework.html"
$remoteHomeworkArchive = "/tmp/visual-lab-$stamp-homework.zip"
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

    foreach ($name in @('run_manifest.json')) {
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

    # Normalize archive timestamps so identical data produces an identical ZIP.
    $fixedPackageTime = [datetime]::SpecifyKind(
        [datetime]'2026-01-01T00:00:00',
        [DateTimeKind]::Utc
    )
    foreach ($entry in @(Get-ChildItem -LiteralPath $packageRoot -Recurse -Force)) {
        $entry.LastWriteTimeUtc = $fixedPackageTime
    }
    (Get-Item -LiteralPath $packageRoot).LastWriteTimeUtc = $fixedPackageTime

    Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $newArchive -CompressionLevel Optimal
    Expand-Archive -LiteralPath $newArchive -DestinationPath $verifyRoot

    $packageFiles = Get-ChildItem -LiteralPath $verifyRoot -Recurse -File
    if ($packageFiles.Count -ne 25) {
        throw "Trajectory package must contain 25 files; found $($packageFiles.Count)."
    }
    $readme = [IO.File]::ReadAllText((Join-Path $verifyRoot 'README.md'), $utf8)
    if (-not $readme.Contains($packageReadmeMarker)) {
        throw "The packaged README is missing its stable marker: $packageReadmeMarker"
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
        "if test -f $remoteBackup/retired-analysis.existed; then " +
        "cp -p $remoteBackup/pressure_analysis.html /var/www/visual-lab/pressure_analysis.html; " +
        "else rm -f /var/www/visual-lab/pressure_analysis.html; fi && " +
        "if test -f $remoteBackup/retired-csv.existed; then " +
        "cp -p $remoteBackup/diffusion_vs_pressure.csv /var/www/visual-lab/results/diffusion_pressure/diffusion_vs_pressure.csv; " +
        "else rm -f /var/www/visual-lab/results/diffusion_pressure/diffusion_vs_pressure.csv; fi && " +
        "if test -f $remoteBackup/learning-page.existed; then " +
        "cp -p $remoteBackup/learning.html /var/www/visual-lab/learning.html; " +
        "else rm -f /var/www/visual-lab/learning.html; fi && " +
        "if test -f $remoteBackup/homework-page.existed; then " +
        "cp -p $remoteBackup/homework.html /var/www/visual-lab/homework.html; " +
        "else rm -f /var/www/visual-lab/homework.html; fi && " +
        "if test -f $remoteBackup/homework-archive.existed; then " +
        "cp -p $remoteBackup/homework_20261027.zip /var/www/visual-lab/downloads/homework_20261027.zip; " +
        "else rm -f /var/www/visual-lab/downloads/homework_20261027.zip; fi"
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @($serverTarget, $restore)) `
        -FailureMessage 'Automatic remote rollback failed'
}

try {
    Write-Host '[1/7] Building visualization and homework pages...'
    Invoke-NativeChecked `
        -Program $python `
        -Arguments @($pageBuilder) `
        -FailureMessage 'Visualization build failed'
    Invoke-NativeChecked `
        -Program $python `
        -Arguments @($homeworkBuilder) `
        -FailureMessage 'Homework page and student-package build failed'
    if (-not (Test-Path -LiteralPath $page -PathType Leaf)) {
        throw "Visualization output missing: $page"
    }
    $pageMarkers = @{
        $page = $mainPageMarker
        $learningPage = $learningPageMarker
        $homeworkPage = $homeworkPageMarker
    }
    foreach ($entry in $pageMarkers.GetEnumerator()) {
        $pageSource = [IO.File]::ReadAllText($entry.Key, [Text.Encoding]::UTF8)
        if (-not $pageSource.Contains($entry.Value)) {
            throw "Page marker is missing from $($entry.Key): $($entry.Value)"
        }
    }

    # All student-facing download buttons must use the current assignment package.
    foreach ($studentPage in @($page, $learningPage, $homeworkPage)) {
        $studentSource = [IO.File]::ReadAllText($studentPage, [Text.Encoding]::UTF8)
        if (-not $studentSource.Contains('downloads/homework_20261027.zip') -or
            $studentSource.Contains('downloads/pressure_diffusion_trajectories.zip')) {
            throw "Student download link must target the six-choice assignment: $studentPage"
        }
    }

    Write-Host '[2/7] Homework package validated (73 files, six original LAMMPS inputs); rebuilding legacy trajectory package...'
    Build-TrajectoryPackage

    $localHashes = @{
        $remoteIndex = Get-Sha256 $page
        $remoteLearningPage = Get-Sha256 $learningPage
        $remoteArchive = Get-Sha256 $archive
        $remoteHomeworkPage = Get-Sha256 $homeworkPage
        $remoteHomeworkArchive = Get-Sha256 $homeworkArchive
    }

    Write-Host '[3/7] Checking SSH connectivity and remote targets...'
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @($serverTarget, "test ! -e $remoteBackup")) `
        -FailureMessage 'Remote backup path already exists or SSH failed'

    Write-Host '[4/7] Uploading site pages, homework and legacy ZIPs, and deployment script...'
    foreach ($item in @(
        @($page, $remoteIndex),
        @($learningPage, $remoteLearningPage),
        @($archive, $remoteArchive),
        @($homeworkPage, $remoteHomeworkPage),
        @($homeworkArchive, $remoteHomeworkArchive)
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
incoming_learning=$3
incoming_archive=$4
health_host=$5
incoming_homework=$6
incoming_homework_archive=$7
site=/var/www/visual-lab
backup="/root/visual-lab-backups/deploy-$stamp"
index="$site/index.html"
learning="$site/learning.html"
archive="$site/downloads/pressure_diffusion_trajectories.zip"
homework="$site/homework.html"
homework_archive="$site/downloads/homework_20261027.zip"
retired_analysis="$site/pressure_analysis.html"
retired_csv="$site/results/diffusion_pressure/diffusion_vs_pressure.csv"
index_next="$index.next"
learning_next="$learning.next"
archive_next="$archive.next"
homework_next="$homework.next"
homework_archive_next="$homework_archive.next"
deployed=0

restore_and_cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    if [ "$status" -ne 0 ] && [ "$deployed" -eq 1 ]; then
        cp -p "$backup/index.html" "$index"
        cp -p "$backup/pressure_diffusion_trajectories.zip" "$archive"
        if [ -f "$backup/retired-analysis.existed" ]; then
            cp -p "$backup/pressure_analysis.html" "$retired_analysis"
        else
            rm -f "$retired_analysis"
        fi
        if [ -f "$backup/retired-csv.existed" ]; then
            cp -p "$backup/diffusion_vs_pressure.csv" "$retired_csv"
        else
            rm -f "$retired_csv"
        fi
        if [ -f "$backup/learning-page.existed" ]; then
            cp -p "$backup/learning.html" "$learning"
        else
            rm -f "$learning"
        fi
        if [ -f "$backup/homework-page.existed" ]; then
            cp -p "$backup/homework.html" "$homework"
        else
            rm -f "$homework"
        fi
        if [ -f "$backup/homework-archive.existed" ]; then
            cp -p "$backup/homework_20261027.zip" "$homework_archive"
        else
            rm -f "$homework_archive"
        fi
    fi
    rm -f "$index_next" "$learning_next" "$archive_next" "$homework_next" "$homework_archive_next"
    exit "$status"
}
trap restore_and_cleanup EXIT HUP INT TERM

test -f "$incoming_index"
test -f "$incoming_learning"
test -f "$incoming_archive"
test -f "$incoming_homework"
test -f "$incoming_homework_archive"
test -f "$index"
test -f "$archive"
test ! -e "$backup"

install -d -m 700 "$backup"
cp -p "$index" "$backup/index.html"
cp -p "$archive" "$backup/pressure_diffusion_trajectories.zip"
if [ -f "$retired_analysis" ]; then
    cp -p "$retired_analysis" "$backup/pressure_analysis.html"
    touch "$backup/retired-analysis.existed"
fi
if [ -f "$retired_csv" ]; then
    cp -p "$retired_csv" "$backup/diffusion_vs_pressure.csv"
    touch "$backup/retired-csv.existed"
fi
if [ -f "$learning" ]; then
    cp -p "$learning" "$backup/learning.html"
    touch "$backup/learning-page.existed"
fi
if [ -f "$homework" ]; then
    cp -p "$homework" "$backup/homework.html"
    touch "$backup/homework-page.existed"
fi
if [ -f "$homework_archive" ]; then
    cp -p "$homework_archive" "$backup/homework_20261027.zip"
    touch "$backup/homework-archive.existed"
fi

install -m 644 "$incoming_index" "$index_next"
install -m 644 "$incoming_learning" "$learning_next"
install -m 644 "$incoming_archive" "$archive_next"
install -m 644 "$incoming_homework" "$homework_next"
install -m 644 "$incoming_homework_archive" "$homework_archive_next"

deployed=1
mv "$index_next" "$index"
mv "$learning_next" "$learning"
mv "$archive_next" "$archive"
mv "$homework_next" "$homework"
mv "$homework_archive_next" "$homework_archive"
rm -f "$retired_analysis" "$retired_csv"

systemctl is-active --quiet nginx
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/'
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/learning.html'
curl --fail --silent --show-error --output /dev/null --head --header "Host: $health_host" 'http://127.0.0.1/downloads/pressure_diffusion_trajectories.zip'
curl --fail --silent --show-error --output /dev/null --header "Host: $health_host" 'http://127.0.0.1/homework.html'
curl --fail --silent --show-error --output /dev/null --head --header "Host: $health_host" 'http://127.0.0.1/downloads/homework_20261027.zip'
test ! -e "$retired_analysis"
test ! -e "$retired_csv"
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
        $remoteLearningPage,
        $remoteArchive,
        $remoteHomeworkPage,
        $remoteHomeworkArchive
    )
    foreach ($path in $localHashes.Keys) {
        if (-not $uploadedHashes.ContainsKey($path) -or $uploadedHashes[$path] -ne $localHashes[$path]) {
            throw "Uploaded SHA-256 mismatch: $path"
        }
    }

    Write-Host '[5/7] Creating backups, switching files, and retiring analysis results...'
    Invoke-NativeChecked `
        -Program 'ssh' `
        -Arguments ($sshArgs + @(
            $serverTarget,
            "sh $remoteScript $stamp $remoteIndex $remoteLearningPage $remoteArchive $ServerAddress $remoteHomeworkPage $remoteHomeworkArchive"
        )) `
        -FailureMessage 'Remote deployment failed; server-side rollback was attempted'
    $deploymentApplied = $true

    $livePaths = @(
        '/var/www/visual-lab/index.html',
        '/var/www/visual-lab/learning.html',
        '/var/www/visual-lab/downloads/pressure_diffusion_trajectories.zip',
        '/var/www/visual-lab/homework.html',
        '/var/www/visual-lab/downloads/homework_20261027.zip'
    )
    $liveHashes = Get-RemoteHashes $livePaths
    foreach ($comparison in @(
        @($livePaths[0], $localHashes[$remoteIndex]),
        @($livePaths[1], $localHashes[$remoteLearningPage]),
        @($livePaths[2], $localHashes[$remoteArchive]),
        @($livePaths[3], $localHashes[$remoteHomeworkPage]),
        @($livePaths[4], $localHashes[$remoteHomeworkArchive])
    )) {
        if (-not $liveHashes.ContainsKey($comparison[0]) -or $liveHashes[$comparison[0]] -ne $comparison[1]) {
            throw "Live SHA-256 mismatch: $($comparison[0])"
        }
    }

    Write-Host '[6/7] Verifying public pages and student download...'
    try {
        $pageResponse = Invoke-WebRequest -UseBasicParsing -Uri "$publicBase/" -TimeoutSec 45
        if ([int]$pageResponse.StatusCode -ne 200 -or -not $pageResponse.Content.Contains($mainPageMarker) -or -not $pageResponse.Content.Contains('href="homework.html"')) {
            throw 'Public page did not return the expected visualization.'
        }
        $learningResponse = Invoke-WebRequest -UseBasicParsing -Uri "$publicBase/learning.html" -TimeoutSec 45
        if (
            [int]$learningResponse.StatusCode -ne 200 -or
            -not $learningResponse.Content.Contains($learningPageMarker) -or
            -not $learningResponse.Content.Contains('href="homework.html"')
        ) {
            throw 'Public learning page did not return the expected content.'
        }

        Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "$publicBase/downloads/pressure_diffusion_trajectories.zip" `
            -OutFile $publicArchive `
            -TimeoutSec 180
        if ((Get-Sha256 $publicArchive) -ne (Get-Sha256 $archive)) {
            throw 'Public trajectory ZIP SHA-256 mismatch.'
        }
        $homeworkResponse = Invoke-WebRequest -UseBasicParsing -Uri "$publicBase/homework.html" -TimeoutSec 45
        if ([int]$homeworkResponse.StatusCode -ne 200 -or -not $homeworkResponse.Content.Contains($homeworkPageMarker)) {
            throw 'Public homework page did not return the expected content.'
        }
        foreach ($response in @($pageResponse, $learningResponse, $homeworkResponse)) {
            if (-not $response.Content.Contains('downloads/homework_20261027.zip') -or
                $response.Content.Contains('downloads/pressure_diffusion_trajectories.zip')) {
                throw 'Public student download link does not target the six-choice assignment.'
            }
        }
        Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "$publicBase/downloads/homework_20261027.zip" `
            -OutFile $publicHomeworkArchive `
            -TimeoutSec 90
        if ((Get-Sha256 $publicHomeworkArchive) -ne (Get-Sha256 $homeworkArchive)) {
            throw 'Public homework ZIP SHA-256 mismatch.'
        }
    }
    catch {
        Restore-RemoteBackup
        $deploymentApplied = $false
        throw
    }

    Write-Host '[7/7] Deployment complete.'
    Write-Host "Page: $publicBase/"
    Write-Host "Learning: $publicBase/learning.html"
    Write-Host "Homework: $publicBase/homework.html"
    Write-Host "ZIP SHA-256: $(Get-Sha256 $archive)"
    Write-Host "Student download: $publicBase/downloads/homework_20261027.zip"
    Write-Host "Homework ZIP SHA-256: $(Get-Sha256 $homeworkArchive)"
    Write-Host "Remote backup: $remoteBackup"
}
catch {
    # This also covers failures in live-hash verification after the remote switch.
    if ($deploymentApplied) {
        Restore-RemoteBackup
        $deploymentApplied = $false
    }
    throw
}
finally {
    $cleanupCommand = "rm -f -- $remoteIndex $remoteLearningPage $remoteArchive $remoteHomeworkPage $remoteHomeworkArchive $remoteScript"
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
