# JAPIM 오프라인 GPU 배포 가이드

이 문서는 `PaddleOCR 3.4.0` 기반 `JAPIM` 이미지를 GitHub Release로 배포하고, 외부 인터넷이 없는 GPU 서버에 반입해 실행하는 절차를 정리합니다.

## 1. 릴리즈 업로드 파일

현재 생성된 릴리즈 산출물 기준:

- 이미지 태그: `japim-paddleocr:3.4.0-gpu`
- 압축본: `japim-paddleocr_3.4.0-gpu.tar.gz`
- 분할 파일:
  - `japim-paddleocr_3.4.0-gpu.tar.gz.part001`
  - `japim-paddleocr_3.4.0-gpu.tar.gz.part002`
  - `japim-paddleocr_3.4.0-gpu.tar.gz.part003`
  - `japim-paddleocr_3.4.0-gpu.tar.gz.part004`
- 해시 파일: `japim-paddleocr_3.4.0-gpu.tar.gz.sha256`
- SHA256: `5CA8373563745C771E6E67E87CB2DA90919E6408190B01679195368AD02BDA80`

권장 업로드 자산:

- `*.part001`
- `*.part002`
- `*.part003`
- `*.part004`
- `*.sha256`
- 선택: `*.release-manifest.json`

원본 `tar.gz` 전체 파일은 GitHub Release 제한 때문에 보통 업로드하지 않고, 분할 파트만 업로드합니다.

주의:

- GitHub Release 자산은 `2GB 이하`가 아니라 실제로는 `2GB 미만`이어야 안전합니다.
- 따라서 분할 크기는 `2,000,000,000` 바이트 수준으로 두는 것을 권장합니다.

## 2. 릴리즈 메타데이터 생성

릴리즈 설명에 넣을 메타데이터 JSON을 만들려면:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\write_release_manifest.ps1 `
  -Image japim-paddleocr:3.4.0-gpu
```

생성 위치 예시:

- `var\release-assets\japim-paddleocr_3.4.0-gpu.release-manifest.json`

## 3. GitHub Release 업로드 체크리스트

1. Release 제목은 `vX.Y.Z` 형식으로 고정합니다.
2. 본문에는 최소한 아래 내용을 적습니다.
3. 포함 PaddleOCR 버전: `3.4.0`
4. 포함 PaddlePaddle GPU 패키지: `3.2.0` / CUDA 12.6 인덱스
5. 이미지 태그: `japim-paddleocr:3.4.0-gpu`
6. SHA256 값
7. 오프라인 서버 반입 절차 문서 위치
8. GPU 런타임 오류 시 CPU 폴백이 가능하다는 점

권장 릴리즈 본문 예시:

```text
Image: japim-paddleocr:3.4.0-gpu
PaddleOCR: 3.4.0
PaddlePaddle GPU: 3.2.0 (CUDA 12.6 index)
SHA256: 5CA8373563745C771E6E67E87CB2DA90919E6408190B01679195368AD02BDA80

Assets:
- japim-paddleocr_3.4.0-gpu.tar.gz.part001
- japim-paddleocr_3.4.0-gpu.tar.gz.part002
- japim-paddleocr_3.4.0-gpu.tar.gz.part003
- japim-paddleocr_3.4.0-gpu.tar.gz.part004
- japim-paddleocr_3.4.0-gpu.tar.gz.sha256

Notes:
- Default container config is /app/configs/docker-gpu.yaml
- If GPU execution fails after runtime initialization, OCR falls back to CPU automatically
```

## 4. 오프라인 서버 반입

오프라인 서버로 아래 파일을 복사합니다.

- `japim-paddleocr_3.4.0-gpu.tar.gz.part001`
- `japim-paddleocr_3.4.0-gpu.tar.gz.part002`
- `japim-paddleocr_3.4.0-gpu.tar.gz.part003`
- `japim-paddleocr_3.4.0-gpu.tar.gz.part004`
- `japim-paddleocr_3.4.0-gpu.tar.gz.sha256`

Windows 서버면 PowerShell 스크립트를 그대로 사용할 수 있고, Linux 서버면 아래 수동 명령을 사용하면 됩니다.

