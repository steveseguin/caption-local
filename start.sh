#!/usr/bin/env bash
set -euo pipefail
CAPTION_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$CAPTION_ROOT/deploy.py" run "$@"
