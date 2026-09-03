"""Установщик Memory Curator: opencode / Claude Code.

Одна команда вместо пяти ручных шагов:

    curator install --opencode   # MCP-секция в конфиг opencode + скилл + worker
    curator install --claude     # .mcp.json в проекте + скилл
    curator install              # спросит: opencode или Claude Code

Идемпотентно: повторный запуск обновляет секцию memory-curator,
остальной конфиг пользователя не трогает.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def _server_command() -> tuple[str, list[str]]:
    """(command, args) запуска MCP-сервера из этого окружения.

    Prefer готовый entrypoint-скрипт в venv; editable-окружение без
    скрипта откатывается на `python -m curator.server`.
    """
    exe_dir = Path(sys.executable).parent
    candidate = exe_dir / "curator-mcp-server"
    if candidate.exists():
        return str(candidate), []
    return sys.executable, ["-m", "curator.server"]


def _default_base_dir() -> str:
    return os.path.expanduser("~/Documents/AI/personal/learnings")


def _skill_source() -> Path | None:
    """Скилл из репо (editable-установка). wheels без репо — скилл не ставим."""
    repo_root = Path(__file__).resolve().parents[2]
    skill = repo_root / ".agents" / "skills" / "curator-save"
    return skill if (skill / "SKILL.md").exists() else None


def _install_skill(dest_root: Path) -> str | None:
    """Скопировать скилл в <dest_root>/curator-save. Возвращает путь или None."""
    source = _skill_source()
    if source is None:
        return None
    dest = dest_root / "curator-save"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    return dest


def _merge_json_config(config_path: Path, update: dict, section: str, key: str) -> tuple[bool, str]:
    """Аккуратно вписать update[key] в cfg[section], не трогая остальное.

    Идемпотентно и безопасно: существующий конфиг с незнакомым/битым JSON
    не перезаписывается — человек правит руками.
    """
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return False, (f"не смог прочитать {config_path} ({e}) — "
                           f"боюсь сломать твой конфиг, добавь секцию руками")
        if not isinstance(config, dict):
            return False, f"{config_path} не JSON-объект — добавь секцию руками"

    config.setdefault(section, {})[key] = update
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, str(config_path)


def _mcp_entry() -> dict:
    command, args = _server_command()
    return {
        "command": command,
        **({"args": args} if args else {}),
        "env": {
            "MEMORY_BACKEND": "local",
            "CURATOR_BASE_DIR": _default_base_dir(),
        },
    }


def install_opencode() -> list[str]:
    """MCP-секция в ~/.config/opencode/opencode.json + скилл + worker."""
    home = Path(os.environ.get("HOME", str(Path.home())))
    steps = []

    ok, result = _merge_json_config(
        home / ".config" / "opencode" / "opencode.json",
        _mcp_entry(), section="mcp", key="memory-curator",
    )
    if not ok:
        return [f"⛔ MCP-конфиг: {result}"]
    steps.append(f"✅ MCP-сервер: {result} (секция mcp.memory-curator, остальное не тронуто)")

    skill = _install_skill(home / ".config" / "opencode" / "skills")
    if skill:
        steps.append(f"✅ Скилл curator-save: {skill}")
    else:
        steps.append("⚠ скилл не найден в репо (wheel-установка?) — MCP работает, скилл скопируй руками")

    try:
        from curator.daemon import ensure_worker
        steps.append(f"✅ Worker: {ensure_worker()}")
    except Exception as e:
        steps.append(f"⚠ worker не поднялся: {e} — запусти позже: curator start")

    steps.append("")
    steps.append("Готово. Перезапусти opencode — появятся тулзы curator_* и скилл curator-save.")
    return steps


def install_claude(project_dir: Path | None = None) -> list[str]:
    """.mcp.json в проекте (cwd) + скилл в ~/.claude/skills."""
    home = Path(os.environ.get("HOME", str(Path.home())))
    project = project_dir or Path.cwd()
    steps = []

    ok, result = _merge_json_config(
        project / ".mcp.json",
        _mcp_entry(), section="mcpServers", key="memory-curator",
    )
    if not ok:
        return [f"⛔ .mcp.json: {result}"]
    steps.append(f"✅ MCP-сервер: {result} (mcpServers.memory-curator)")

    skill = _install_skill(home / ".claude" / "skills")
    if skill:
        steps.append(f"✅ Скилл curator-save: {skill}")
    else:
        steps.append("⚠ скилл не найден в репо (wheel-установка?) — скопируй руками")

    steps.append("")
    steps.append("Готово. Перезапусти Claude Code в проекте — появятся тулзы curator_*.")
    return steps