## 5. Windows 서버에서 이미지 복원

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import_release_parts.ps1 `
  -ArchiveBase C:\deploy\japim-paddleocr_3.4.0-gpu.tar.gz
```

선택적으로 다른 태그를 붙이려면:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import_release_parts.ps1 `
  -ArchiveBase C:\deploy\japim-paddleocr_3.4.0-gpu.tar.gz `
  -Retag registry.local/japim-paddleocr:3.4.0-gpu
```

이 스크립트는 다음을 순서대로 수행합니다.

1. `.part001~004` 병합
2. SHA256 검증
3. `tar.gz` 압축 해제
4. `docker load`
5. 선택 시 `docker tag`

## 6. Linux 서버에서 이미지 복원

```bash
cat japim-paddleocr_3.4.0-gpu.tar.gz.part001 \
    japim-paddleocr_3.4.0-gpu.tar.gz.part002 \
    japim-paddleocr_3.4.0-gpu.tar.gz.part003 \
    japim-paddleocr_3.4.0-gpu.tar.gz.part004 \
  > japim-paddleocr_3.4.0-gpu.tar.gz

sha256sum japim-paddleocr_3.4.0-gpu.tar.gz
gunzip -c japim-paddleocr_3.4.0-gpu.tar.gz > japim-paddleocr_3.4.0-gpu.tar
docker load -i japim-paddleocr_3.4.0-gpu.tar
```

## 7. GPU 서버 실행

기본 실행:

```bash
docker run --rm --gpus all -p 8000:8000 japim-paddleocr:3.4.0-gpu
```

RHEL 9 GPU 서버에 대해서는 별도 가이드를 따르는 것을 권장합니다.

- [docs/redhat9-gpu-guide.ko.md](C:\Users\USER\projects\japim\docs\redhat9-gpu-guide.ko.md)
- [docs/ubuntu-gpu-guide.ko.md](C:\Users\USER\projects\japim\docs\ubuntu-gpu-guide.ko.md)

볼륨 마운트 예시:

```bash
docker run --rm --gpus all \
  -p 8000:8000 \
  -v /srv/japim/output:/app/output \
  -v /srv/japim/temp:/app/temp \
  japim-paddleocr:3.4.0-gpu
```

같은 GPU 서버에서 CPU 강제 실행:

```bash
docker run --rm -p 8000:8000 \
  -e JAPIM_CONFIG=/app/configs/default.yaml \
  japim-paddleocr:3.4.0-gpu
```

## 8. 기동 후 확인

헬스체크:

```bash
curl http://localhost:8000/health
```

정상 응답:

```json
{"status":"ok"}
```

브라우저 테스트 페이지:

- `http://localhost:8000/`

## 9. GPU 호환성 주의사항

이 이미지는 GPU 배포형이지만, 실제 OCR이 GPU로 동작하려면 대상 서버 GPU 아키텍처가 공식 PaddlePaddle GPU 휠과 호환되어야 합니다.

현재 구현된 동작은 다음과 같습니다.

- GPU 초기화 및 실행 성공: 그대로 GPU OCR 사용
- GPU 실행 중 런타임 오류 발생: 로그 경고 후 CPU 자동 폴백
- 다만 이 이미지는 GPU 배포형이라 NVIDIA 드라이버 라이브러리가 전혀 없는 순수 CPU 호스트용 이미지는 아님

## 10. 권장 운영 점검

배포 직후 아래를 반드시 확인합니다.

1. `/health` 응답
2. 브라우저 테스트 페이지 업로드 동작
3. PDF 업로드 후 결과 PDF 다운로드
4. `detections.csv` / `detections.jsonl` 생성 여부
5. 로그에 GPU 폴백 경고가 있는지 여부

## 11. 참고 스크립트

- 이미지 빌드: `scripts\build_offline_image.ps1`
- 릴리즈 분할: `scripts\export_release_parts.ps1`
- 릴리즈 복원: `scripts\import_release_parts.ps1`
- 릴리즈 메타데이터 생성: `scripts\write_release_manifest.ps1`
- 컨테이너 스모크 테스트: `scripts\smoke_test_container.ps1`
