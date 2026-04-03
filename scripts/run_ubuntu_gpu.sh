#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-japim-paddleocr:3.4.0-gpu}"
CONTAINER_NAME="${CONTAINER_NAME:-japim}"
HOST_PORT="${HOST_PORT:-8000}"
OUTPUT_DIR="${OUTPUT_DIR:-/srv/japim/output}"
TEMP_DIR="${TEMP_DIR:-/srv/japim/temp}"
FORCE_CPU="${FORCE_CPU:-false}"

mkdir -p "${OUTPUT_DIR}" "${TEMP_DIR}"

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

ARGS=(
  run -d --restart unless-stopped
  --name "${CONTAINER_NAME}"
  -p "${HOST_PORT}:8000"
  -v "${OUTPUT_DIR}:/app/output"
  -v "${TEMP_DIR}:/app/temp"
)

if [[ "${FORCE_CPU}" == "true" ]]; then
  ARGS+=(-e "JAPIM_CONFIG=/app/configs/default.yaml")
else
  ARGS+=(--gpus all)
fi

ARGS+=("${IMAGE}")

docker "${ARGS[@]}"
docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
