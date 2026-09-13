#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec "${SHOWCASE_PYTHON:-python3}" "$project_root/scripts/showcase_runtime.py" stop
