#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
python_executable="${PYTHON_EXECUTABLE:-python}"

case "$mode" in
  pending|full)
    exec "$python_executable" -m automation.cli sync --mode "$mode"
    ;;
  validate)
    exec "$python_executable" -m automation.cli validate
    ;;
  setup-dry-run)
    exec "$python_executable" -m automation.cli setup-sheet --dry-run
    ;;
  *)
    printf 'invalid affiliate sync mode: %s\n' "$mode" >&2
    exit 64
    ;;
esac
