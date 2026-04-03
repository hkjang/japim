#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/import_release_parts.sh --archive-base /path/to/japim-paddleocr_3.4.0-gpu.tar.gz [options]

Options:
  --archive-base PATH   Base archive path without part suffix
  --working-dir PATH    Working directory for merged files (default: ./var/import-linux)
  --engine NAME         Container engine to load with: docker|podman (default: podman)
  --retag NAME          Optional image tag to apply after load
  --skip-hash-check     Skip SHA256 verification
EOF
}

ARCHIVE_BASE=""
WORKING_DIR="./var/import-linux"
ENGINE="podman"
RETAG=""
SKIP_HASH_CHECK="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive-base)
      ARCHIVE_BASE="$2"
      shift 2
      ;;
    --working-dir)
      WORKING_DIR="$2"
      shift 2
      ;;
    --engine)
      ENGINE="$2"
      shift 2
      ;;
    --retag)
      RETAG="$2"
      shift 2
      ;;
    --skip-hash-check)
      SKIP_HASH_CHECK="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${ARCHIVE_BASE}" ]]; then
  echo "--archive-base is required" >&2
  usage >&2
  exit 1
fi

if [[ "${ENGINE}" != "docker" && "${ENGINE}" != "podman" ]]; then
  echo "--engine must be docker or podman" >&2
  exit 1
fi

mkdir -p "${WORKING_DIR}"

ARCHIVE_NAME="$(basename "${ARCHIVE_BASE}")"
MERGED_GZIP="${WORKING_DIR}/${ARCHIVE_NAME}"
if [[ "${MERGED_GZIP}" == *.tar.gz ]]; then
  TAR_PATH="${MERGED_GZIP%.gz}"
else
  TAR_PATH="${MERGED_GZIP}.tar"
fi

SHA_PATH="${ARCHIVE_BASE}.sha256"
shopt -s nullglob
PARTS=( "${ARCHIVE_BASE}".part* )
shopt -u nullglob

if (( ${#PARTS[@]} > 0 )); then
  cat "${PARTS[@]}" > "${MERGED_GZIP}"
elif [[ -f "${ARCHIVE_BASE}" ]]; then
  cp -f "${ARCHIVE_BASE}" "${MERGED_GZIP}"
else
  echo "Archive not found: ${ARCHIVE_BASE} or ${ARCHIVE_BASE}.part*" >&2
  exit 1
fi

if [[ "${SKIP_HASH_CHECK}" != "true" ]]; then
  if [[ ! -f "${SHA_PATH}" ]]; then
    echo "SHA256 file not found: ${SHA_PATH}" >&2
    exit 1
  fi
  EXPECTED="$(tr -d '\r\n' < "${SHA_PATH}" | tr '[:lower:]' '[:upper:]')"
  ACTUAL="$(sha256sum "${MERGED_GZIP}" | awk '{print toupper($1)}')"
  if [[ "${EXPECTED}" != "${ACTUAL}" ]]; then
    echo "SHA256 mismatch. expected=${EXPECTED} actual=${ACTUAL}" >&2
    exit 1
  fi
fi

gunzip -c "${MERGED_GZIP}" > "${TAR_PATH}"
LOAD_OUTPUT="$(${ENGINE} load -i "${TAR_PATH}")"

if [[ -n "${RETAG}" ]]; then
  SOURCE_TAG="$(printf '%s\n' "${LOAD_OUTPUT}" | awk -F': ' '/Loaded image:/ {print $2}' | tail -n1)"
  if [[ -z "${SOURCE_TAG}" ]]; then
    echo "Could not determine loaded image tag" >&2
    exit 1
  fi
  "${ENGINE}" tag "${SOURCE_TAG}" "${RETAG}"
fi

printf 'gzip=%s\n' "${MERGED_GZIP}"
printf 'tar=%s\n' "${TAR_PATH}"
printf 'engine=%s\n' "${ENGINE}"
printf 'container_load=%s\n' "${LOAD_OUTPUT}"
if [[ -n "${RETAG}" ]]; then
  printf 'retag=%s\n' "${RETAG}"
fi
