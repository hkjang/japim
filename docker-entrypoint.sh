#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  CONFIG_PATH="${JAPIM_CONFIG:-/app/configs/docker-gpu.yaml}"
  exec japim serve --config "${CONFIG_PATH}" --host 0.0.0.0 --port 8000
fi

exec japim "$@"
