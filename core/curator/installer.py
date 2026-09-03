"""Установщик Memory Curator: opencode / Claude Code.

Одна команда вместо ручных шагов:

    curator install --opencode   # MCP + команды + скиллы + worker
    curator install --claude     # .mcp.json + слэш-команды + скиллы
    curator install              # спросит, куда ставить

Единственный вопрос — куда класть базу знаний (любой путь, создастся при
первом сохранении). Идемпотентно: повторный запуск обновляет наши секции,
конфиг пользователя не трогает.
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


def default_base_dir() -> str:
    """Дефолт базы знаний — нейтральный путь (не привязан к машине автора)."""
    return os.path.expanduser("~/memory-curator")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _install_skills(dest_root: Path) -> list[Path]:
    """Скопировать ВСЕ скиллы из репо (curator-save, mapping-documentation
    и будущие) в <dest_root>/. wheel-установка без репо — пусто."""
    skills_root = _repo_root() / ".agents" / "skills"
    if not skills_root.is_dir():
        return []
    installed = []
    for source in sorted(skills_root.iterdir()):
        if not (source / "SKILL.md").exists():
            continue
        dest = dest_root / source.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        installed.append(dest)
    return installed


def _commands_source() -> dict:
    """Команды (/curator-*) из репо — источник правды для обоих харнесов."""
    path = _repo_root() / "integrations" / "commands.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_json_config(config_path: Path) -> tuple[dict | None, str | None]:
    if not config_path.exists():
        return {}, None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return None, f"не смог прочитать {config_path} ({e}) — боюсь сломать твой конфиг, добавь секции руками"
    if not isinstance(config, dict):
        return None, f"{config_path} не JSON-объект — добавь секции руками"
    return config, None


def _write_json_config(config_path: Path, config: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mcp_entry(base_dir: str) -> dict:
    command, args = _server_command()
    return {
        "command": command,
        **({"args": args} if args else {}),
        "env": {
            "MEMORY_BACKEND": "local",
            "CURATOR_BASE_DIR": base_dir,
            # MapRouter без карты молча = дефолт (session/{type}.md);
            # карта появится в базе — маршрутизация по темам включится сама
            "ROUTER_CLASS": "curator.routing.map_router.MapRouter",
        },
    }


def install_opencode(base_dir: str | None = None) -> list[str]:
    """MCP + команды + скиллы + worker в ~/.config/opencode."""
    home = Path(os.environ.get("HOME", str(Path.home())))
    base = base_dir or default_base_dir()
    steps = [f"База знаний: {base} (создастся при первом сохранении)"]

    config_path = home / ".config" / "opencode" / "opencode.json"
    config, error = _read_json_config(config_path)
    if config is None:
        return [f"⛔ MCP/команды: {error}"]
    config.setdefault("mcp", {})["memory-curator"] = _mcp_entry(base)
    commands = _commands_source()
    if commands:
        config.setdefault("command", {}).update(commands)
    _write_json_config(config_path, config)
    steps.append(f"✅ MCP-сервер и {len(commands)} команд /curator-*: {config_path} (остальное не тронуто)")

    skills = _install_skills(home / ".config" / "opencode" / "skills")
    if skills:
        steps.append(f"✅ Скиллы: {', '.join(s.name for s in skills)}")
    else:
        steps.append("⚠ скиллы не найдены в репо (wheel-установка?) — MCP и команды работают")

    try:
        from curator.daemon import ensure_worker
        steps.append(f"✅ Worker: {ensure_worker()}")
    except Exception as e:
        steps.append(f"⚠ worker не поднялся: {e} — запусти позже: curator start")

    steps.append("")
    steps.append("Готово. Перезапусти opencode — появятся команды /curator-*, тулзы curator_* и скиллы.")
    return steps


def install_claude(base_dir: str | None = None, project_dir: Path | None = None) -> list[str]:
    """.mcp.json в проекте (cwd) + слэш-команды ~/.claude/commands + скиллы."""
    home = Path(os.environ.get("HOME", str(Path.home())))
    project = project_dir or Path.cwd()
    base = base_dir or default_base_dir()
    steps = [f"База знаний: {base} (создастся при первом сохранении)"]

    mcp_path = project / ".mcp.json"
    config, error = _read_json_config(mcp_path)
    if config is None:
        return [f"⛔ .mcp.json: {error}"]
    config.setdefault("mcpServers", {})["memory-curator"] = _mcp_entry(base)
    _write_json_config(mcp_path, config)
    steps.append(f"✅ MCP-сервер: {mcp_path}")

    commands = _commands_source()
    commands_dir = home / ".claude" / "commands"
    if commands:
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, spec in commands.items():
            description = spec.get("description", "")
            template = spec.get("template", "")
            (commands_dir / f"{name}.md").write_text(
                f"---\ndescription: {description}\n---\n\n{template}\n",
                encoding="utf-8",
            )
        steps.append(f"✅ Слэш-команды: {len(commands)} в {commands_dir}")

    skills = _install_skills(home / ".claude" / "skills")
    if skills:
        steps.append(f"✅ Скиллы: {', '.join(s.name for s in skills)}")
    else:
        steps.append("⚠ скиллы не найдены в репо (wheel-установка?) — MCP и команды работают")

    steps.append("")
    steps.append("Готово. Перезапусти Claude Code в проекте — появятся команды /curator-*, тулзы curator_* и скиллы.")
    return steps
