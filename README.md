# JAPIM

JAPIM is a PaddleOCR based PDF PII masking service for scanned or image-heavy documents.

## Features

- PDF to PNG rendering
- OCR preprocessing
- PaddleOCR based text extraction
- Rule based PII detection and bbox masking
- Masked PDF reassembly
- JSON and CSV audit output without raw PII persistence
- REST API for upload, process, status, and download
- Browser test page for manual upload and result verification

## Quick start

```powershell
pip install -e .[dev,ocr]
uvicorn japim.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` and upload a PDF.

## CLI

```powershell
japim run --input C:\data\sample.pdf --config configs\default.yaml
```

## Docker build

Build the GPU-ready image and let Docker download the latest official PaddleOCR 3.4.0-compatible models into the image:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_offline_image.ps1 -Tag japim-paddleocr:0.1.0
```

The image uses a multi-stage build:

- a CPU fetch stage downloads the latest official PaddleOCR model bundle
- the final runtime stage installs `paddlepaddle-gpu==3.2.0` from the official CUDA 11.8 package index
- the fetched models are copied into `/app/models/paddleocr`, so the final image is self-contained for offline deployment

The container starts with `/app/configs/docker-gpu.yaml` by default, so it will use GPU OCR on a CUDA-enabled host. If you want to force CPU mode for troubleshooting, override the config:

```powershell
docker run --rm -p 8000:8000 -e JAPIM_CONFIG=/app/configs/default.yaml japim-paddleocr:0.1.0
```

For normal GPU deployment with NVIDIA Container Toolkit:

```powershell
docker run --rm --gpus all -p 8000:8000 japim-paddleocr:0.1.0
```

If the installed official PaddlePaddle GPU wheel does not support the host GPU architecture yet, the OCR engine automatically falls back to CPU instead of failing the whole job. This keeps the same GPU-ready image deployable on mixed server fleets.

If you also want a local copy of the official models in the repo for inspection, you can fetch them separately:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\fetch_paddle_models.ps1
```

Or let the build script populate the local `models\paddleocr` folder before the image build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_offline_image.ps1 -Tag japim-paddleocr:0.1.0 -AutoFetchModels
```

Split the resulting image archive for GitHub Releases:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_release_parts.ps1 -Image japim-paddleocr:0.1.0
```

The export script uses a chunk size below GitHub's 2 GB per-asset limit so each release part can be uploaded without manual resizing.

Merge split release parts and load the image on an offline server:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import_release_parts.ps1 `
  -ArchiveBase C:\deploy\japim-paddleocr_3.4.0-gpu.tar.gz
```

Generate a release manifest JSON:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\write_release_manifest.ps1 `
  -Image japim-paddleocr:3.4.0-gpu
```

Detailed Korean deployment guide:

- [docs/offline-release-guide.ko.md](C:\Users\USER\projects\japim\docs\offline-release-guide.ko.md)
- [docs/redhat9-gpu-guide.ko.md](C:\Users\USER\projects\japim\docs\redhat9-gpu-guide.ko.md)
- [docs/ubuntu-gpu-guide.ko.md](C:\Users\USER\projects\japim\docs\ubuntu-gpu-guide.ko.md)

Ready-to-run Linux helper scripts:

- [scripts/run_ubuntu_gpu.sh](C:\Users\USER\projects\japim\scripts\run_ubuntu_gpu.sh)
- [scripts/run_rhel9_gpu.sh](C:\Users\USER\projects\japim\scripts\run_rhel9_gpu.sh)
- [scripts/import_release_parts.sh](C:\Users\USER\projects\japim\scripts\import_release_parts.sh)

Systemd service templates:

- [deploy/systemd/japim-docker.service](C:\Users\USER\projects\japim\deploy\systemd\japim-docker.service)
- [deploy/systemd/japim-podman.service](C:\Users\USER\projects\japim\deploy\systemd\japim-podman.service)

## Mock E2E

For API and upload/download smoke tests without the Paddle model, generate a deterministic sample:

```powershell
python scripts\generate_sample_pdf.py
japim serve --config configs\mock-e2e.yaml
```

For a full container smoke test with upload and download verification:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke_test_container.ps1 `
  -Image japim-paddleocr:0.1.0 `
  -InputPdf samples\generated\sample-e2e.pdf `
  -OutputDir var\smoke
```

## Korean support

- The default OCR language is `korean`.
- The REST API preserves Korean filenames on upload and download.
- `scripts\generate_sample_pdf.py --korean` can generate a Korean sample PDF when a Korean-capable font such as `malgun.ttf` or `NanumGothic.ttf` is available.
