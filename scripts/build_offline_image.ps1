param(
    [string]$Tag = "japim-paddleocr:latest",
    [string]$PaddlePackage = "paddlepaddle-gpu==3.2.0",
    [string]$PaddlePackageIndex = "https://www.paddlepaddle.org.cn/packages/stable/cu118/",
    [string]$PaddleFetchPackage = "paddlepaddle==3.2.0",
    [string]$PaddleFetchPackageIndex = "https://www.paddlepaddle.org.cn/packages/stable/cpu/",
    [switch]$AutoFetchModels
)

$ErrorActionPreference = "Stop"

if ($AutoFetchModels) {
    & "$PSScriptRoot\fetch_paddle_models.ps1"
}

docker build `
    --build-arg PADDLE_PACKAGE=$PaddlePackage `
    --build-arg PADDLE_PACKAGE_INDEX=$PaddlePackageIndex `
    --build-arg PADDLE_FETCH_PACKAGE=$PaddleFetchPackage `
    --build-arg PADDLE_FETCH_PACKAGE_INDEX=$PaddleFetchPackageIndex `
    -t $Tag `
    .
