param([string]$Version = '0.2.0')

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$packagingRoot = $PSScriptRoot
$releaseRoot = Join-Path $packagingRoot 'release'
$distRoot = Join-Path $packagingRoot ("dist-v$Version")
$buildRoot = Join-Path $packagingRoot ("build-v$Version")
$pyInstaller = Join-Path $projectRoot '.conda\envs\yuhen\Scripts\pyinstaller.exe'
$specPath = Join-Path $packagingRoot 'yuhen.spec'
$appName = -join @([char]0x7FFC, [char]0x00B7, [char]0x65F6, [char]0x5149, [char]0x8BB0)
$blankLabel = -join @([char]0x7A7A, [char]0x767D, [char]0x7248)
$blankName = "$appName-Windows-v$Version-$blankLabel"
$blankDir = Join-Path $releaseRoot $blankName
$blankZip = Join-Path $releaseRoot "$blankName.zip"

function Remove-SafeGeneratedTarget {
    param([string]$Target)
    $allowedRoot = [System.IO.Path]::GetFullPath($packagingRoot).TrimEnd('\') + '\'
    $resolved = [System.IO.Path]::GetFullPath($Target)
    if (-not $resolved.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a target outside the packaging directory: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $pyInstaller)) {
    throw "PyInstaller was not found: $pyInstaller"
}

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
foreach ($target in @($distRoot, $buildRoot, $blankDir, $blankZip)) {
    Remove-SafeGeneratedTarget -Target $target
}

Write-Host "[1/4] Building Windows application v$Version" -ForegroundColor Cyan
& $pyInstaller --noconfirm --clean --distpath $distRoot --workpath $buildRoot $specPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$bundleSource = Join-Path $distRoot $appName
if (-not (Test-Path -LiteralPath (Join-Path $bundleSource "$appName.exe"))) {
    throw 'The application executable is missing from the build output.'
}

Write-Host '[2/4] Creating an isolated blank release directory' -ForegroundColor Cyan
Copy-Item -LiteralPath $bundleSource -Destination $blankDir -Recurse
$blankData = Join-Path $blankDir 'data'
New-Item -ItemType Directory -Force -Path $blankData | Out-Null
foreach ($directoryName in @('photos', 'thumbnails', 'audio', '.tmp')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $blankData $directoryName) | Out-Null
}

Write-Host '[3/4] Adding documentation and creating the blank archive' -ForegroundColor Cyan
Copy-Item -LiteralPath (Join-Path $packagingRoot 'README-blank-zh-CN.txt') -Destination (Join-Path $blankDir 'README-zh-CN.txt')
$versionText = @(
    "$appName Windows v$Version",
    "Build time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Edition: $blankLabel",
    'Launch: double-click the application executable',
    'Default URL: http://127.0.0.1:8000'
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText((Join-Path $blankDir 'VERSION.txt'), $versionText, [System.Text.UTF8Encoding]::new($false))
Compress-Archive -LiteralPath $blankDir -DestinationPath $blankZip -CompressionLevel Optimal

Write-Host '[4/4] Writing SHA-256 checksum' -ForegroundColor Cyan
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $blankZip
$hashPath = Join-Path $releaseRoot "SHA256SUMS-v$Version.txt"
$hashLine = "$($hash.Hash)  $([System.IO.Path]::GetFileName($blankZip))"
[System.IO.File]::WriteAllText($hashPath, $hashLine + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host 'Blank release build complete:' -ForegroundColor Green
Write-Host $blankZip
Write-Host $hashPath
