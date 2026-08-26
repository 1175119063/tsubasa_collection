param(
    [string]$Version = '0.3.0',
    [string]$SourceDirectory = ''
)

$ErrorActionPreference = 'Stop'
$packagingRoot = $PSScriptRoot
$releaseRoot = Join-Path $packagingRoot 'release'
$appName = -join @([char]0x7FFC, [char]0x00B7, [char]0x65F6, [char]0x5149, [char]0x8BB0)
$blankLabel = -join @([char]0x7A7A, [char]0x767D, [char]0x7248)
if (-not $SourceDirectory) {
    $SourceDirectory = Join-Path $releaseRoot "$appName-Windows-v$Version-$blankLabel"
}
$source = [System.IO.Path]::GetFullPath($SourceDirectory)
$allowedRoot = [System.IO.Path]::GetFullPath($releaseRoot).TrimEnd('\') + '\'
if (-not $source.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Installer source must stay inside the release directory: $source"
}
if (-not (Test-Path -LiteralPath (Join-Path $source "$appName.exe"))) {
    throw "Release application was not found: $source"
}

$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $iscc) {
    throw 'Inno Setup 6 is not installed. No installer was built.'
}

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
& $iscc "/DMyAppVersion=$Version" "/DMySourceDir=$source" "/O$releaseRoot" (Join-Path $packagingRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

$installer = Join-Path $releaseRoot "$appName-Windows-v$Version-Setup.exe"
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $installer
$manifest = [ordered]@{
    version = $Version
    installer_url = "https://example.invalid/releases/$([System.IO.Path]::GetFileName($installer))"
    sha256 = $hash.Hash.ToLowerInvariant()
    notes = "Replace installer_url before publishing this manifest."
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $releaseRoot 'update-manifest.json') -Encoding utf8
Write-Host 'Installer and draft update manifest created. Review installer_url before publishing.' -ForegroundColor Green
