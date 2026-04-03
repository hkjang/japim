param(
    [Parameter(Mandatory = $true)]
    [string]$Image,
    [string]$OutputDir = "var\release-assets",
    [int64]$ChunkSizeBytes = 2147483648
)

$ErrorActionPreference = "Stop"

function Compress-Gzip {
    param(
        [string]$SourcePath,
        [string]$DestinationPath
    )

    $buffer = New-Object byte[] (4MB)
    $inputStream = [System.IO.File]::OpenRead($SourcePath)
    try {
        $outputStream = [System.IO.File]::Create($DestinationPath)
        try {
            $gzipStream = New-Object System.IO.Compression.GZipStream($outputStream, [System.IO.Compression.CompressionMode]::Compress)
            try {
                while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $gzipStream.Write($buffer, 0, $read)
                }
            }
            finally {
                $gzipStream.Dispose()
            }
        }
        finally {
            $outputStream.Dispose()
        }
    }
    finally {
        $inputStream.Dispose()
    }
}

function Split-File {
    param(
        [string]$SourcePath,
        [string]$TargetPrefix,
        [int64]$PartSize
    )

    $buffer = New-Object byte[] (4MB)
    $index = 1
    $source = [System.IO.File]::OpenRead($SourcePath)
    try {
        while ($source.Position -lt $source.Length) {
            $partPath = "{0}.part{1:d3}" -f $TargetPrefix, $index
            $target = [System.IO.File]::Create($partPath)
            try {
                $remaining = $PartSize
                while ($remaining -gt 0 -and $source.Position -lt $source.Length) {
                    if ($remaining -gt $buffer.Length) {
                        $toRead = $buffer.Length
                    }
                    else {
                        $toRead = [int]$remaining
                    }
                    $read = $source.Read($buffer, 0, $toRead)
                    if ($read -le 0) {
                        break
                    }
                    $target.Write($buffer, 0, $read)
                    $remaining -= $read
                }
            }
            finally {
                $target.Dispose()
            }
            $index += 1
        }
    }
    finally {
        $source.Dispose()
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$safeName = ($Image -replace "[^a-zA-Z0-9_.-]", "_")
$tarPath = Join-Path $OutputDir "$safeName.tar"
$gzipPath = "$tarPath.gz"
$prefix = Join-Path $OutputDir "$safeName.tar.gz"

docker image save -o $tarPath $Image
Compress-Gzip -SourcePath $tarPath -DestinationPath $gzipPath
Remove-Item -LiteralPath $tarPath -Force

Split-File -SourcePath $gzipPath -TargetPrefix $prefix -PartSize $ChunkSizeBytes

$hash = Get-FileHash -Algorithm SHA256 $gzipPath
Set-Content -Path "$gzipPath.sha256" -Value $hash.Hash -Encoding ascii

Write-Output "archive=$gzipPath"
Write-Output "sha256=$($hash.Hash)"
