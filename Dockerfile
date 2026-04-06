ARG CUDA_IMAGE=nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${PYTHON_IMAGE} AS model-fetch

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PADDLE_OCR_BASE_DIR=/tmp/paddle-cache \
    PADDLE_PDX_MODEL_SOURCE=BOS \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

RUN apt-get update && apt-get install -y \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY scripts /app/scripts

ARG PADDLE_FETCH_PACKAGE="paddlepaddle==3.2.0"
ARG PADDLE_FETCH_PACKAGE_INDEX="https://www.paddlepaddle.org.cn/packages/stable/cpu/"
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install "${PADDLE_FETCH_PACKAGE}" -i "${PADDLE_FETCH_PACKAGE_INDEX}" && \
    python3 -m pip install ".[ocr]" && \
    python3 /app/scripts/fetch_paddle_models.py --output-dir /opt/paddle-models/paddleocr --cache-dir /tmp/paddle-cache

FROM ${CUDA_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PADDLE_OCR_BASE_DIR=/app/models \
    PADDLE_PDX_MODEL_SOURCE=BOS \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    FLAGS_allocator_strategy=auto_growth \
    FLAGS_fraction_of_gpu_memory_to_use=0.1 \
    LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/cuda/targets/x86_64-linux/lib

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    poppler-utils \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/lib/x86_64-linux-gnu/libcudnn.so.9 /usr/lib/x86_64-linux-gnu/libcudnn.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcudart.so.12 /usr/local/cuda/targets/x86_64-linux/lib/libcudart.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcublas.so.12 /usr/local/cuda/targets/x86_64-linux/lib/libcublas.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcublasLt.so.12 /usr/local/cuda/targets/x86_64-linux/lib/libcublasLt.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcurand.so.10 /usr/local/cuda/targets/x86_64-linux/lib/libcurand.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcusolver.so.11 /usr/local/cuda/targets/x86_64-linux/lib/libcusolver.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcusparse.so.12 /usr/local/cuda/targets/x86_64-linux/lib/libcusparse.so && \
    ln -sf /usr/local/cuda/targets/x86_64-linux/lib/libcufft.so.11 /usr/local/cuda/targets/x86_64-linux/lib/libcufft.so && \
    ldconfig

WORKDIR /app

RUN mkdir -p /app/models

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY configs /app/configs
COPY models/README.md /app/models/README.md
COPY scripts /app/scripts
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
COPY --from=model-fetch /opt/paddle-models/paddleocr /app/models/paddleocr

ARG PADDLE_PACKAGE="paddlepaddle-gpu==3.2.0"
ARG PADDLE_PACKAGE_INDEX="https://www.paddlepaddle.org.cn/packages/stable/cu126/"
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install "${PADDLE_PACKAGE}" -i "${PADDLE_PACKAGE_INDEX}" && \
    python3 -m pip install ".[ocr]"

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
