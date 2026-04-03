#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-japim-paddleocr:3.4.0-gpu}"
CONTAINER_NAME="${CONTAINER_NAME:-japim}"
HOST_PORT="${HOST_PORT:-8000}"
OUTPUT_DIR="${OUTPUT_DIR:-/srv/japim/output}"
TEMP_DIR="${TEMP_DIR:-/srv/japim/temp}"
FORCE_CPU="${FORCE_CPU:-false}"
DISABLE_SELINUX_LABEL="${DISABLE_SELINUX_LABEL:-false}"

mkdir -p "${OUTPUT_DIR}" "${TEMP_DIR}"

MOUNT_SUFFIX=":Z"
if [[ "${DISABLE_SELINUX_LABEL}" == "true" ]]; then
  MOUNT_SUFFIX=""
fi

ARGS=(
  run -d --replace
  --name "${CONTAINER_NAME}"
  -p "${HOST_PORT}:8000"
  -v "${OUTPUT_DIR}:/app/output${MOUNT_SUFFIX}"
  -v "${TEMP_DIR}:/app/temp${MOUNT_SUFFIX}"
)

if [[ "${DISABLE_SELINUX_LABEL}" == "true" ]]; then
  ARGS+=(--security-opt label=disable)
fi

if [[ "${FORCE_CPU}" == "true" ]]; then
  ARGS+=(-e "JAPIM_CONFIG=/app/configs/default.yaml")
else
  ARGS+=(--device nvidia.com/gpu=all)
fi

ARGS+=("${IMAGE}")

podman "${ARGS[@]}"
podman ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
