param(
    [Parameter(Mandatory = $true)]
    [string]$Image,
    [string]$AssetDir = "var\release-assets"
)

$ErrorActionPreference = "Stop"

$resolvedAssetDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($AssetDir)
$safeName = ($Image -replace "[^a-zA-Z0-9_.-]", "_")
$archiveName = "$safeName.tar.gz"
$archivePath = Join-Path $resolvedAssetDir $archiveName
$shaPath = "$archivePath.sha256"
$partFiles = Get-ChildItem -Path (Join-Path $resolvedAssetDir "$archiveName.part*") -ErrorAction SilentlyContinue | Sort-Object Name

if (-not (Test-Path -LiteralPath $archivePath)) {
    throw "Archive not found: $archivePath"
}

$payload = [ordered]@{
    image = $Image
    archive = [System.IO.Path]::GetFileName($archivePath)
    archive_size = (Get-Item -LiteralPath $archivePath).Length
    sha256 = if (Test-Path -LiteralPath $shaPath) { (Get-Content -LiteralPath $shaPath -Raw).Trim() } else { $null }
    parts = @(
        $partFiles | ForEach-Object {
            [ordered]@{
                name = $_.Name
                size = $_.Length
            }
        }
    )
    generated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
}

$manifestPath = Join-Path $resolvedAssetDir "$safeName.release-manifest.json"
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output "manifest=$manifestPath"
