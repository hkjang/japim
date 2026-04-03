# PaddleOCR models

Place offline model assets here before building the Docker image.

Expected layout:

```text
models/
  paddleocr/
    det/
    rec/
    cls/
```

You can also auto-populate this folder with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\fetch_paddle_models.ps1
```
