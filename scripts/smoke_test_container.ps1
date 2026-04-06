param(
    [string]$Image = "japim-paddleocr:3.4.0-gpu",
    [string]$ContainerName = "japim-smoke",
    [int]$HostPort = 18080,
    [Parameter(Mandatory = $true)]
    [string]$InputPdf,
    [string]$OutputDir = "var\smoke",
    [string]$ConfigPath = "",
    [switch]$UseGpu = $true
)

$ErrorActionPreference = "Stop"

function Wait-Health {
    param(
        [string]$BaseUrl,
        [int]$MaxAttempts = 60
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 5
            if ($response.status -eq "ok") {
                return
            }
        }
        catch {
        }
        Start-Sleep -Seconds 2
    }

    throw "API health check timed out"
}

function Wait-Job {
    param(
        [string]$BaseUrl,
        [string]$JobId,
        [int]$MaxAttempts = 120
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $status = Invoke-RestMethod -Uri "$BaseUrl/api/v1/jobs/$JobId" -Method Get -TimeoutSec 10
        if ($status.status -in @("success", "fail")) {
            return $status
        }
        Start-Sleep -Seconds 2
    }

    throw "Job polling timed out"
}

$resolvedPdf = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InputPdf)
$baseUrl = "http://localhost:$HostPort"
$resolvedOutputDir = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDir))
New-Item -ItemType Directory -Force -Path $resolvedOutputDir | Out-Null

$uploadJsonPath = Join-Path $resolvedOutputDir "upload-response.json"
$statusJsonPath = Join-Path $resolvedOutputDir "job-status.json"
$maskedPdfPath = Join-Path $resolvedOutputDir "masked.pdf"
$csvPath = Join-Path $resolvedOutputDir "detections.csv"
$jsonlPath = Join-Path $resolvedOutputDir "detections.jsonl"
$pdfHeadersPath = Join-Path $resolvedOutputDir "masked.headers.txt"

docker rm -f $ContainerName 2>$null | Out-Null

$dockerArgs = @("run", "-d", "--rm", "--name", $ContainerName, "-p", "${HostPort}:8000")
if ($UseGpu) {
    $dockerArgs += @("--gpus", "all")
}
if ($ConfigPath) {
    $dockerArgs += @("-e", "JAPIM_CONFIG=$ConfigPath")
}
elseif (-not $UseGpu) {
    $dockerArgs += @("-e", "JAPIM_CONFIG=/app/configs/default.yaml")
}
$dockerArgs += $Image

$containerId = (& docker @dockerArgs).Trim()

try {
    Wait-Health -BaseUrl $baseUrl

    & curl.exe -sS -X POST -F "file=@$resolvedPdf;type=application/pdf" "$baseUrl/api/v1/jobs" -o $uploadJsonPath
    $uploadResponse = Get-Content -LiteralPath $uploadJsonPath -Raw | ConvertFrom-Json
    $jobStatus = Wait-Job -BaseUrl $baseUrl -JobId $uploadResponse.job_id
    $jobStatus | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statusJsonPath -Encoding utf8

    if ($jobStatus.status -ne "success") {
        throw "Job failed: $($jobStatus.message)"
    }

    & curl.exe -sS -D $pdfHeadersPath -L "$baseUrl$($jobStatus.masked_pdf_url)" -o $maskedPdfPath
    & curl.exe -sS -L "$baseUrl$($jobStatus.detections_csv_url)" -o $csvPath
    & curl.exe -sS -L "$baseUrl$($jobStatus.detections_jsonl_url)" -o $jsonlPath

    Write-Output "container_id=$containerId"
    Write-Output "job_id=$($uploadResponse.job_id)"
    Write-Output "status=$($jobStatus.status)"
    Write-Output "masked_pdf=$maskedPdfPath"
    Write-Output "detections_csv=$csvPath"
    Write-Output "detections_jsonl=$jsonlPath"
    Write-Output "masked_headers=$pdfHeadersPath"
}
finally {
    try {
        docker logs $ContainerName --tail 120 | Out-Host
    }
    catch {
    }
    docker rm -f $ContainerName 2>$null | Out-Null
}
