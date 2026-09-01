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
  setup)
    if [[ "${ORVANI_CONFIRM_SETUP:-false}" != "true" ]]; then
      printf 'setup requires explicit ORVANI_CONFIRM_SETUP=true\n' >&2
      exit 64
    fi
    if [[ "${ORVANI_IMPORT_WORKSHEET:-}" != "Importações" ]]; then
      printf 'setup is restricted to the authorized Importações worksheet\n' >&2
      exit 64
    fi
    exec "$python_executable" -m automation.cli setup-sheet
    ;;
  *)
    printf 'invalid affiliate sync mode: %s\n' "$mode" >&2
    exit 64
    ;;
esac
