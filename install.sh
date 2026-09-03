#!/usr/bin/env bash
# Установка Memory Curator: venv + пакет + интеграция в opencode / Claude Code.
# Использование: ./install.sh --opencode   (или --claude, --base-dir ПУТЬ)
set -euo pipefail
cd "$(dirname "$0")/core"

python3 -m venv .venv
.venv/bin/pip install --quiet -e .
exec .venv/bin/curator install "$@"
