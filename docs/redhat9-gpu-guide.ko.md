# RHEL 9 GPU 배포 가이드

이 문서는 `Red Hat Enterprise Linux 9` GPU 서버에서 `JAPIM` 이미지를 기동할 때 필요한 호스트 준비와 실행 방법을 정리합니다.

## 1. 핵심 판단

RHEL 9에서는 다음 조합을 권장합니다.

- 권장 컨테이너 엔진: `Podman`
- GPU 연동 방식: `NVIDIA Container Toolkit + CDI`
- 이미지: `japim-paddleocr:3.4.0-gpu`

이유:

- Red Hat 9의 기본 컨테이너 도구는 Podman 계열입니다.
- NVIDIA 공식 문서는 `RHEL 9.x`를 NVIDIA Container Toolkit 지원 플랫폼에 포함합니다.
- NVIDIA 공식 CDI 문서는 Podman에서 `--device nvidia.com/gpu=all` 방식 사용을 안내합니다.

## 2. 호스트 사전 점검

다음 명령으로 기본 상태를 먼저 확인합니다.

```bash
cat /etc/redhat-release
nvidia-smi
podman --version
```

정상 조건:

- OS: `Red Hat Enterprise Linux release 9.x`
- `nvidia-smi` 실행 성공
- `podman` 사용 가능

## 3. Podman 설치

RHEL 9 기본 컨테이너 도구 설치:

```bash
sudo dnf module install -y container-tools
```

## 4. NVIDIA Container Toolkit 설치

공식 저장소 등록:

```bash
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
```

설치:

```bash
sudo dnf install -y nvidia-container-toolkit
```

버전 확인:

```bash
nvidia-ctk --version
```

## 5. CDI 생성

Podman에서 GPU를 넘기려면 CDI 스펙을 생성합니다.

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
nvidia-ctk cdi list
```

정상이라면 `nvidia.com/gpu=all` 또는 개별 GPU 이름이 조회됩니다.

## 6. 릴리즈 파일 복원

오프라인 반입 후 Linux에서 바로 쓰는 스크립트:

```bash
chmod +x scripts/import_release_parts.sh
./scripts/import_release_parts.sh \
  --archive-base /data/release/japim-paddleocr_3.4.0-gpu.tar.gz \
  --engine podman
```

수동으로 하려면:

```bash
cat japim-paddleocr_3.4.0-gpu.tar.gz.part001 \
    japim-paddleocr_3.4.0-gpu.tar.gz.part002 \
    japim-paddleocr_3.4.0-gpu.tar.gz.part003 \
  > japim-paddleocr_3.4.0-gpu.tar.gz

sha256sum japim-paddleocr_3.4.0-gpu.tar.gz
gunzip -c japim-paddleocr_3.4.0-gpu.tar.gz > japim-paddleocr_3.4.0-gpu.tar
podman load -i japim-paddleocr_3.4.0-gpu.tar
```

## 7. Podman 실행

기본 실행:

```bash
podman run --rm \
  --device nvidia.com/gpu=all \
  -p 8000:8000 \
  japim-paddleocr:3.4.0-gpu
```

저장소에 포함된 실행 스크립트 사용:

```bash
chmod +x scripts/run_rhel9_gpu.sh
./scripts/run_rhel9_gpu.sh
```

출력 디렉터리와 임시 디렉터리 바인드 마운트:

```bash
sudo mkdir -p /srv/japim/output /srv/japim/temp

podman run --rm \
  --device nvidia.com/gpu=all \
  -p 8000:8000 \
  -v /srv/japim/output:/app/output:Z \
  -v /srv/japim/temp:/app/temp:Z \
  japim-paddleocr:3.4.0-gpu
```

`SELinux`가 활성화된 RHEL 9에서는 bind mount에 `:Z`를 붙이는 것을 권장합니다.

## 8. Docker를 써야 하는 경우

RHEL 9에서는 Podman이 더 자연스럽지만, Docker를 운영 중이라면 NVIDIA 공식 문서의 Docker 런타임 설정 절차를 따라 아래처럼 준비합니다.

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --gpus all -p 8000:8000 japim-paddleocr:3.4.0-gpu
```

## 9. 실행 후 확인

헬스체크:

```bash
curl http://localhost:8000/health
```

브라우저 테스트 페이지:

- `http://서버IP:8000/`

## 10. GPU 호환성 주의

현재 이미지 내부 GPU 패키지는:

- `paddlepaddle-gpu==3.2.0`
- 공식 `cu118` 인덱스 기준

Paddle 공식 Linux PIP 문서는 `3.2.0` GPU 설치 시 `CUDA 11.8`, `12.6`, `12.9` 계열 인덱스를 안내합니다. 다만 실제 GPU 아키텍처 지원 여부는 공식 휠 빌드 범위에 따라 달라질 수 있습니다.

현재 앱 동작:

- GPU 초기화 성공: GPU OCR 사용
- GPU 초기화 실패: 경고 로그 후 CPU 자동 폴백

즉 RHEL 9 서버에서도 서비스는 기동되지만, GPU 아키텍처가 공식 휠과 맞지 않으면 CPU로 내려갈 수 있습니다.

## 11. SELinux 문제 해결

증상:

- 출력 디렉터리 쓰기 실패
- temp 디렉터리 접근 실패
- Podman 바인드 마운트 권한 오류

우선 조치:

1. bind mount 경로에 `:Z` 추가
2. 필요 시 컨테이너용 디렉터리를 미리 생성
3. 그래도 막히면 `audit.log`와 `ausearch -m avc` 확인

임시 점검용으로만:

```bash
podman run --rm \
  --device nvidia.com/gpu=all \
  --security-opt label=disable \
  -p 8000:8000 \
  japim-paddleocr:3.4.0-gpu
```

이 옵션은 SELinux 분리를 낮추므로 운영 기본값으로는 권장하지 않습니다.

스크립트로 일시 점검:

```bash
DISABLE_SELINUX_LABEL=true ./scripts/run_rhel9_gpu.sh
```

## 12. 권장 운영 절차

1. `nvidia-smi`로 드라이버와 GPU 인식 확인
2. `nvidia-ctk cdi generate` 및 `nvidia-ctk cdi list` 확인
3. `podman load` 또는 `scripts/import_release_parts.sh`로 이미지 반입
4. `podman run --device nvidia.com/gpu=all ...` 실행
5. `/health` 확인
6. 웹 테스트 페이지에서 PDF 업로드/다운로드 확인

## 13. 참고 문서

- NVIDIA Container Toolkit install guide: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.17.8/install-guide.html>
- NVIDIA CDI support: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html>
- Red Hat RHEL 9 container docs: <https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/htmlsingle/building_running_and_managing_containers/>
- Paddle Linux pip install guide: <https://www.paddlepaddle.org.cn/documentation/docs/install/pip/linux-pip_en.html>

Ubuntu 서버에 대해서는 별도 가이드를 참고합니다.

- [docs/ubuntu-gpu-guide.ko.md](C:\Users\USER\projects\japim\docs\ubuntu-gpu-guide.ko.md)

## 14. systemd 자동기동

템플릿 파일:

- [deploy/systemd/japim-podman.service](C:\Users\USER\projects\japim\deploy\systemd\japim-podman.service)

적용 예시:

```bash
sudo cp deploy/systemd/japim-podman.service /etc/systemd/system/japim.service
sudo systemctl daemon-reload
sudo systemctl enable --now japim.service
sudo systemctl status japim.service
```
