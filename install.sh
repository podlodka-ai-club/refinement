#!/usr/bin/env bash
# Установка Memory Curator — просто запусти, без вопросов:
# сам найдёт opencode / Claude Code и поставит всё (MCP, команды, скиллы, worker).
# Флаги опциональны (для скриптов): --opencode | --claude | --base-dir ПУТЬ
set -euo pipefail
cd "$(dirname "$0")/core"

python3 -m venv .venv
.venv/bin/pip install --quiet -e .
exec .venv/bin/curator install "$@"
