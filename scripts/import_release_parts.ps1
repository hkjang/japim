param(
    [Parameter(Mandatory = $true)]
    [string]$ArchiveBase,
    [string]$WorkingDir = "var\import",
    [string]$Retag,
    [switch]$SkipHashCheck
)

$ErrorActionPreference = "Stop"

function Join-Parts {
    param(
        [string[]]$PartPaths,
        [string]$DestinationPath
    )

    $buffer = New-Object byte[] (4MB)
    $output = [System.IO.File]::Create($DestinationPath)
    try {
        foreach ($part in $PartPaths) {
            $input = [System.IO.File]::OpenRead($part)
            try {
                while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $output.Write($buffer, 0, $read)
                }
            }
            finally {
                $input.Dispose()
            }
        }
    }
    finally {
        $output.Dispose()
    }
}

function Expand-Gzip {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    $buffer = New-Object byte[] (4MB)
    $input = [System.IO.File]::OpenRead($SourcePath)
    try {
        $gzip = New-Object System.IO.Compression.GZipStream($input, [System.IO.Compression.CompressionMode]::Decompress)
        try {
            $output = [System.IO.File]::Create($DestinationPath)
            try {
                while (($read = $gzip.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $output.Write($buffer, 0, $read)
                }
            }
            finally {
                $output.Dispose()
            }
        }
        finally {
            $gzip.Dispose()
        }
    }
    finally {
        $input.Dispose()
    }
}

$resolvedArchiveBase = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ArchiveBase)
$resolvedWorkingDir = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $WorkingDir))
New-Item -ItemType Directory -Force -Path $resolvedWorkingDir | Out-Null

$partFiles = Get-ChildItem -LiteralPath "$resolvedArchiveBase.part*" -ErrorAction SilentlyContinue | Sort-Object Name
$gzipPath = Join-Path $resolvedWorkingDir ([System.IO.Path]::GetFileName($resolvedArchiveBase))
if ($gzipPath.EndsWith(".tar.gz", [System.StringComparison]::OrdinalIgnoreCase)) {
    $tarPath = $gzipPath.Substring(0, $gzipPath.Length - 3)
}
else {
    $tarPath = [System.IO.Path]::ChangeExtension($gzipPath, ".tar")
}
$shaPath = "$resolvedArchiveBase.sha256"

if ($partFiles.Count -gt 0) {
    Join-Parts -PartPaths $partFiles.FullName -DestinationPath $gzipPath
}
elseif (Test-Path -LiteralPath $resolvedArchiveBase) {
    Copy-Item -LiteralPath $resolvedArchiveBase -Destination $gzipPath -Force
}
else {
    throw "Archive not found: $resolvedArchiveBase or $resolvedArchiveBase.part*"
}

if (-not $SkipHashCheck) {
    if (-not (Test-Path -LiteralPath $shaPath)) {
        throw "SHA256 file not found: $shaPath"
    }

    $expected = (Get-Content -LiteralPath $shaPath -Raw).Trim().ToUpperInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 $gzipPath).Hash.ToUpperInvariant()
    if ($expected -ne $actual) {
        throw "SHA256 mismatch. expected=$expected actual=$actual"
    }
}

Expand-Gzip -SourcePath $gzipPath -DestinationPath $tarPath
$loadOutput = docker load -i $tarPath

if ($Retag) {
    $loadedLine = ($loadOutput | Select-String -Pattern "Loaded image:").Line | Select-Object -Last 1
    if (-not $loadedLine) {
        throw "Could not determine loaded image tag from docker load output"
    }

    $sourceTag = $loadedLine.Substring($loadedLine.IndexOf(":") + 1).Trim()
    docker tag $sourceTag $Retag | Out-Null
}

Write-Output "gzip=$gzipPath"
Write-Output "tar=$tarPath"
Write-Output "docker_load=$($loadOutput -join [Environment]::NewLine)"
if ($Retag) {
    Write-Output "retag=$Retag"
}
