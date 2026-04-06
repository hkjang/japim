param(
    [string]$OutputDir = "models\paddleocr",
    [string]$Lang = "korean",
    [string]$PaddlePackage = "paddlepaddle==3.2.0",
    [string]$PaddlePackageIndex = "https://www.paddlepaddle.org.cn/packages/stable/cpu/",
    [string]$TextDetectionModelName = "PP-OCRv5_mobile_det",
    [string]$TextRecognitionModelName = "",
    [string]$TextlineOrientationModelName = "PP-LCNet_x0_25_textline_ori"
)

$ErrorActionPreference = "Stop"

docker run --rm `
    -v "${PWD}:/workspace" `
    -w /workspace `
    python:3.11-slim `
    bash -lc "apt-get update && apt-get install -y libgomp1 libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 && pip install --upgrade pip setuptools wheel && pip install `"$PaddlePackage`" -i `"$PaddlePackageIndex`" && pip install -e .[ocr] && export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True && python scripts/fetch_paddle_models.py --output-dir `"$OutputDir`" --lang `"$Lang`" --text-detection-model-name `"$TextDetectionModelName`" --text-recognition-model-name `"$TextRecognitionModelName`" --textline-orientation-model-name `"$TextlineOrientationModelName`""
