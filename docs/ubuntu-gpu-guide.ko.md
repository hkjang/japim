# Ubuntu GPU 배포 가이드

이 문서는 `Ubuntu` GPU 서버에서 `JAPIM` 이미지를 실행하는 절차를 정리합니다.

## 1. 권장 조합

Ubuntu에서는 다음 조합을 권장합니다.

- 컨테이너 엔진: `Docker Engine`
- GPU 연동: `NVIDIA Container Toolkit`
- 이미지: `japim-paddleocr:3.4.0-gpu`

## 2. 지원 대상

Docker 공식 Ubuntu 설치 문서는 현재 `Ubuntu 22.04 LTS`, `Ubuntu 24.04 LTS`, `Ubuntu 25.10`을 안내합니다.

실무 권장:

- `Ubuntu 22.04 LTS`
- `Ubuntu 24.04 LTS`

## 3. 사전 점검

```bash
cat /etc/os-release
nvidia-smi
docker --version
```

정상 조건:

- `nvidia-smi` 실행 성공
- Docker 사용 가능

## 4. Docker Engine 설치

Docker 공식 문서 기준으로 `apt` 저장소 방식 설치를 권장합니다.

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

## 5. NVIDIA Container Toolkit 설치

공식 NVIDIA 설치 가이드 기준:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
```

Docker 런타임 설정:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## 6. GPU 노출 확인

```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi
```

이 명령이 성공하면 컨테이너 안에서 GPU 접근이 되는 상태입니다.

## 7. 릴리즈 파일 복원

Linux 복원 스크립트:

```bash
chmod +x scripts/import_release_parts.sh
./scripts/import_release_parts.sh \
  --archive-base /data/release/japim-paddleocr_3.4.0-gpu.tar.gz \
  --engine docker
```

## 8. 서비스 실행

기본 실행:

```bash
docker run --rm --gpus all -p 8000:8000 japim-paddleocr:3.4.0-gpu
```

저장소에 포함된 실행 스크립트 사용:

```bash
chmod +x scripts/run_ubuntu_gpu.sh
./scripts/run_ubuntu_gpu.sh
```

고VRAM 서버에서 더 무거운 프로파일로 바꾸고 싶다면:

```bash
CONFIG_PATH=/app/configs/docker-gpu-highmem.yaml ./scripts/run_ubuntu_gpu.sh
```

볼륨 마운트 예시:

```bash
sudo mkdir -p /srv/japim/output /srv/japim/temp

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

같은 GPU 서버에서 CPU 강제 스크립트 실행:

```bash
FORCE_CPU=true ./scripts/run_ubuntu_gpu.sh
```

## 9. 기동 후 확인

헬스체크:

```bash
curl http://localhost:8000/health
```

브라우저 테스트 페이지:

- `http://서버IP:8000/`

## 10. GPU OOM / GPU 사용률 0% 점검

다음 명령을 같이 봅니다.

```bash
watch -n 1 nvidia-smi
docker logs -f japim
```

중요:

- `nvidia-smi`의 `GPU-Util`이 0%라고 해서 반드시 CPU만 쓰는 것은 아닙니다.
- OCR 추론은 짧은 burst 형태라 샘플링 타이밍에 따라 0%로 보일 수 있습니다.
- 대신 `Memory-Usage`와 컨테이너 로그를 같이 봐야 합니다.

현재 기본 GPU 프로파일은 OOM 완화를 위해 다음처럼 낮춰져 있습니다.

- 모바일 detection 모델 사용
- recognition batch size 1
- orientation batch size 1
- `FLAGS_allocator_strategy=auto_growth`
- `FLAGS_fraction_of_gpu_memory_to_use=0.1`
- 기본 `docker-gpu.yaml`은 DPI와 전처리 크기를 낮춘 안전 프로파일

로그에서 아래 문구가 보이면 GPU 대신 CPU로 내려간 것입니다.

- `GPU OCR backend initialization failed, falling back to CPU`

VRAM이 충분한 서버라면 더 무거운 설정으로 바꿀 수 있습니다.

```bash
docker run --rm --gpus all -p 8000:8000 \
  -e JAPIM_CONFIG=/app/configs/docker-gpu-highmem.yaml \
  japim-paddleocr:3.4.0-gpu
```

같은 설정은 실행 스크립트에서도 바로 줄 수 있습니다.

```bash
CONFIG_PATH=/app/configs/docker-gpu-highmem.yaml ./scripts/run_ubuntu_gpu.sh
```

## 11. Ubuntu 운영 주의사항

Docker 공식 문서는 Ubuntu에서 포트를 외부로 노출할 경우 `ufw` 규칙을 우회할 수 있다고 안내합니다.

운영 시 권장:

1. 보안그룹 또는 방화벽 정책을 별도로 확인
2. 필요한 포트만 노출
3. 가능하면 reverse proxy 뒤에 배치
4. `DOCKER-USER` 체인 기준 필터링 정책 검토

## 12. GPU 호환성

현재 이미지 내부 GPU 패키지:

- `paddlepaddle-gpu==3.2.0`
- 공식 `CUDA 11.8` 인덱스 기준

앱 동작:

- GPU 초기화 및 실행 성공: GPU OCR 사용
- GPU 실행 중 런타임 오류: CPU 자동 폴백
- 이 이미지는 NVIDIA 드라이버 라이브러리가 없는 순수 CPU 호스트용 이미지는 아님

즉 Ubuntu 서버에서도 공식 휠이 해당 GPU 아키텍처를 지원하지 않으면 서비스는 살아 있지만 성능은 CPU 수준으로 내려갑니다.

## 13. 참고 문서

- Docker Engine on Ubuntu: <https://docs.docker.com/engine/install/ubuntu/>
- NVIDIA Container Toolkit install guide: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>
- Paddle Linux pip install guide: <https://www.paddlepaddle.org.cn/documentation/docs/install/pip/linux-pip_en.html>

## 14. systemd 자동기동

템플릿 파일:

- [deploy/systemd/japim-docker.service](C:\Users\USER\projects\japim\deploy\systemd\japim-docker.service)

적용 예시:

```bash
sudo cp deploy/systemd/japim-docker.service /etc/systemd/system/japim.service
sudo systemctl daemon-reload
sudo systemctl enable --now japim.service
sudo systemctl status japim.service
```
