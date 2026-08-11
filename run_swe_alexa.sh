#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
export PATH="${HOME}/.local/bin:${PATH}"
exec python3 -m swe_alexa "$@"
